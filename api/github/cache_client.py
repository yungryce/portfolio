import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

logger = logging.getLogger('portfolio.api')

class GitHubCache:
    """
    Azure Blob Storage-based caching system for GitHub API responses.
    
    This class provides a robust caching layer that stores GitHub API responses
    in Azure Blob Storage with TTL-based expiration and automatic cleanup capabilities.
    
    Attributes:
        use_cache (bool): Whether caching is enabled
        cache_ttl (int): Default time-to-live for cache entries in seconds
        blob_service_client (BlobServiceClient): Azure Blob Storage client
        container_name (str): Name of the blob container for cache storage
    """
    def __init__(self, use_cache: bool = True) -> None:
        """
        Initialize the GitHub cache with Azure Blob Storage backend.
        
        Args:
            use_cache: Whether to enable caching functionality. Defaults to True.
        """
        self.use_cache = use_cache
        self.cache_ttl = 21600  # Default TTL of 6 hours
        self._init_cache()

    def _init_cache(self) -> None:
        """
        Initialize Azure Blob Storage connection and create container if needed.
        
        Sets up the blob service client using the AzureWebJobsStorage connection string
        and creates the cache container if it doesn't exist. Handles authentication
        and network errors gracefully.
        
        Raises:
            Logs errors but doesn't raise exceptions to allow graceful fallback
            when Azure Storage is not available.
        """
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

    def _generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a normalized cache key from an endpoint and optional parameters.
        
        Creates a consistent, filesystem-safe cache key by normalizing the endpoint
        and including a hash of parameters when provided.
        
        Args:
            endpoint: The API endpoint or identifier to cache
            params: Optional dictionary of parameters to include in the key
            
        Returns:
            A normalized cache key string safe for use as a blob name
            
        Example:
            >>> cache._generate_cache_key("repos/user/repo", {"include": "languages"})
            "repos_user_repo_a1b2c3d4"
        """
        normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
        if params:
            param_string = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
            return f"{normalized_endpoint}_{param_hash}"
        return normalized_endpoint

    def _get_from_cache(self, cache_key: str) -> Dict[str, Any]:
        """
        Retrieve cache data and metadata for a given key with expiration checking.
        
        Fetches the cached data from Azure Blob Storage, validates its expiration,
        and returns comprehensive metadata about the cache entry status.
        
        Args:
            cache_key: The cache key to retrieve
            
        Returns:
            Dictionary containing:
            - status: 'valid', 'expired', 'missing', 'disabled', or 'error'
            - data: The cached data (None if not valid)
            - metadata: Blob metadata dictionary
            - expires_at: ISO format expiration timestamp (if available)
            - time_until_expiry_seconds: Seconds until expiration (if valid)
            - last_modified: ISO format last modified timestamp
            - size_bytes: Size of the cached data in bytes
            
        Example:
            >>> result = cache._get_from_cache("repos_user_repo")
            >>> if result['status'] == 'valid':
            ...     data = result['data']
        """
        if not self.blob_service_client or not self.use_cache:
            return {'status': 'disabled', 'data': None, 'metadata': None}
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=cache_key
            )
            if not blob_client.exists():
                return {'status': 'missing', 'data': None, 'metadata': None}

            properties = blob_client.get_blob_properties()
            metadata = properties.metadata

            # Check expiration
            current_time = datetime.now()
            if 'expires_at' in metadata:
                expires_at = datetime.fromisoformat(metadata['expires_at'])
                time_until_expiry = (expires_at - current_time).total_seconds()
                if expires_at > current_time:
                    data = json.loads(blob_client.download_blob().readall())
                    return {
                        'status': 'valid',
                        'data': data.get('data'),
                        'metadata': metadata,
                        'expires_at': expires_at.isoformat(),
                        'time_until_expiry_seconds': int(time_until_expiry),
                        'last_modified': properties.last_modified.isoformat(),
                        'size_bytes': properties.size
                    }
                else:
                    blob_client.delete_blob()
                    return {
                        'status': 'expired',
                        'data': None,
                        'metadata': metadata,
                        'expires_at': expires_at.isoformat(),
                        'time_until_expiry_seconds': 0,
                        'last_modified': properties.last_modified.isoformat(),
                        'size_bytes': properties.size
                    }
            else:
                logger.warning(f"Cache key {cache_key} missing expires_at metadata")
                return {
                    'status': 'None',
                    'data': None,
                    'metadata': metadata,
                    'last_modified': properties.last_modified.isoformat(),
                    'size_bytes': properties.size
                }
        except Exception as e:
            logger.warning(f"Error retrieving cache entry for key {cache_key}: {str(e)}")
            return {'status': 'error', 'data': None, 'metadata': None}

    def _save_to_cache(self, cache_key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        Save data to cache with specified or default TTL.
        
        Stores the provided data in Azure Blob Storage with proper JSON serialization,
        content type settings, and expiration metadata.
        
        Args:
            cache_key: The cache key to store data under
            data: The data to cache (must be JSON serializable)
            ttl: Time-to-live in seconds. Uses default cache_ttl if not provided
            
        Returns:
            True if successfully saved, False otherwise
            
        Example:
            >>> success = cache._save_to_cache("user_repos", repos_data, ttl=3600)
            >>> if success:
            ...     print("Data cached successfully")
        """
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

    def cleanup_expired_cache(self, batch_size: int = 100, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up expired cache entries from Azure Blob Storage.
        
        Scans all blobs in the cache container, identifies expired entries based on
        their expiration metadata or age, and optionally deletes them. Processes
        blobs in batches for better performance and memory usage.
        
        Args:
            batch_size: Number of blobs to process in each batch. Defaults to 100
            dry_run: If True, only identifies expired entries without deleting them
            
        Returns:
            Dictionary containing cleanup operation results:
            - status: 'completed', 'skipped', or 'failed'
            - total_blobs: Total number of blobs processed
            - expired_count: Number of expired blobs found
            - deleted_count: Number of blobs actually deleted
            - error_count: Number of errors encountered
            - dry_run: Whether this was a dry run
            - cleanup_time: ISO timestamp of cleanup operation
            
        Example:
            >>> result = cache.cleanup_expired_cache(batch_size=50, dry_run=True)
            >>> print(f"Found {result['expired_count']} expired entries")
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
        Process a batch of blobs for cleanup operation.
        
        Examines each blob in the batch to determine if it's expired based on
        metadata or age, and optionally deletes expired blobs.
        
        Args:
            container_client: Azure container client for blob operations
            blob_batch: List of blob objects to process
            current_time: Current datetime for expiration comparison
            dry_run: If True, don't actually delete blobs
            
        Returns:
            Dictionary with batch processing results:
            - expired: Number of expired blobs found in this batch
            - deleted: Number of blobs actually deleted from this batch
            - errors: Number of errors encountered in this batch
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
        Get comprehensive statistics about the current cache state.
        
        Analyzes all blobs in the cache container to provide detailed statistics
        including total size, number of valid/expired entries, and container health.
        
        Returns:
            Dictionary containing cache statistics:
            - status: 'active', 'disabled', 'no_container', or 'error'
            - total_blobs: Total number of cache entries
            - total_size_bytes: Total size of all cache entries in bytes
            - total_size_mb: Total size in megabytes (rounded to 2 decimal places)
            - expired_count: Number of expired cache entries
            - valid_count: Number of valid cache entries
            - container_name: Name of the cache container
            - default_ttl_seconds: Default TTL for new cache entries
            
        Example:
            >>> stats = cache.get_cache_statistics()
            >>> print(f"Cache has {stats['valid_count']} valid entries, "
            ...       f"{stats['total_size_mb']} MB total")
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

