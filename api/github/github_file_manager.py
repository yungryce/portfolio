from .github_api import GitHubAPI
from .cache_client import GitHubCache

class GitHubFileManager:
    def __init__(self, api: GitHubAPI, cache: GitHubCache):
        self.api = api
        self.cache = cache

    def get_file_content(self, username=None, repo=None, path=None):
        username = username or self.api.username
        if not repo:
            raise ValueError("Repository name is required")
        path_segment = path if path else ""
        endpoint = f"repos/{username}/{repo}/contents/{path_segment}"
        cache_key = self.cache._generate_cache_key(endpoint)
        cached = self.cache._get_from_cache(cache_key)
        if cached is not None:
            return cached
        file_data = self.api.make_request('GET', endpoint)
        if not file_data:
            return None
        if isinstance(file_data, dict) and file_data.get('type') == 'file':
            content = self.api.decode_file_content(file_data)
            self.cache._save_to_cache(cache_key, content)
            return content
        elif isinstance(file_data, list):
            self.cache._save_to_cache(cache_key, file_data)
            return file_data
        return None

    def get_container_files(self, username=None, repo=None, container_path=""):
        return self.get_file_content(username, repo, container_path or "")
