import logging
import os
import datetime
from typing import Dict, List, Optional, Any
from ai.type_analyzer import FileTypeAnalyzer
from ai.repo_context_builder import RepoContextBuilder
from ai.ai_context_builder import AIContextBuilder
from model.fine_tuning import SemanticModel
from ai.semantic_scorer import SemanticScorer
from github.cache_client import GitHubCache

logger = logging.getLogger('portfolio.api')


class AIAssistant:
    """
    Main AI coordinator for portfolio queries.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    def __init__(self, username: str = 'yungryce'):
        logger.info(f"Initializing AI Assistant for user: {username}")
        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.semantic_model = SemanticModel()
        self.semantic_scorer = SemanticScorer(self.semantic_model)
        self.file_type_analyzer = FileTypeAnalyzer()
        self.ai_context_builder = AIContextBuilder()
        self.context_builder = RepoContextBuilder(username=username)
        self.cache_client = GitHubCache(use_cache=True)

        logger.info(f"AI Assistant initialized for user: {self.username}")
    
    def calculate_repo_scores(self, repo: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Calculates and returns the context, language, and type scores for a repository.
        Returns a dict with all scores and intermediate data for metadata consumption.
        """
        repo_context = repo.get("repoContext", {})
        repo_languages = repo.get("languages", {})
        file_types = repo.get("file_types", {})
        categorized = repo.get("categorized_types", {})
        repo_name = repo.get("name", "Unknown")

        # Safety checks
        if not isinstance(repo_context, dict):
            repo_context = {}
        if not isinstance(repo_languages, dict):
            repo_languages = {}
        if not isinstance(file_types, dict):
            file_types = {}
        if not isinstance(categorized, dict):
            categorized = {}

        context_score = self.semantic_scorer.score_context_similarity(query, repo_context)
        language_score = self.semantic_scorer.score_language_matches(query, repo_languages)
        type_score = self.file_type_analyzer.calculate_type_score(categorized)

        # Aggregate total score
        total_score = self.semantic_scorer.aggregate_scores(context_score, language_score, type_score)

        # Prepare metadata
        score_metadata = {
            "context_score": context_score,
            "language_score": language_score,
            "type_score": type_score,
            "total_relevance_score": total_score,
            "file_types": file_types,
            "categorized_types": categorized
        }
        return score_metadata

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

            # Ensure fine-tuned model is ready (handles cache check, loading, and training)
            model_ready = self.semantic_model.ensure_model_ready(repo_context_results)
            if not model_ready:
                logger.warning("Model preparation failed, but continuing with base model")
          
            # Score repositories - use all repositories for scoring even if they lack documentation
            scored_repos = []
            for repo in repo_context_results:
                try:
                    score_metadata = self.calculate_repo_scores(repo, query)
                    repo.update(score_metadata)
                    scored_repos.append(repo)
                except Exception as e:
                    logger.error(f"Error scoring repository {repo.get('name', 'Unknown')}: {str(e)}")
                    continue
                
            scored_repos.sort(key=lambda r: r.get("total_relevance_score", 0), reverse=True)
            top_repos = scored_repos[:max_repos]
            context = self.context_builder.build_tiered_context(top_repos, max_repos=max_repos)
            system_message = self.ai_context_builder.build_rules_context(context)
            # logger.debug(f"Built system message for AI: {system_message[:500]}...")
            
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


