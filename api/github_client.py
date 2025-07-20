import json
import logging
import os
import requests
import hashlib
import time
from datetime import datetime, timedelta

from azure.storage.blob import BlobServiceClient, ContentSettings
from base64 import b64decode
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError
import re
from github_helpers import trim_processed_repo


from .rename.cache_client import GitHubCache
from .rename.github_api import GitHubAPI
from .rename.github_file_manager import GitHubFileManager
from .rename.github_repo_manager import GitHubRepoManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from azure.core.exceptions import HttpResponseError, ClientAuthenticationError


class GitHubClient:
    """
    Facade for GitHub operations, providing a unified interface for API, caching, file, and repo management.
    """
    def __init__(self, token=None, username=None, use_cache=True):
        self.api = GitHubAPI(token=token, username=username)
        self.cache = GitHubCache(use_cache=use_cache)
        self.file_manager = GitHubFileManager(self.api, self.cache)
        self.repo_manager = GitHubRepoManager(self.api, self.cache, self.file_manager)

    # Example pass-through methods for backward compatibility
    def get_repo_metadata(self, *args, **kwargs):
        return self.repo_manager.get_repo_metadata(*args, **kwargs)

    def get_all_repos_metadata(self, *args, **kwargs):
        return self.repo_manager.get_all_repos_metadata(*args, **kwargs)

    def get_file_content(self, *args, **kwargs):
        return self.file_manager.get_file_content(*args, **kwargs)

    def get_container_files(self, *args, **kwargs):
        return self.file_manager.get_container_files(*args, **kwargs)

    def get_all_repos_with_context(self, *args, **kwargs):
        return self.repo_manager.get_all_repos_with_context(*args, **kwargs)

    def cleanup_expired_cache(self, *args, **kwargs):
        return self.cache.cleanup_expired_cache(*args, **kwargs)

    def get_cache_statistics(self, *args, **kwargs):
        return self.cache.get_cache_statistics(*args, **kwargs)

    def _init_cache(self):
        """Initialize Azure Blob Storage cache with robust error handling."""
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
        """Generate a consistent cache key for endpoint and parameters."""
        normalized_endpoint = endpoint.lstrip('/').replace('/', '_').replace('?', '_').replace('&', '_')
        
        if params:
            param_string = json.dumps(params, sort_keys=True)
            param_hash = hashlib.md5(param_string.encode()).hexdigest()[:8]
            return f"{normalized_endpoint}_{param_hash}"
        
        return normalized_endpoint
    
    def _get_from_cache(self, cache_key):
        """Retrieve data from cache if available and not expired."""
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
                        logger.debug(f"Cache hit for key: {cache_key}")
                        return cache_data['data']
                    else:
                        logger.debug(f"Cache expired for key: {cache_key}")
                        blob_client.delete_blob()
                
            return None
        except Exception as e:
            logger.warning(f"Error reading from cache for key {cache_key}: {str(e)}")
            return None
    
    def _save_to_cache(self, cache_key, data, ttl=None):
        """Save data to cache with expiration time."""
        if not self.blob_service_client or not self.use_cache:
            return False
            
        ttl = ttl or self.cache_ttl
        
        try:
            cache_data = {
                'data': data,
                'expires_at': (datetime.now() + timedelta(seconds=ttl)).isoformat(),
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
                )
            )
            
            return True
        except Exception as e:
            logger.warning(f"Error saving to cache for key {cache_key}: {str(e)}")
            return False
        
    def _get_repo_languages(self, username=None, repo=None):
        """
        Get programming languages used in a repository.
        Independent of metadata - can be called standalone.
        
        Args:
            username: GitHub username
            repo: Repository name
            
        Returns:
            dict: Language names mapped to byte counts
        """
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        
        languages_endpoint = f"repos/{username}/{repo}/languages"
        
        try:
            # Let make_request handle caching with longer TTL for languages (4 hours)
            languages_data = self.make_request('GET', languages_endpoint, cache_ttl=14400)
            return languages_data if languages_data else {}
        except Exception as e:
            logger.warning(f"Failed to fetch languages for {username}/{repo}: {str(e)}")
            return {}
        
    def _decode_file_content(self, file_data, path, endpoint):
        """Helper to decode file content from GitHub API response."""
        content = file_data.get('content', '')
        if content:
            try:
                decoded_content = b64decode(content).decode('utf-8')
                return decoded_content
            except Exception as decode_error:
                logger.warning(f"Failed to decode content for {path}: {str(decode_error)}")
                # Fallback to raw API request
                return self.make_request('GET', endpoint, accept_raw=True, cache_ttl=3600)
        else:
            logger.warning(f"No content field in response for {path}")
            return None

    def _fetch_individual_file(self, username, repo, file_path):
        """Fetch a single file's content efficiently."""
        try:
            endpoint = f"repos/{username}/{repo}/contents/{file_path}"
            file_data = self.make_request('GET', endpoint, cache_ttl=3600)
            
            if file_data and isinstance(file_data, dict) and file_data.get('type') == 'file':
                return self._decode_file_content(file_data, file_path, endpoint)
            
            # If file_data doesn't have content field, try raw request
            return self.make_request('GET', endpoint, accept_raw=True, cache_ttl=3600)
            
        except Exception as e:
            logger.warning(f"Failed to fetch individual file {file_path}: {str(e)}")
            return None

    def _process_directory_files(self, file_data, path, username, repo):
        """Process directory listing to find container-level files."""
        # Determine if we're at repository root or in a subdirectory
        is_repo_root = path == '' or path == '.' or path == '/' or not path.strip()
        
        # Base files that exist everywhere
        base_files = {
            "README.md", 
            ".repo-context.json", 
            "ARCHITECTURE.md"
        }
        
        # Add context-specific files
        if is_repo_root:
            container_files = base_files | {"SKILLS-INDEX.md"}
            logger.debug(f"Checking repository root for files: {container_files}")
        else:
            container_files = base_files | {"PROJECT-MANIFEST.md"}
            logger.debug(f"Checking subdirectory '{path}' for files: {container_files}")
        
        found_files = {}
        files_needing_fetch = []
        
        # First pass: extract files with inline content
        for item in file_data:
            if item.get('type') == 'file' and item.get('name') in container_files:
                file_name = item['name']
                
                # Check if file has inline content (GitHub includes content for small files)
                if 'content' in item and item['content']:
                    try:
                        decoded_content = b64decode(item['content']).decode('utf-8')
                        found_files[file_name] = decoded_content
                        logger.debug(f"Found and decoded {file_name} in directory listing")
                    except Exception as decode_error:
                        logger.warning(f"Failed to decode {file_name} from directory listing: {str(decode_error)}")
                        files_needing_fetch.append(item)
                else:
                    # File too large for directory listing, needs individual fetch
                    files_needing_fetch.append(item)
        
        # Second pass: batch fetch remaining files (if any)
        if files_needing_fetch:
            logger.info(f"Fetching {len(files_needing_fetch)} files individually")
            for item in files_needing_fetch:
                file_name = item['name']
                file_path = item['path']
                
                # Make individual API call for this specific file
                file_content = self._fetch_individual_file(username, repo, file_path)
                if file_content:
                    found_files[file_name] = file_content
        
        # Log results
        if found_files:
            logger.info(f"Found {len(found_files)} files in {'root' if is_repo_root else 'subdirectory'} '{path}': {list(found_files.keys())}")
        else:
            logger.warning(f"No expected files found in {'root' if is_repo_root else 'subdirectory'} '{path}'")
        
        return found_files if found_files else None

    def make_request(self, method, endpoint, headers=None, params=None, data=None, accept_raw=False, use_cache=None, cache_ttl=None):
        """Make a request to GitHub API with optimized caching and error handling."""
        use_cache = self.use_cache if use_cache is None else use_cache
        full_url = f"https://api.github.com/{endpoint.lstrip('/')}"
        
        # Generate cache key once for the entire request
        cache_key = None
        cache_eligible = method.upper() == 'GET' and use_cache
        
        if cache_eligible:
            cache_key = self._generate_cache_key(endpoint, params)
            cached_data = self._get_from_cache(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit for {method} {endpoint}")
                return cached_data
        
        # Merge default headers with custom headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        if accept_raw:
            request_headers['Accept'] = 'application/vnd.github.v3.raw'
        
        # Make request with retry logic
        retries = 3
        backoff = 1
        last_exception = None
        
        for attempt in range(retries):
            try:
                response = requests.request(
                    method=method,
                    url=full_url,
                    headers=request_headers,
                    params=params,
                    json=data,
                    timeout=30 
                )

                # Handle authentication errors (401) - don't retry
                if response.status_code == 401:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('message', 'Bad credentials')
                    logger.error(f"GitHub authentication failed: {error_msg}")
                    raise Exception(f"GitHub authentication failed: {error_msg}")
                
                # Handle rate limiting (403) - wait and retry if reasonable
                elif response.status_code == 403:
                    if 'X-RateLimit-Remaining' in response.headers:
                        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                        if remaining == 0:
                            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                            wait_time = max(0, reset_time - time.time())
                            if wait_time > 0 and wait_time < 60:
                                logger.warning(f"Rate limit exceeded, waiting {wait_time:.2f}s")
                                time.sleep(wait_time + 1)
                                continue
                            else:
                                raise Exception(f"GitHub rate limit exceeded, wait time too long: {wait_time}s")
                
                    # Other 403 errors
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('message', 'Access forbidden')
                    raise Exception(f"GitHub access forbidden: {error_msg}")
                
                # Handle successful responses
                if response.status_code == 200:
                    if accept_raw:
                        result = response.text
                    else:
                        try:
                            result = response.json()
                        except json.JSONDecodeError:
                            result = response.text
                    
                    # Cache the result for GET requests using pre-generated cache key
                    if cache_eligible and cache_key:
                        ttl = cache_ttl or self.cache_ttl
                        self._save_to_cache(cache_key, result, ttl)
                    
                    return result
                
                # Handle 404s gracefully
                elif response.status_code == 404:
                    logger.debug(f"Resource not found: {full_url}")
                    return None
                
                # Handle other error codes
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"GitHub API error: {error_msg}")
                    if attempt == retries - 1:
                        raise Exception(error_msg)
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error on attempt {attempt+1}: {str(e)}")
                last_exception = e
                if attempt < retries - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 16)
                    continue
    
        # All retries failed
        raise Exception(f"GitHub API request failed after {retries} attempts: {str(last_exception)}")
        
    def get_repo_metadata(self, username=None, repo=None, include_languages=False):
        """
        Get detailed information for a repository.
        
        Args:
            username: GitHub username
            repo: Repository name  
            include_languages: Whether to also fetch language data
            
        Returns:
            dict: Repository metadata, optionally with languages
        """
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        
        endpoint = f"repos/{username}/{repo}"
        
        repo_data = self.make_request('GET', endpoint, cache_ttl=7200)  # 2 hour cache for metadata
        if not repo_data:
            return None

        # Optionally fetch languages if requested
        if include_languages:
            try:
                languages_data = self._get_repo_languages(username, repo)
                repo_data['languages'] = languages_data
            except Exception as e:
                logger.warning(f"Failed to fetch languages for {username}/{repo}: {str(e)}")
                repo_data['languages'] = {}

        return repo_data

    def get_all_repos_metadata(self, username=None, per_page=100, include_languages=False):
        """
        Get repositories for a user with pagination handling and optimized caching.
        
        Args:
            username: GitHub username (defaults to instance username)
            per_page: Number of repositories per page (max 100)
            include_languages: Whether to fetch language data for each repository
            
        Returns:
            list: Repository metadata, optionally with language data
        """
        username = username or self.username
        endpoint = f"users/{username}/repos"
        params = {'sort': 'updated', 'per_page': per_page}
        # Cache key for the complete aggregated result (all pages + optional languages)
        cache_suffix = "_with_languages" if include_languages else "_basic"
        complete_cache_key = self._generate_cache_key(f"users_{username}_repos_complete{cache_suffix}", {'per_page': per_page})
        
        # Check cache for complete result
        cached_data = self._get_from_cache(complete_cache_key)
        if cached_data is not None:
            logger.info(f"Using cached repository data for {username} " + 
                       ("(with languages)" if include_languages else "(basic)"))
            return cached_data
        
        # If not cached, fetch all pages (make_request handles individual page caching)
        all_repos = []
        page = 1
        
        while True:
            params['page'] = page
            logger.info(f"Fetching repositories page {page} for {username}")
            
            try:
                # make_request handles caching of individual pages automatically
                repos = self.make_request('GET', endpoint, params=params, cache_ttl=1800)  # 30 min per page
                
                if not repos or not isinstance(repos, list):
                    break
                    
                all_repos.extend(repos)
                logger.info(f"Fetched {len(repos)} repositories on page {page}")
                
                if len(repos) < per_page:
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching repos for {username}, page {page}: {str(e)}")
                break
    
        # Enhance with languages if requested (each language call also cached by make_request)
        if include_languages and all_repos:
            logger.info(f"Fetching language data for {len(all_repos)} repositories")
            for repo in all_repos:
                try:
                    # _get_repo_languages calls make_request which handles caching
                    languages = self._get_repo_languages(username, repo['name'])
                    repo['languages'] = languages
                except Exception as e:
                    logger.warning(f"Failed to fetch languages for {repo['name']}: {str(e)}")
                    repo['languages'] = {}
    
        # Cache ONLY the complete aggregated result (not individual API responses)
        if all_repos:
            self._save_to_cache(complete_cache_key, all_repos, ttl=7200)  # 2 hours for complete result
            logger.info(f"Cached {len(all_repos)} repositories for {username} " + 
                       ("with languages" if include_languages else "without languages"))
                
        return all_repos

    def get_file_content(self, username=None, repo=None, path=None):
        """
         Generic method to fetch a specific file's content.
        Returns the raw content as string, or None if not found.
        """
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        # Empty path is valid and represents the repository root
        path_segment = path if path else ""

        endpoint = f"repos/{username}/{repo}/contents/{path_segment}"

        try:
            # Single API call to get file/directory metadata (cached for 1 hour)
            file_data = self.make_request('GET', endpoint, cache_ttl=3600)
            
            if not file_data:
                logger.debug(f"File or directory not found: {username}/{repo}/{path_segment}")
                return None

            # Handle single file - return raw content only
            if isinstance(file_data, dict) and file_data.get('type') == 'file':
                return self._decode_file_content(file_data, path, endpoint)
            
            # Handle directory - return raw list for root directory or process for subdirectories
            elif isinstance(file_data, list):
                if not path or path == "" or path == "/":
                    return file_data
                else:
                    logger.info(f"Path {path} is a directory, checking for container-level files")
                    return self._process_directory_files(file_data, path, username, repo)
            
            # Handle edge cases
            elif isinstance(file_data, dict) and file_data.get('type') == 'dir':
                logger.warning(f"Directory response returned as dict instead of list for {path}")
                return None

            # Fallback to raw content request
            logger.debug(f"Unknown file type, attempting raw request for {path}")
            return self.make_request('GET', endpoint, accept_raw=True, cache_ttl=3600)
            
        except Exception as e:
            logger.error(f"Error fetching file content for {username}/{repo}/{path_segment}: {str(e)}")
            return None

    def get_container_files(self, username=None, repo=None, container_path=""):
        """
        Optimized method to get all container-level files based on location.
        This is now just a wrapper around get_file_content for consistency.
        """
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        
        # Normalize container path
        container_path = container_path.strip('/') if container_path else ""
        
        # Use the optimized get_file_content method
        return self.get_file_content(username, repo, container_path or "")
    
    def get_all_repos_with_context(self, username=None, include_languages=True):
        """
        Get all repositories with context and optionally languages.
        Optimized for bulk operations with AI Assistant.
        
        Args:
            username: GitHub username
            include_languages: Whether to fetch language data for each repository
    
        Returns:
            list: Repository data with context and optionally languages (raw data)
        """
        username = username or self.username
        
        # Cache key for the complete enhanced result
        cache_suffix = "_with_languages" if include_languages else "_basic"
        cache_key = f"repos_with_context_{username}{cache_suffix}"
        
        # Always log execution start with request ID for traceability
        request_id = f"req-{int(time.time())}"
        
        # Check cache for complete enhanced result
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            logger.info(f"Request ID: {request_id} - Using cached data ({len(cached_data)} repositories)")
            return cached_data

        # Get all repositories (this method handles its own caching)
        all_repos = self.get_all_repos_metadata(username, include_languages=include_languages)
        
        # Enhance each repository with context (get_file_content uses make_request which caches)
        repos_with_context = []
        for repo in all_repos:
            try:
                repo_name = repo['name']
                
                # Get repository context (make_request handles caching)
                repo_context = self.get_file_content(username, repo_name, '.repo-context.json')
                
                if repo_context and isinstance(repo_context, str):
                    try:
                        repo['repoContext'] = json.loads(repo_context)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in context for {repo_name}")
                        repo['repoContext'] = {}
                else:
                    repo['repoContext'] = {}
                
                if 'contents_url' in repo:
                    try:
                        # Get root directory listing (single API call, cached)
                        root_files = self.get_file_content(username, repo_name, "")

                        if isinstance(root_files, list):
                            # Extract just the file paths for efficiency
                            file_paths = [item.get('path') for item in root_files 
                                        if isinstance(item, dict) and 'path' in item]
                            repo['file_paths'] = file_paths
                            
                        else:
                            logger.warning(f"Root files for {repo_name} is not a list: {type(root_files)}")
                    except Exception as e:
                        logger.warning(f"Failed to get file listing for {repo_name}: {str(e)}")
                else:
                    logger.warning(f"No contents_url found for {repo_name}, unable to fetch file listing")
                
                trimmed_repo = trim_processed_repo(repo)
                repos_with_context.append(trimmed_repo)
                
            except Exception as e:
                logger.warning(f"Failed to enhance {repo.get('name', 'unknown')}: {str(e)}")
                # Ensure repo has required fields even on error
                if 'languages' not in repo and include_languages:
                    repo['languages'] = {}
                repo['repoContext'] = {}
                trimmed_repo = trim_processed_repo(repo)
                repos_with_context.append(trimmed_repo)
                
        # Cache ONLY the complete enhanced result (raw data)
        self._save_to_cache(cache_key, repos_with_context, ttl=3600)  # 1 hour for enhanced data
    
        logger.info(f"Enhanced {len(repos_with_context)} repositories with context for {username} " +
                   ("(with languages)" if include_languages else "(without languages)"))
    
        return repos_with_context
    
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
                            logger.debug(f"Would delete expired blob: {blob.name} (expired at {expires_at})")
                        else:
                            # Delete the expired blob
                            blob_client.delete_blob()
                            batch_deleted += 1
                            logger.debug(f"Deleted expired blob: {blob.name}")
                    else:
                        # Blob is still valid
                        time_remaining = expires_at - current_time
                        logger.debug(f"Blob {blob.name} expires in {time_remaining}")
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
                
                try:
                    # Check if blob is expired
                    blob_client = container_client.get_blob_client(blob.name)
                    blob_data = blob_client.download_blob().readall()
                    cache_data = json.loads(blob_data)
                    
                    if 'expires_at' in cache_data:
                        expires_at = datetime.fromisoformat(cache_data['expires_at'])
                        if expires_at <= current_time:
                            expired_count += 1
                        else:
                            valid_count += 1
                    else:
                        # No expiration data - check age
                        blob_age = current_time - blob.last_modified.replace(tzinfo=None)
                        if blob_age.total_seconds() > (self.cache_ttl * 2):
                            expired_count += 1
                        else:
                            valid_count += 1
                            
                except Exception:
                    # Count problematic blobs as expired
                    expired_count += 1
            
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

