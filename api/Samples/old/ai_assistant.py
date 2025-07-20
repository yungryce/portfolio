import logging
import os
from typing import Dict, List, Optional, Tuple
from github_client import GitHubClient
from data_filter import extract_language_terms
from .helpers import extract_context_terms
from .repository_scorer import RepositoryScorer
from .context_builder import ContextBuilder
from .ai_query_processor import AIQueryProcessor
# Use the existing logger from function_app.py
logger = logging.getLogger('portfolio.api')


class AIAssistant:
    """
    Coordinating AI Assistant class for portfolio query processing.
    Orchestrates repository scoring, context building, and AI query processing.
    """
    
    def __init__(self, github_token: str = None, username: str = 'yungryce'):
        """
        Initialize the AI Assistant with GitHub client and specialized components.
        
        Args:
            github_token: GitHub API token for repository access
            username: GitHub username for repository queries
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Initialize GitHub client
        self.gh_client = self._initialize_github_client()
        
        # Initialize specialized components
        self.repository_scorer = RepositoryScorer()
        self.context_builder = ContextBuilder(self.gh_client, self.username)
        self.ai_query_processor = AIQueryProcessor(self.groq_api_key)
        
        logger.info(f"AI Assistant initialized for user: {self.username}")
    
    def _initialize_github_client(self) -> Optional[GitHubClient]:
        """Initialize GitHub client with error handling."""
        if self.github_token:
            return GitHubClient(token=self.github_token, username=self.username)
        else:
            logger.warning("GitHub token not configured - file fetching disabled")
            return None
    
    def process_query(self, query: str, repositories: List[Dict]) -> Tuple[str, Dict]:
        """
        Process a query using the complete AI assistant pipeline.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries with context
            
        Returns:
            Tuple of (AI response, metadata dictionary)
        """
        logger.info(f"Processing query: {query[:100]}...")
        
        # Stage 1: Extract search terms and language terms
        search_terms = extract_context_terms(query, repositories)
        language_terms = extract_language_terms(query)
        search_terms['languages'] = language_terms

        # Log extracted terms for better debugging
        logger.info(f"Extracted terms - Tech: {len(search_terms.get('tech', []))}, " 
                f"Skills: {len(search_terms.get('skills', []))}, "
                f"Languages: {len(language_terms)}")

        RELEVANCE_THRESHOLD = 3.4
        fallback_used = False

        # Check if query has any technical meaning (including skills)
        has_technical_content = bool(
            language_terms or 
            search_terms.get('tech') or 
            search_terms.get('skills') or 
            search_terms.get('components') or 
            search_terms.get('project')
        )

        if not has_technical_content:
            # Stage 2A: Query lacks specificity, use fallback repositories
            logger.info("Query lacks technical specificity, using fallback strategy")
            fallback_used = True
            relevant_repos = self.repository_scorer.get_fallback_repositories(repositories, 5)
        else:
            # Stage 2B: Score and filter repositories
            logger.info("Query has technical content, scoring repositories")
            all_scored_repos = self.repository_scorer.process_repositories_with_scoring(
                repositories, search_terms, limit=10
            )

            # Filter repositories by threshold and use fallback if needed
            relevant_repos = [repo for repo in all_scored_repos if repo.get('total_relevance_score', 0) >= RELEVANCE_THRESHOLD]
            
            if not relevant_repos:
                logger.info(f"No repositories meet the relevance threshold of {RELEVANCE_THRESHOLD}, using fallback")
                fallback_used = True
                relevant_repos = self.repository_scorer.get_fallback_repositories(repositories, 5)
        
        # Log repository scores for the top results
        if logger.isEnabledFor(logging.DEBUG):
            for i, repo in enumerate(relevant_repos[:5]):
                logger.debug(f"Final result {i+1}: {repo.get('name')} - "
                            f"Score: {repo.get('total_relevance_score', 0)}")
        
        logger.info(f"Using {len(relevant_repos)} repositories for context building")

        # Stage 3: Build enhanced context
        enhanced_context = self.context_builder.build_enhanced_context(relevant_repos)
        
        # Stage 4: Process AI query with metadata
        ai_response, metadata = self.ai_query_processor.process_query_with_metadata(
            query, enhanced_context, fallback_used, repositories, relevant_repos, 
            search_terms, language_terms
        )
        
        return ai_response, metadata
    
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
        return {
            "github_client": self.gh_client is not None,
            "repository_scorer": self.repository_scorer is not None,
            "context_builder": self.context_builder is not None,
            "ai_query_processor": self.ai_query_processor.validate_api_configuration(),
            "overall_ready": all([
                self.repository_scorer is not None,
                self.context_builder is not None,
                self.ai_query_processor.validate_api_configuration()
            ])
        }
    
    def get_system_status(self) -> Dict:
        """
        Get comprehensive system status information.
        
        Returns:
            Dictionary with system status details
        """
        return {
            "components": {
                "github_client": "configured" if self.gh_client else "not_configured",
                "repository_scorer": "initialized",
                "context_builder": "initialized",
                "ai_query_processor": self.ai_query_processor.get_api_status()
            },
            "configuration": self.validate_configuration(),
            "username": self.username,
            "github_token_configured": bool(self.github_token)
        }
    
    # Legacy method compatibility (if needed)
    def query_ai_with_context(self, query: str, enhanced_context: str, fallback_used: bool = False) -> str:
        """
        Legacy compatibility method for direct AI querying.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            fallback_used: Whether fallback repositories were used
            
        Returns:
            AI response string
        """
        logger.warning("Using legacy query_ai_with_context method. Consider using process_query instead.")
        return self.ai_query_processor.query_ai_with_context(query, enhanced_context, fallback_used)
    
    def build_enhanced_context(self, repositories: List[Dict], max_chars: int = None) -> str:
        """
        Legacy compatibility method for context building.
        
        Args:
            repositories: List of repository dictionaries
            max_chars: Maximum characters for context
            
        Returns:
            Enhanced context string
        """
        logger.warning("Using legacy build_enhanced_context method. Consider using ContextBuilder directly.")
        return self.context_builder.build_enhanced_context(repositories, max_chars)