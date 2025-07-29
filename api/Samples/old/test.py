import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def process_query_results(self, query: str, repo_context_results: List[Dict[str, Any]], max_repos: int = 3) -> Dict[str, Any]:
    """
    Consumes repository context results from the orchestrator, scores repositories, builds context, and prepares AI query payload for Groq API.
    """
    try:
        logger.info(f"Processing query: {query[:100]} with orchestrator results...")
        if not repo_context_results:
            return {
                "response": f"No repositories found for {self.username}.",
                "repositories_used": [],
                "total_repositories": 0,
                "query": query
            }
        scored_repos = []
        for repo in repo_context_results:
            score_metadata = self.calculate_repo_scores(repo, query)
            repo.update(score_metadata)
            scored_repos.append(repo)
        scored_repos.sort(key=lambda r: r.get("total_relevance_score", 0), reverse=True)
        top_repos = scored_repos[:max_repos]
        context = self.context_builder.build_tiered_context(top_repos, max_repos=max_repos)
        system_message = self.context_builder.build_rules_context(context)
        logger.debug(f"Built system message for AI: {system_message[:500]}...")
        response = {
            "response": f"Top repositories for '{query}': {[r['name'] for r in top_repos]}",
            "tiered_context": context,
            "system_message": system_message,
            "repositories_used": [
                {
                    "name": repo.get('name'),
                    "relevance_score": repo.get('total_relevance_score', 0)
                }
                for repo in top_repos
            ],
            "total_repositories": len(repo_context_results),
            "query": query
        }
        logger.info(f"Successfully processed query using {len(top_repos)} repositories")
        return response
    except Exception as e:
        logger.error(f"Error in AI processing pipeline: {str(e)}", exc_info=True)
        return {
            "response": f"Error: {str(e)}",
            "repositories_used": [],
            "total_repositories": 0,
            "query": query,
            "error": str(e)
        }