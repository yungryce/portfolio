from typing import Dict, Any, List
import logging
import os

logger = logging.getLogger('portfolio.api')

class RepoContextBuilder:
    """
    Builds graduated AI context for top repositories.
    """
    def __init__(self):
        pass

    def build_tiered_context(self, top_repos: List[Dict], max_repos: int = 3) -> Dict[str, Any]:
        """
        Builds a context dict for the top repositories using pre-fetched content from repo bundles.
        Returns structured context suitable for AI context building with tiered importance.
        
        Args:
            top_repos: List of repository bundles with pre-fetched content and scoring
            max_repos: Maximum number of repositories to include in context
        
        Returns:
            Dictionary with primary_repo, secondary_repo, and tertiary_repo context
        """
        context = {}
        for i, repo in enumerate(top_repos[:max_repos]):
            repo_name = repo.get("name")
            
            # Extract pre-fetched content directly from repo bundle
            readme = repo.get("readme", "")
            skills_index = repo.get("skills_index", "")
            architecture = repo.get("architecture", "")
            
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

