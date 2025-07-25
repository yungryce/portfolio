import logging
import os
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Optional, Any
from ai.semantic_scorer import SemanticScorer
from ai.type_analyzer import FileTypeAnalyzer
from ai.repo_context_builder import RepoContextBuilder
from data_filter import extract_language_terms
from .helpers import extract_context_terms

logger = logging.getLogger('portfolio.api')


class AIAssistant:
    """
    Main AI coordinator for portfolio queries.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    def __init__(self, username: str = 'yungryce', repo_manager=None):
        logger.info(f"Initializing AI Assistant for user: {username}")
        self.username = username
        self.repo_manager = repo_manager
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.semantic_scorer = SemanticScorer()
        self.file_type_analyzer = FileTypeAnalyzer()
        self.context_builder = RepoContextBuilder(repo_manager=repo_manager, username=username)
        # Repo manager setup if not provided
        if not self.repo_manager:
            from github.github_api import GitHubAPI
            from github.cache_client import GitHubCache
            from github.github_file_manager import GitHubFileManager
            from github.github_repo_manager import GitHubRepoManager
            github_token = os.getenv('GITHUB_TOKEN')
            api = GitHubAPI(token=github_token, username=username)
            cache = GitHubCache(use_cache=True)
            file_manager = GitHubFileManager(api, cache)
            self.repo_manager = GitHubRepoManager(api, cache, file_manager)
        logger.info(f"AI Assistant initialized for user: {self.username}")

    def get_all_file_types(self, repo_name: str) -> Dict[str, int]:
        """
        Recursively retrieve all file types/extensions in a repository.
        """
        file_types = {}
        files = self.repo_manager.get_repository_tree(self.username, repo_name, recursive=True)
        for file_path in files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext:
                file_types[ext] = file_types.get(ext, 0) + 1
        # logger.debug(f"File types for {repo_name}: {file_types}")
        return file_types
    
    def calculate_repo_scores(self, repo: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Calculates and returns the context, language, and type scores for a repository.
        Returns a dict with all scores and intermediate data for metadata consumption.
        """
        repo_context = repo.get("repoContext", {})
        repo_languages = repo.get("languages", {})
        repo_name = repo.get("name", "Unknown")

        # Safety checks
        if not isinstance(repo_context, dict):
            repo_context = {}
        if not isinstance(repo_languages, dict):
            repo_languages = {}

        context_score = self.semantic_scorer.score_context_similarity(query, repo_context)
        language_score = self.semantic_scorer.score_language_matches(query, repo_languages)
        file_types = self.get_all_file_types(repo_name)
        categorized = self.file_type_analyzer.analyze_repository_files(file_types)
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

    def process_query(self, query: str, max_repos: int = 3) -> Dict[str, Any]:
        try:
            logger.info(f"Processing query: {query[:100]}...")
            repositories = self.repo_manager.get_all_repos_with_context(
                username=self.username, 
                include_languages=True
            )
            if not repositories:
                return {
                    "response": f"No repositories found for {self.username}.",
                    "repositories_used": [],
                    "total_repositories": 0,
                    "query": query
                }
            scored_repos = []
            for repo in repositories:
                # Calculate all scores and get metadata
                score_metadata = self.calculate_repo_scores(repo, query)
                # Attach all score metadata to repo for downstream consumption
                repo.update(score_metadata)
                scored_repos.append(repo)
                
            scored_repos.sort(key=lambda r: r.get("total_relevance_score", 0), reverse=True)
            top_repos = scored_repos[:max_repos]
            for repo in top_repos:
                logger.debug(
                    f"{repo.get('name', 'Unknown')}: "
                    f"Total: {repo.get('total_relevance_score', 0)}: "
                    f"Semantic: {repo.get('context_score', 0)}: "
                    f"Lang: {repo.get('language_score', 0)} -: "
                    f"Types: {repo.get('type_score', 0)}-{repo.get('categorized_types', {})}"
                )
            context = self.context_builder.build_tiered_context(top_repos, max_repos=max_repos)
            logger.debug(f"Built context for top repositories: {context['primary_repo']}")
            ai_response = f"Top repositories for '{query}': {[r['name'] for r in top_repos]}"
            response = {
                "response": ai_response,
                "repositories_used": [
                    {
                        "name": repo.get('name'),
                        "relevance_score": repo.get('total_relevance_score', 0),
                        "languages": list(repo.get('languages', {}).keys()),
                        "categorized_types": repo.get("categorized_types", {}),
                        "score_metadata": {
                            "context_score": repo.get("context_score", 0),
                            "language_score": repo.get("language_score", 0),
                            "type_score": repo.get("type_score", 0)
                        }
                    }
                    for repo in top_repos
                ],
                "total_repositories": len(repositories),
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