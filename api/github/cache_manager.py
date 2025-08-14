import os
import json
import hashlib
import logging
import functools
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List, Callable
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

logger = logging.getLogger('portfolio.api')

class CacheManager:
    """
    Centralized caching system for the Portfolio API.
    
    This class provides a unified approach to managing caching across different levels:
    1. Low-Level Request Caching: Caches responses from external APIs (e.g., GitHub API)
    2. Bundle Caching: Caches repository bundles (individual and aggregated)
    3. Metadata Caching: Caches metadata for trained models
    
    Features:
    - Dynamic TTL (None for no expiration)
    - Decorator-based caching for easy application to methods
    - Azure Blob Storage backend with proper error handling
    - Change detection based on fingerprints
    
    Attributes:
        container_name (str): Name of the blob container for cache storage
        default_ttl (int): Default time-to-live for cache entries in seconds
        blob_service_client (BlobServiceClient): Azure Blob Storage client
        use_cache (bool): Whether caching is enabled
    """
    def __init__(self, container_name: str = "github-cache", default_ttl: int = 21600, use_cache: bool = True) -> None:
        """
        Initialize the cache manager with Azure Blob Storage backend.
        
        Args:
            container_name: The name of the blob container to use. Defaults to "github-cache".
            default_ttl: Default time-to-live in seconds. Defaults to 6 hours (21600 seconds).
            use_cache: Whether to enable caching functionality. Defaults to True.
        """
        self.container_name = container_name
        self.default_ttl = default_ttl
        self.use_cache = use_cache
        self._init_cache()
    
    def _init_cache(self) -> None:
        """
        Initialize Azure Blob Storage connection and create container if needed.
        
        Sets up the blob service client using the AzureWebJobsStorage connection string
        and creates the cache container if it doesn't exist. Handles authentication
        and network errors gracefully.
        """
        connection_string = os.getenv('AzureWebJobsStorage')
        if connection_string and self.use_cache:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
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
            logger.warning("Azure Storage connection string not found or caching disabled")
            self.blob_service_client = None

    def get(self, cache_key: str) -> Dict[str, Any]:
        """
        Retrieve cache data and metadata for a given key with expiration checking.
        
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

            # Check if non-expiring cache
            if metadata.get('no_expiry') == 'True':
                data = json.loads(blob_client.download_blob().readall())
                return {
                    'status': 'valid',
                    'data': data.get('data'),
                    'fingerprint': metadata.get('fingerprint'),
                    'no_expiry': True,
                    'last_modified': properties.last_modified.isoformat(),
                    'size_bytes': properties.size
                }

            # Check expiration for TTL-based cache
            current_time = datetime.now()
            if 'expires_at' in metadata:
                expires_at = datetime.fromisoformat(metadata['expires_at'])
                time_until_expiry = (expires_at - current_time).total_seconds()
                if expires_at > current_time:
                    data = json.loads(blob_client.download_blob().readall())
                    return {
                        'status': 'valid',
                        'data': data.get('data'),
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
                    'status': 'error',
                    'data': None,
                    'metadata': metadata,
                    'last_modified': properties.last_modified.isoformat(),
                    'size_bytes': properties.size
                }
        except Exception as e:
            logger.warning(f"Error retrieving cache entry for key {cache_key}: {str(e)}")
            return {'status': 'error', 'data': None, 'metadata': None}

    def save(self, cache_key: str, data: Any, ttl: Optional[int] = None, fingerprint: Optional[str] = None) -> bool:
        """
        Save data to cache with optional TTL.
        
        Args:
            cache_key: The cache key to store data under
            data: The data to cache (must be JSON serializable)
            ttl: Time-to-live in seconds. None means no expiration.
            
        Returns:
            True if successfully saved, False otherwise
        """
        if not self.blob_service_client or not self.use_cache:
            return False
        try:
            metadata = {}
            cache_data = {
                'data': data,
                'cached_at': datetime.now().isoformat()
            }
            
            # Store fingerprint if provided
            if fingerprint:
                metadata['fingerprint'] = fingerprint
            
            if ttl is None:
                # Non-expiring cache
                metadata['no_expiry'] = 'True'
                cache_data['ttl'] = None
            else:
                # TTL-based cache
                ttl = ttl or self.default_ttl
                expires_at = (datetime.now() + timedelta(seconds=ttl)).isoformat()
                metadata['expires_at'] = expires_at
                cache_data['ttl'] = ttl
            
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
                metadata=metadata
            )
            return True
        except Exception as e:
            logger.warning(f"Error saving to cache for key {cache_key}: {str(e)}")
            return False

    def delete(self, cache_key: str) -> bool:
        """
        Delete a cache entry.
        
        Args:
            cache_key: The cache key to delete
            
        Returns:
            True if successfully deleted or didn't exist, False on error
        """
        if not self.blob_service_client or not self.use_cache:
            return False
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=cache_key
            )
            if blob_client.exists():
                blob_client.delete_blob()
            return True
        except Exception as e:
            logger.warning(f"Error deleting cache entry for key {cache_key}: {str(e)}")
            return False

    def cache_decorator(self, cache_key_func: Callable, ttl: Optional[int] = None):
        """
        Decorator to handle caching logic for any function.
        
        Args:
            cache_key_func: A function that generates a cache key based on function arguments
            ttl: Time-to-live in seconds. None means no expiration.
            
        Returns:
            A decorator function that wraps the target function with caching logic
            
        Example:
        ```python
        cache_manager = CacheManager(container_name="github-cache")
        
        def generate_request_cache_key(method, endpoint, params):
            return f"request:{method}:{endpoint}:{hashlib.md5(str(params).encode()).hexdigest()[:8]}"
            
        class GitHubAPI:
            @cache_manager.cache_decorator(cache_key_func=generate_request_cache_key, ttl=3600)
            def make_request(self, method: str, endpoint: str, params: Dict[str, Any]):
                # Logic for making API request
                pass
        ```
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key based on function arguments
                try:
                    cache_key = cache_key_func(*args[1:], **kwargs)
                except TypeError:
                    cache_key = cache_key_func(*args, **kwargs)
                
                # Check cache
                cache_result = self.get(cache_key)
                if cache_result['status'] == 'valid':
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cache_result['data']
                
                # Cache miss or expired, call the function
                logger.debug(f"Cache miss for key: {cache_key}, calling function")
                result = func(*args, **kwargs)
                
                # Save result to cache
                self.save(cache_key, result, ttl=ttl)
                
                return result
            return wrapper
        return decorator

    def cleanup_expired_cache(self, batch_size: int = 100, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up expired cache entries from Azure Blob Storage.
        
        Args:
            batch_size: Number of blobs to process in each batch. Defaults to 100
            dry_run: If True, only identifies expired entries without deleting them
            
        Returns:
            Dictionary containing cleanup operation results
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
                    batch_result = self._process_cleanup_batch(blob_batch, current_time, dry_run)
                    expired_count += batch_result['expired']
                    deleted_count += batch_result['deleted']
                    error_count += batch_result['errors']
                    blob_batch = []
            
            # Process remaining blobs
            if blob_batch:
                batch_result = self._process_cleanup_batch(blob_batch, current_time, dry_run)
                expired_count += batch_result['expired']
                deleted_count += batch_result['deleted']
                error_count += batch_result['errors']
            
            logger.info(f"Cache cleanup completed: {expired_count} expired, {deleted_count} deleted")
            
            return {
                "status": "completed",
                "total_blobs": total_blobs,
                "expired_count": expired_count,
                "deleted_count": deleted_count,
                "error_count": error_count,
                "dry_run": dry_run,
                "cleanup_time": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error during cache cleanup: {str(e)}")
            return {
                "status": "failed",
                "reason": str(e),
                "expired_count": 0,
                "deleted_count": 0,
                "error_count": 1
            }

    def _process_cleanup_batch(self, blob_batch, current_time, dry_run):
        """Process a batch of blobs for cleanup."""
        expired = 0
        deleted = 0
        errors = 0
        
        for blob in blob_batch:
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=blob.name
                )
                
                properties = blob_client.get_blob_properties()
                metadata = properties.metadata
                
                # Skip non-expiring cache entries
                if metadata.get('no_expiry') == 'True':
                    continue
                
                # Check if expired
                if 'expires_at' in metadata:
                    expires_at = datetime.fromisoformat(metadata['expires_at'])
                    if expires_at <= current_time:
                        expired += 1
                        if not dry_run:
                            blob_client.delete_blob()
                            deleted += 1
                else:
                    # No expiration metadata, check creation time as fallback
                    creation_time = properties.creation_time
                    age_seconds = (current_time - creation_time).total_seconds()
                    
                    # If older than 30 days and no expiration set, consider expired
                    if age_seconds > 30 * 24 * 60 * 60:
                        expired += 1
                        if not dry_run:
                            blob_client.delete_blob()
                            deleted += 1
            except Exception as e:
                logger.warning(f"Error processing blob {blob.name} during cleanup: {str(e)}")
                errors += 1
        
        return {'expired': expired, 'deleted': deleted, 'errors': errors}

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary containing cache statistics:
            - total_entries: Total number of cache entries
            - total_size_bytes: Total size of all cache entries in bytes
            - entries_by_type: Dictionary of entry counts by type (determined by prefix)
            - oldest_entry: ISO timestamp of oldest entry
            - newest_entry: ISO timestamp of newest entry
        """
        if not self.blob_service_client or not self.use_cache:
            return {
                "status": "disabled",
                "total_entries": 0,
                "total_size_bytes": 0
            }
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            # Check if container exists
            if not container_client.exists():
                return {
                    "status": "empty",
                    "total_entries": 0,
                    "total_size_bytes": 0
                }
            
            # Track statistics
            total_entries = 0
            total_size_bytes = 0
            entries_by_type = {}
            oldest_timestamp = None
            newest_timestamp = None
            
            # Process all blobs
            for blob in container_client.list_blobs():
                total_entries += 1
                total_size_bytes += blob.size
                
                # Track by type (using prefix)
                prefix = blob.name.split('_')[0] if '_' in blob.name else 'unknown'
                entries_by_type[prefix] = entries_by_type.get(prefix, 0) + 1
                
                # Track timestamps
                if oldest_timestamp is None or blob.last_modified < oldest_timestamp:
                    oldest_timestamp = blob.last_modified
                
                if newest_timestamp is None or blob.last_modified > newest_timestamp:
                    newest_timestamp = blob.last_modified
            
            return {
                "status": "active",
                "total_entries": total_entries,
                "total_size_bytes": total_size_bytes,
                "entries_by_type": entries_by_type,
                "oldest_entry": oldest_timestamp.isoformat() if oldest_timestamp else None,
                "newest_entry": newest_timestamp.isoformat() if newest_timestamp else None
            }
        except Exception as e:
            logger.error(f"Error getting cache statistics: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "total_entries": 0,
                "total_size_bytes": 0
            }

# Create a global instance of CacheManager
cache_manager = CacheManager()
