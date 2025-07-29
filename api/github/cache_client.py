import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

logger = logging.getLogger('portfolio.api')

class GitHubCache:
    def __init__(self, use_cache=True):
        self.use_cache = use_cache
        self.cache_ttl = 3600
        self._init_cache()

    def _init_cache(self):
        connection_string = os.getenv('AzureWebJobsStorage')
        if connection_string and self.use_cache:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                self.container_name = 'github-cache'
                try:
                    self.blob_service_client.create_container(self.container_name)
                    logger.info(f"Created cache container: {self.container_name}")
                except Exception as e:
                    if "ContainerAlreadyExists" not in str(e):
                        logger.warning(f"Container creation issue: {str(e)}")
                    logger.info(f"Using existing cache container: {self.container_name}")
                logger.info("Azure Storage cache initialized")
            except ClientAuthenticationError as auth_err:
                logger.error(f"Azure Storage authentication failed: {auth_err}. "
                             "Check your storage account keys or managed identity configuration.")
                self.blob_service_client = None
            except HttpResponseError as http_err:
                if "AuthorizationFailure" in str(http_err) or "AuthenticationFailed" in str(http_err):
                    logger.error(f"Azure Storage authorization error: {http_err}. "
                                 "Verify your credentials and permissions.")
                elif "Network" in str(http_err) or "Forbidden" in str(http_err):
                    logger.error(f"Azure Storage network restriction: {http_err}. "
                                 "Check firewall, virtual network, or private endpoint settings.")
                else:
                    logger.error(f"Azure Storage HTTP error: {http_err}")
                self.blob_service_client = None
            except Exception as e:
                logger.error(f"Failed to initialize Azure Storage cache: {str(e)}")
                self.blob_service_client = None
        else:
            logger.warning("Azure Storage connection string not found, caching disabled")
            self.blob_service_client = None

    def _generate_cache_key(self, endpoint, params=None):
        normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
        if params:
            param_string = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
            return f"{normalized_endpoint}_{param_hash}"
        return normalized_endpoint

    def _get_from_cache(self, cache_key):
        if not self.blob_service_client or not self.use_cache:
            return None
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=cache_key
            )
            if blob_client.exists():
                data = blob_client.download_blob().readall()
                cache_data = json.loads(data)
                if 'expires_at' in cache_data:
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    if expires_at > datetime.now():
                        return cache_data['data']
                    else:
                        blob_client.delete_blob()
            return None
        except Exception as e:
            logger.warning(f"Error reading from cache for key {cache_key}: {str(e)}")
            return None

    def _save_to_cache(self, cache_key, data, ttl=None):
        if not self.blob_service_client or not self.use_cache:
            return False
        ttl = ttl or self.cache_ttl
        try:
            expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
            cache_data = {
                'data': data,
                'cached_at': datetime.now().isoformat(),
                'ttl': ttl
            }
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=cache_key
            )
            blob_client.upload_blob(
                json.dumps(cache_data, separators=(',', ':')),
                overwrite=True,
                content_settings=ContentSettings(
                    content_type='application/json',
                    content_encoding='utf-8'
                ),
                metadata={'expires_at': expires_at}
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving to cache for key {cache_key}: {str(e)}")
            return False

    def cleanup_expired_cache(self, batch_size=100, dry_run=False):
        """
        Clean up expired cache entries from Azure Blob Storage.
        
        Args:
            batch_size: Number of blobs to process in each batch
            dry_run: If True, only log what would be deleted without actually deleting
        
        Returns:
            dict: Summary of cleanup operation
        """
        if not self.blob_service_client or not self.use_cache:
            logger.warning("Cache cleanup skipped: no blob service client or caching disabled")
            return {
                "status": "skipped",
                "reason": "Cache not configured",
                "expired_count": 0,
                "deleted_count": 0,
                "error_count": 0
            }
        
        logger.info(f"Starting cache cleanup (batch_size={batch_size}, dry_run={dry_run})")
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Check if container exists
            if not container_client.exists():
                logger.info(f"Cache container '{self.container_name}' does not exist")
                return {
                    "status": "completed",
                    "reason": "Container does not exist",
                    "expired_count": 0,
                    "deleted_count": 0,
                    "error_count": 0
                }
            
            # Track cleanup statistics
            total_blobs = 0
            expired_count = 0
            deleted_count = 0
            error_count = 0
            current_time = datetime.now()
            
            # Process blobs in batches
            blob_batch = []
            
            logger.info(f"Scanning blobs in container '{self.container_name}'")
            
            for blob in container_client.list_blobs():
                total_blobs += 1
                blob_batch.append(blob)
                
                # Process batch when full
                if len(blob_batch) >= batch_size:
                    batch_results = self._process_cleanup_batch(
                        container_client, blob_batch, current_time, dry_run
                    )
                    expired_count += batch_results['expired']
                    deleted_count += batch_results['deleted']
                    error_count += batch_results['errors']
                    
                    # Clear batch
                    blob_batch = []
                    
                    # Log progress
                    if total_blobs % (batch_size * 10) == 0:
                        logger.info(f"Processed {total_blobs} blobs, found {expired_count} expired")
            
            # Process remaining blobs in final batch
            if blob_batch:
                batch_results = self._process_cleanup_batch(
                    container_client, blob_batch, current_time, dry_run
                )
                expired_count += batch_results['expired']
                deleted_count += batch_results['deleted']
                error_count += batch_results['errors']
            
            # Log final results
            logger.info(f"Cache cleanup completed: {total_blobs} total blobs, "
                    f"{expired_count} expired, {deleted_count} deleted, {error_count} errors")
            
            return {
                "status": "completed",
                "total_blobs": total_blobs,
                "expired_count": expired_count,
                "deleted_count": deleted_count,
                "error_count": error_count,
                "dry_run": dry_run,
                "cleanup_time": current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "error": str(e),
                "expired_count": 0,
                "deleted_count": 0,
                "error_count": 1
            }


    def _process_cleanup_batch(self, container_client, blob_batch, current_time, dry_run):
        """
        Process a batch of blobs for cleanup.
        
        Args:
            container_client: Azure container client
            blob_batch: List of blob objects to process
            current_time: Current datetime for expiration comparison
            dry_run: If True, don't actually delete blobs
        
        Returns:
            dict: Batch processing results
        """
        batch_expired = 0
        batch_deleted = 0
        batch_errors = 0
        
        for blob in blob_batch:
            try:
                # Download blob metadata to check expiration
                blob_client = container_client.get_blob_client(blob.name)
                
                # Download and parse blob content to check expiration
                blob_data = blob_client.download_blob().readall()
                cache_data = json.loads(blob_data)
                
                # Check if blob has expiration data
                if 'expires_at' in cache_data:
                    expires_at = datetime.fromisoformat(cache_data['expires_at'])
                    
                    # Check if expired
                    if expires_at <= current_time:
                        batch_expired += 1
                        
                        if dry_run:
                            # logger.debug(f"Would delete expired blob: {blob.name} (expired at {expires_at})")
                            pass
                        else:
                            # Delete the expired blob
                            blob_client.delete_blob()
                            batch_deleted += 1
                            # logger.debug(f"Deleted expired blob: {blob.name}")
                    # else:
                        # Blob is still valid
                        # time_remaining = expires_at - current_time
                        # logger.debug(f"Blob {blob.name} expires in {time_remaining}")
                else:
                    # Blob doesn't have expiration data - might be old format
                    # Check blob creation time as fallback
                    blob_age = current_time - blob.last_modified.replace(tzinfo=None)
                    if blob_age.total_seconds() > (self.cache_ttl * 2):  # Double the normal TTL
                        batch_expired += 1
                        
                        if dry_run:
                            logger.debug(f"Would delete old blob without expiration: {blob.name}")
                        else:
                            blob_client.delete_blob()
                            batch_deleted += 1
                            logger.debug(f"Deleted old blob: {blob.name}")
                            
            except json.JSONDecodeError:
                # Blob content is not valid JSON - might be corrupted
                logger.warning(f"Blob {blob.name} contains invalid JSON, marking for deletion")
                batch_expired += 1
                
                if not dry_run:
                    try:
                        blob_client.delete_blob()
                        batch_deleted += 1
                    except Exception as delete_err:
                        logger.error(f"Failed to delete corrupted blob {blob.name}: {str(delete_err)}")
                        batch_errors += 1
                        
            except Exception as e:
                logger.error(f"Error processing blob {blob.name}: {str(e)}")
                batch_errors += 1
        
        return {
            'expired': batch_expired,
            'deleted': batch_deleted,
            'errors': batch_errors
        }

    def get_cache_statistics(self):
        """
        Get statistics about the current cache state.
        
        Returns:
            dict: Cache statistics
        """
        if not self.blob_service_client or not self.use_cache:
            return {
                "status": "disabled",
                "total_blobs": 0,
                "total_size_bytes": 0,
                "expired_count": 0,
                "valid_count": 0
            }
        
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            if not container_client.exists():
                return {
                    "status": "no_container",
                    "total_blobs": 0,
                    "total_size_bytes": 0,
                    "expired_count": 0,
                    "valid_count": 0
                }
            
            total_blobs = 0
            total_size = 0
            expired_count = 0
            valid_count = 0
            current_time = datetime.now()
            
            for blob in container_client.list_blobs():
                total_blobs += 1
                total_size += blob.size
                expires_at = blob.metadata.get('expires_at') if blob.metadata else None
                
                if expires_at:
                    try:
                        expires_at_dt = datetime.fromisoformat(expires_at)
                        if expires_at_dt <= current_time:
                            expired_count += 1
                        else:
                            valid_count += 1
                    except Exception:
                        expired_count += 1
                else:
                    # No expiration data - check age
                    blob_age = current_time - blob.last_modified.replace(tzinfo=None)
                    if blob_age.total_seconds() > (self.cache_ttl * 2):
                        expired_count += 1
                    else:
                        valid_count += 1
            
            return {
                "status": "active",
                "total_blobs": total_blobs,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "expired_count": expired_count,
                "valid_count": valid_count,
                "container_name": self.container_name,
                "default_ttl_seconds": self.cache_ttl
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache statistics: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "total_blobs": 0,
                "total_size_bytes": 0,
                "expired_count": 0,
                "valid_count": 0
            }

