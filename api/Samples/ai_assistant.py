import logging
import os
import datetime
from typing import Dict, List, Optional, Any
from ai.type_analyzer import FileTypeAnalyzer
from ai.repo_context_builder import RepoContextBuilder
from ai.ai_assistant import AIContextBuilder
from config.fine_tuning import SemanticModel
from ai.semantic_scorer import SemanticScorer

logger = logging.getLogger('portfolio.api')


class AIAssistant:
    """
    Main AI coordinator for portfolio queries.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    def __init__(self, username: str = None):
        logger.info(f"Initializing AI Assistant for user: {username}")

        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.semantic_model = SemanticModel()
        self.semantic_scorer = SemanticScorer(self.semantic_model)
        self.file_type_analyzer = FileTypeAnalyzer()
        self.ai_context_builder = AIContextBuilder()
        self.context_builder = RepoContextBuilder()

        logger.info(f"AI Assistant initialized for user: {self.username}")

    def calculate_repo_scores(self, repo_bundle: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Calculates and returns the context, language, and type scores for a repository.
        Returns a dict with all scores and intermediate data for metadata consumption.
        """
        repo_context = repo_bundle.get("repoContext", {})
        repo_languages = repo_bundle.get("languages", {})
        file_types = repo_bundle.get("file_types", {})
        categorized = repo_bundle.get("categorized_types", {})
        repo_name = repo_bundle.get("name", "Unknown")

        # Safety checks
        if not isinstance(repo_context, dict):
            repo_context = {}
        if not isinstance(repo_languages, dict):
            repo_languages = {}
        if not isinstance(file_types, dict):
            file_types = {}
        if not isinstance(categorized, dict):
            categorized = {}

        context_score = float(self.semantic_scorer.score_context_similarity(query, repo_bundle))
        language_score = float(self.semantic_scorer.score_language_matches(query, repo_languages))
        type_score = float(self.file_type_analyzer.calculate_type_score(categorized))
        logger.debug(f"Calculated scores for repository '{repo_name}': "
                     f"Context: {context_score}, Language: {language_score}, Type: {type_score}")

        # Aggregate total score
        total_score = float(self.semantic_scorer.aggregate_scores(context_score, language_score, type_score))

        # Prepare metadata
        score_metadata = {
            "context_score": context_score,
            "language_score": language_score,
            "type_score": type_score,
            "total_relevance_score": total_score,
            "scoring_timestamp": datetime.datetime.now().isoformat()
        }
        return score_metadata

    def process_query_results(self, query: str, all_repos_bundle: List[Dict[str, Any]], max_repos: int = 3) -> Dict[str, Any]:
        """
        Consumes repository context results from the orchestrator, scores repositories, builds context, and prepares AI query payload for Groq API.
        """
        try:
            logger.info(f"Processing query: {query[:100]} with orchestrator results...")
            if not all_repos_bundle:
                return {
                    "response": f"No repositories found for {self.username}.",
                    "repositories_used": [],
                    "total_repositories": 0,
                    "query": query
                }

            # Ensure fine-tuned model is ready (handles cache check, loading, and training)
            model_ready = self.semantic_model.ensure_model_ready(all_repos_bundle)
            if not model_ready:
                logger.warning("Model preparation failed, but continuing with base model")
          
            # Score repositories - use all repositories for scoring even if they lack documentation
            scored_repos = []
            documented_repos = [repo for repo in all_repos_bundle if repo.get("has_documentation", False)]
            for repo_bundle in documented_repos:
                try:
                    score_metadata = self.calculate_repo_scores(repo_bundle, query)
                    repo_bundle.update(score_metadata)
                    scored_repos.append(repo_bundle)
                except Exception as e:
                    logger.error(f"Error scoring repository {repo_bundle.get('name', 'Unknown')}: {str(e)}")
                    continue
                
            scored_repos.sort(key=lambda r: r.get("context_score", 0), reverse=True)
            logger.debug(f"scored repos---{[repo.get('name', 'Unknown') for repo in scored_repos]}---")
            top_repos = scored_repos[:max_repos]
            context = self.ai_context_builder.build_tiered_context(top_repos, max_repos=max_repos)
            system_message = self.ai_context_builder.build_rules_context(context)
            # logger.debug(f"Built system message for AI: {system_message[:500]}...")
            
            response = {
                "response": f"Top repositories for '{query}': {[r['name'] for r in top_repos]}",
                "tiered_context": context,
                "system_message": system_message,
                "repositories_used": [
                    {
                        "name": repo.get('name'),
                        "context_score": repo.get('context_score', 0)
                    }
                    for repo in top_repos
                ],
                "total_repositories": len(all_repos_bundle),
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


