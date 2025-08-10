from .github_api import GitHubAPI
from .cache_manager import cache_manager

class GitHubFileManager:
    def __init__(self, api: GitHubAPI):
        self.api = api

    @cache_manager.cache_decorator(cache_key_func=lambda username, repo, path: f"file_content:{username}:{repo}:{path}", ttl=3600)
    def get_file_content(self, username=None, repo=None, path=None):
        username = username or self.api.username
        if not repo:
            raise ValueError("Repository name is required")
        path_segment = path if path else ""
        endpoint = f"repos/{username}/{repo}/contents/{path_segment}"
        file_data = self.api.make_request('GET', endpoint)
        if isinstance(file_data, dict) and file_data.get('type') == 'file':
            return self.api.decode_file_content(file_data)
        return file_data

    @cache_manager.cache_decorator(cache_key_func=lambda username, repo, path: f"directory_list:{username}:{repo}:{path}", ttl=3600)
    def list_directory(self, username=None, repo=None, path=""):
        """
        List files and directories at the given path (metadata only, no content).
        """
        username = username or self.api.username
        if not repo:
            raise ValueError("Repository name is required")
        path_segment = path if path else ""
        endpoint = f"repos/{username}/{repo}/contents/{path_segment}"
        file_data = self.api.make_request('GET', endpoint)
        return file_data if isinstance(file_data, list) else []