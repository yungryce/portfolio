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



    def _build_summary_context(self, repo: Dict) -> Dict:
        return {
            "name": repo.get("name"),
            "summary": repo.get("readme", "")[:200]
        }

    def _build_mention_context(self, repo: Dict) -> Dict:
        return {"name": repo.get("name")}

