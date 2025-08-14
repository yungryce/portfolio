from github.github_api import GitHubAPI
from Samples.cache_client import GitHubCache
from github.github_repo_manager import GitHubRepoManager
from typing import Dict, Any, List
import logging
import os

logger = logging.getLogger('portfolio.api')

class RepoContextBuilder:
    """
    Builds graduated AI context for top repositories.
    """
    def __init__(self, username):
        github_token = os.getenv('GITHUB_TOKEN')
        api = GitHubAPI(token=github_token, username=username)
        cache = GitHubCache(use_cache=True)
        self.repo_manager = GitHubRepoManager(api, cache, username=username)
        self.username = username

    def build_tiered_context(self, top_repos: List[Dict], max_repos: int = 3) -> Dict[str, Any]:
        """
        Builds a context dict for the top repositories, retrieving README.md, SKILLS-INDEX.md,
        and ARCHITECTURE.md using the repo_manager for each repo. Returns all retrieved files,
        processed repo_context (with scoring metadata), and is suitable for AI context building.
        """
        context = {}
        for i, repo in enumerate(top_repos[:max_repos]):
            repo_name = repo.get("name")
            # Retrieve files using repo_manager
            readme = self.repo_manager.get_file_content(repo_name, "README.md") or ""
            skills_index = self.repo_manager.get_file_content(repo_name, "SKILLS-INDEX.md") or ""
            architecture = self.repo_manager.get_file_content(repo_name, "ARCHITECTURE.md") or ""
            # Compose context for each repo
            repo_context = {
                "name": repo_name,
                "readme": readme,
                "skills_index": skills_index,
                "architecture": architecture,
                "context": repo.get("repoContext", {}),
                "score_metadata": {
                    "context_score": repo.get("context_score", 0),
                    "language_score": repo.get("language_score", 0),
                    "type_score": repo.get("type_score", 0),
                    "total_relevance_score": repo.get("total_relevance_score", 0),
                    "categorized_types": repo.get("categorized_types", {}),
                    "file_types": repo.get("file_types", {})
                }
            }
            # Assign to tiered context
            if i == 0:
                context['primary_repo'] = repo_context
            elif i == 1:
                context['secondary_repo'] = repo_context
            elif i == 2:
                context['tertiary_repo'] = repo_context
        return context

    def _build_summary_context(self, repo: Dict) -> Dict:
        return {
            "name": repo.get("name"),
            "summary": repo.get("readme", "")[:200]
        }

    def _build_mention_context(self, repo: Dict) -> Dict:
        return {"name": repo.get("name")}
    
   