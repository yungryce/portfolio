import logging
import os
from typing import Dict, List, Optional, Any
from ..Private.new.repository_scorer import RepositoryScorer
from ..Private.new.context_builder import ContextBuilder
from ..Private.new.ai_query_processor import AIQueryProcessor
from data_filter import extract_language_terms
from .helpers import extract_context_terms
from data_filter import extract_language_terms

logger = logging.getLogger('portfolio.api')

class AIAssistant:
    """
    Main AI coordinator for portfolio queries.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    
    def __init__(self, username: str = 'yungryce', repo_manager=None):
        """
        Initialize the AI Assistant with repository manager and specialized components.
        
        Args:
            username: GitHub username for repository queries
            repo_manager: GitHub repository manager for data access
        """
        logger.info(f"Initializing AI Assistant for user: {username}")
        self.username = username
        self.repo_manager = repo_manager
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Initialize specialized components
        self.repository_scorer = RepositoryScorer()
        self.context_builder = ContextBuilder(repo_manager=repo_manager, username=username)
        self.ai_query_processor = AIQueryProcessor(self.groq_api_key)
        
        # Initialize GitHub components if not provided
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

    def process_query(self, query: str, max_repos: int = 5) -> Dict[str, Any]:
        """
        Process a portfolio query through the AI pipeline.
        
        Args:
            query: The user's question
            max_repos: Maximum number of repositories to include in context
            
        Returns:
            Dict containing the AI response and metadata
        """
        try:
            logger.info(f"Processing query: {query[:100]}...")
            
            # Step 1: Get all repositories with context
            repositories = self.repo_manager.get_all_repos_with_context(
                username=self.username, 
                include_languages=True
            )
            
            if not repositories:
                return {
                    "response": f"I don't have access to any repositories for {self.username}. Please check the GitHub token and permissions.",
                    "repositories_used": [],
                    "total_repositories": 0,
                    "query": query
                }
            
            # Step 2: Extract search terms from the query
            context_terms = extract_context_terms(query, repositories)
            language_terms = extract_language_terms(query)
            search_terms = {
                'context_terms': context_terms,
                'language_terms': language_terms
            }
            
            logger.info(f"Extracted search terms: {search_terms}")
            
            # Step 3: Score and rank repositories
            scored_repos = self.repository_scorer.score_repositories(repositories, search_terms)
            
            # Step 4: Select top repositories using fallback logic
            RELEVANCE_THRESHOLD = 3.4
            fallback_used = False
            
            # Check if query has any technical meaning
            has_technical_content = bool(
                language_terms or 
                context_terms.get('tech') or 
                context_terms.get('skills') or 
                context_terms.get('components') or 
                context_terms.get('project')
            )
            
            if not has_technical_content:
                logger.info("Query lacks technical specificity, using fallback strategy")
                fallback_used = True
                top_repos = self.repository_scorer.get_fallback_repositories(repositories, max_repos)
            else:
                # Filter repositories by threshold
                relevant_repos = [repo for repo in scored_repos if repo.get('total_relevance_score', 0) >= RELEVANCE_THRESHOLD]
                
                if not relevant_repos:
                    logger.info(f"No repositories meet the relevance threshold of {RELEVANCE_THRESHOLD}, using fallback")
                    fallback_used = True
                    top_repos = self.repository_scorer.get_fallback_repositories(repositories, max_repos)
                else:
                    top_repos = relevant_repos[:max_repos]
            
            logger.info(f"Selected top {len(top_repos)} repositories for context")
            
            # Step 5: Build context from top repositories
            context = self.context_builder.build_enhanced_context(top_repos)
            
            # Step 6: Process query with AI
            ai_response = self.ai_query_processor.query_ai_with_context(context, query, fallback_used)
            
            # Prepare response
            response = {
                "response": ai_response,
                "repositories_used": [
                    {
                        "name": repo.get('name'),
                        "relevance_score": repo.get('total_relevance_score', 0),
                        "languages": list(repo.get('languages', {}).keys())
                    }
                    for repo in top_repos
                ],
                "total_repositories": len(repositories),
                "search_terms": search_terms,
                "fallback_used": fallback_used,
                "query": query
            }
            
            logger.info(f"Successfully processed query using {len(top_repos)} repositories")
            return response
            
        except Exception as e:
            logger.error(f"Error in AI processing pipeline: {str(e)}", exc_info=True)
            return {
                "response": f"I encountered an error while processing your query: {str(e)}",
                "repositories_used": [],
                "total_repositories": 0,
                "query": query,
                "error": str(e)
            }

    def calculate_difficulty_score(self, repo: Dict) -> Dict:
        """
        Calculate difficulty score for a repository using the repository scorer.
        
        Args:
            repo: Repository dictionary
            
        Returns:
            Dictionary with difficulty analysis
        """
        return self.repository_scorer.calculate_difficulty_score(repo)

    def get_difficulty_score(self, repo: Dict) -> Dict:
        """
        Get difficulty score with caching using the repository scorer.
        
        Args:
            repo: Repository dictionary
            
        Returns:
            Dictionary with difficulty analysis
        """
        return self.repository_scorer.get_difficulty_score(repo)

    def validate_configuration(self) -> Dict[str, bool]:
        """
        Validate the configuration of all components.
        
        Returns:
            Dictionary with validation results for each component
        """
        results = {
            'github_token': bool(os.getenv('GITHUB_TOKEN')),
            'groq_api_key': bool(self.groq_api_key),
            'repo_manager': bool(self.repo_manager),
            'repository_scorer': bool(self.repository_scorer),
            'context_builder': bool(self.context_builder),
            'ai_query_processor': bool(self.ai_query_processor)
        }
        
        logger.info(f"Configuration validation: {results}")
        return results

    def get_system_status(self) -> Dict:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with system status information
        """
        status = {
            'configuration': self.validate_configuration(),
            'ai_api_status': self.ai_query_processor.get_api_status() if self.ai_query_processor else None,
            'username': self.username,
            'initialized': True
        }
        
        logger.info(f"System status: {status}")
        return status
