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
                repo_context = repo.get("repoContext", {})
                repo_languages = repo.get("languages", {})
                context_score = self.semantic_scorer.score_context_similarity(query, repo_context)
                language_score = self.semantic_scorer.score_language_matches(query, repo_languages)
                logger.debug(f"------ {repo.get('name', 'Unknown')}: {context_score}: {language_score}")
                file_types = self.get_all_file_types(repo.get("name"))
                categorized = self.file_type_analyzer.analyze_repository_files(file_types)
                logger.debug(f"****** {repo.get('name', 'Unknown')}: {categorized}: {file_types}")
                type_score = self.file_type_analyzer.calculate_type_score(categorized)
                total_score = self.semantic_scorer.aggregate_scores(context_score, language_score) + type_score
                repo["total_relevance_score"] = total_score
                repo["file_types"] = file_types
                repo["categorized_types"] = categorized
                scored_repos.append(repo)
            scored_repos.sort(key=lambda r: r.get("total_relevance_score", 0), reverse=True)
            top_repos = scored_repos[:max_repos]
            context = self.context_builder.build_tiered_context(top_repos, max_repos=max_repos)
            ai_response = f"Top repositories for '{query}': {[r['name'] for r in top_repos]}"
            response = {
                "response": ai_response,
                "repositories_used": [
                    {
                        "name": repo.get('name'),
                        "relevance_score": repo.get('total_relevance_score', 0),
                        "languages": list(repo.get('languages', {}).keys()),
                        "categorized_types": repo.get("categorized_types", {})
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