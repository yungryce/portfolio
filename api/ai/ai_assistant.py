import logging
import os
import datetime
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional, Any
from ai.semantic_scorer import SemanticScorer
from ai.type_analyzer import FileTypeAnalyzer
from ai.repo_context_builder import RepoContextBuilder
from ai.ai_context_builder import AIContextBuilder
from model.fine_tuning import SemanticModel
from github.cache_client import GitHubCache

logger = logging.getLogger('portfolio.api')


class AIAssistant:
    """
    Main AI coordinator for portfolio queries.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    def __init__(self, username: str = 'yungryce', 
                base_model_path: str = 'sentence-transformers/all-MiniLM-L6-v2',
                fine_tuned_model_path: str = '/tmp/fine_tuned_model'):
        logger.info(f"Initializing AI Assistant for user: {username}")
        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.semantic_scorer = SemanticScorer(base_model_path)
        self.semantic_model = SemanticModel(base_model_path)
        self.fine_tuned_model_path = fine_tuned_model_path
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
                
            documented_repos = [repo for repo in repo_context_results if repo.get("has_documentation", False)]
            skipped_count = len(repo_context_results) - len(documented_repos)
            if skipped_count > 0:
                logger.info(f"Skipped {skipped_count} repositories without sufficient documentation")
            if not documented_repos:
                logger.warning(f"No repositories with sufficient documentation found for {self.username}")
                return {
                    "response": f"No repositories with sufficient documentation found for {self.username}.",
                    "repositories_used": [],
                    "total_repositories": len(repo_context_results),
                    "undocumented_count": skipped_count,
                    "query": query
                }
            
            cache_key = "fine_tuned_model"
            cache_result = self.cache_client._get_from_cache(cache_key)
            
            if cache_result['status'] == 'valid':
                # We have a valid model reference in cache - load it from storage
                logger.info("Found valid fine-tuned model in cache. Loading from storage...")
                model_info = cache_result['data']
                
                # Load the model from storage
                load_success = self.semantic_model.load_model_from_storage(model_info)
                
                if load_success:
                    logger.info(f"Successfully loaded fine-tuned model from storage: {model_info.get('blob_name')}")
                else:
                    logger.warning("Failed to load model from storage. Will use base model for scoring.")
        
            elif cache_result['status'] != 'valid':
                logger.info("Fine-tuned model not found in cache. Running fine-tuning process...")
                logger.info(f"Fine-tuning context {len(repo_context_results)} of types: {', '.join(set(repo.get('type', 'Unknown') for repo in repo_context_results))}")

                # Train model using the documented repositories
                model_path = f"fine_tuned_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                success = self.semantic_model.train_from_repositories(
                    documented_repos, 
                    model_path # This is now used as an identifier, not just a file path
                )
                
                # Save model metadata to cache if training was successful
                if success:
                    model_info = {
                        "model_path": model_path,
                        "storage_type": "blob",
                        "container": "ai-models",
                        "blob_name": f"{model_path}.zip",
                        "training_timestamp": datetime.now().isoformat(),
                        "training_repos_count": len(documented_repos)
                    }
                    
                    self.cache_client._save_to_cache(
                        cache_key, 
                        model_info,
                        ttl=86400 * 7  # Cache for 7 days since models are now durable
                    )
                    logger.info("Fine-tuned model reference saved to cache.")
                
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


