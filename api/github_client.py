import json
import logging
import os
import re
import requests
import hashlib
import time
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, ContentSettings
from base64 import b64decode
from azure.core.exceptions import HttpResponseError, ClientAuthenticationError

# Configure logging
logger = logging.getLogger('portfolio.github_client')
logger.setLevel(logging.INFO)

class GitHubClient:
    """Streamlined GitHub client focused on efficient file fetching with caching."""
    
    def __init__(self, token=None, username=None, use_cache=True):
        """Initialize the GitHub client with authentication."""
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.username = username or 'yungryce'
        self.headers = {'Authorization': f'token {self.token}'} if self.token else {}
        self.use_cache = use_cache
        self.cache_ttl = 3600  # Default cache TTL: 1 hour
        
        # Initialize Azure Blob Storage for caching
        self._init_cache()

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
            
            logger.debug(f"Saved to cache: {cache_key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Error saving to cache for key {cache_key}: {str(e)}")
            return False
        
    def _decode_file_content(self, file_data, path, endpoint):
        """Helper to decode file content from GitHub API response."""
        content = file_data.get('content', '')
        if content:
            try:
                decoded_content = b64decode(content).decode('utf-8')
                logger.debug(f"Successfully decoded file content for {path}")
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
                logger.debug(f"Making {method} request to {full_url} (attempt {attempt+1}/{retries})")
                
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
                    
                    logger.debug(f"Successful {method} request to {endpoint}")
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
        
        
        
    def get_repo_metadata(self, username=None, repo=None):
            """Get detailed information for a repository."""
            username = username or self.username
            if not repo:
                raise ValueError("Repository name is required")
                
            endpoint = f"repos/{username}/{repo}"
            return self.make_request('GET', endpoint)

    def get_all_repos_metadata(self, username=None, per_page=100):
        """Get repositories for a user with pagination handling and optimized caching."""
        username = username or self.username
        endpoint = f"users/{username}/repos"
        params = {'sort': 'updated', 'per_page': per_page}
        
        # Use a specific cache key for the complete repository list
        complete_cache_key = self._generate_cache_key(f"users_{username}_repos_complete", {'per_page': per_page})
        cached_data = self._get_from_cache(complete_cache_key)
        if cached_data is not None:
            logger.info(f"Using cached repository data for {username}")
            return cached_data
        
        # If not cached, fetch all pages
        all_repos = []
        page = 1
        
        while True:
            params['page'] = page
            logger.info(f"Fetching repositories page {page} for {username}")
            
            try:
                repos = self.make_request('GET', endpoint, params=params, cache_ttl=1800)  # 30 min cache per page
                
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
        
        # Cache the complete repository list with longer TTL
        if all_repos:
            self._save_to_cache(complete_cache_key, all_repos, ttl=7200)  # Cache for 2 hours
            
        return all_repos

    def get_file_content(self, username=None, repo=None, path=None):
        """
         Generic method to fetch a specific file's content.
        Returns the raw content as string, or None if not found.
        """
        username = username or self.username
        if not repo:
            raise ValueError("Repository name is required")
        if not path:
            raise ValueError("File path is required")
            
        endpoint = f"repos/{username}/{repo}/contents/{path}"

        try:
            # Single API call to get file/directory metadata (cached for 1 hour)
            file_data = self.make_request('GET', endpoint, cache_ttl=3600)
            
            if not file_data:
                logger.debug(f"File or directory not found: {username}/{repo}/{path}")
                return None

            # Handle single file - return raw content only
            if isinstance(file_data, dict) and file_data.get('type') == 'file':
                return self._decode_file_content(file_data, path, endpoint)
            
            # Handle directory - return dict of container files
            elif isinstance(file_data, list):
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
            logger.error(f"Error fetching file content for {username}/{repo}/{path}: {str(e)}")
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

