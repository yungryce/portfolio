import logging
from typing import Dict, List, Any
from ai.type_analyzer import FileTypeAnalyzer
from ai.semantic_scorer import SemanticScorer
from config.fine_tuning import SemanticModel
import datetime

logger = logging.getLogger('portfolio.api')

class RepoScoringService:
    """
    Service for scoring repositories against queries with different algorithms.
    Decoupled from AI processing to allow reuse in different contexts.
    """
    
    def __init__(self, username: str = None):
        """Initialize the repository scoring service with required components."""
        self.semantic_model = SemanticModel()
        self.semantic_scorer = SemanticScorer(self.semantic_model)
        self.file_type_analyzer = FileTypeAnalyzer()
        self.username = username
        
    def score_repositories(self, query: str, repositories: List[Dict]) -> List[Dict]:
        """
        Score all repositories against the query and return a list of scored repositories.
        This doesn't modify the original repositories.
        
        Args:
            query: The user query to score repositories against
            repositories: List of repository bundles
            
        Returns:
            List of repositories with scores added
        """
        logger.info(f"Scoring {len(repositories)} repositories against query: {query[:50]}...")
        
        # Load model without training (training happens in background activity)
        self.semantic_model.ensure_model_ready(repositories, train_if_missing=False)
        
        scored_repos = []
        for repo in repositories:
            try:
                # Calculate scores
                scored_repo = repo.copy()  # Don't modify original data
                scores = self.calculate_repository_score(scored_repo, query)
                
                # Add scores to repository
                scored_repo.update(scores)
                scored_repos.append(scored_repo)
                
            except Exception as e:
                repo_name = repo.get("name", "Unknown")
                logger.error(f"Error scoring repository '{repo_name}': {str(e)}", exc_info=True)
                # Add to list anyway with zero scores to maintain repo count
                repo_copy = repo.copy()
                repo_copy.update({
                    "context_score": 0.0,
                    "language_score": 0.0,
                    "type_score": 0.0,
                    "total_relevance_score": 0.0,
                    "error": str(e)
                })
                scored_repos.append(repo_copy)
                
        # Sort by total relevance score
        scored_repos.sort(key=lambda r: r.get("total_relevance_score", 0), reverse=True)
        
        return scored_repos
        
    def calculate_repository_score(self, repo_bundle: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Calculate the relevance scores for a single repository.
        
        Args:
            repo_bundle: Repository bundle with metadata and content
            query: The user query to score against
            
        Returns:
            Dictionary with all score components
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

        # Calculate individual scores
        context_score = float(self.semantic_scorer.score_context_similarity(query, repo_bundle))
        language_score = float(self.semantic_scorer.score_language_matches(query, repo_languages))
        type_score = float(self.file_type_analyzer.calculate_type_score(categorized))
        
        logger.debug(f"Calculated scores for repository '{repo_name}': "
                    f"Context: {context_score}, Language: {language_score}, Type: {type_score}")

        # Aggregate total score
        total_score = float(self.semantic_scorer.aggregate_scores(context_score, language_score, type_score))

        # Return score components and metadata
        return {
            "context_score": context_score,
            "language_score": language_score,
            "type_score": type_score,
            "total_relevance_score": total_score,
            "scoring_timestamp": datetime.datetime.now().isoformat()
        }