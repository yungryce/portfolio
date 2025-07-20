import logging
import math
from typing import Any, Dict, List, Tuple, Type, TypeVar
from ...ai.helpers import (
    # Language processing
    calculate_language_score, get_language_matches, process_language_data,
    
    # Search and scoring
    extract_repo_data, extract_context_terms, calculate_tech_score, calculate_skill_score,
    calculate_component_score, calculate_project_score, calculate_general_score,
    calculate_bonus_score
)
from data_filter import  extract_language_terms

logger = logging.getLogger('portfolio.api')
T = TypeVar('T')

class RepositoryScorer:
    """
    Handles repository scoring, relevance calculation, and difficulty assessment.
    Responsible for ranking repositories based on search terms and calculating difficulty scores.
    """
    
    def __init__(self):
        """Initialize the RepositoryScorer."""
        logger.info("RepositoryScorer initialized")
    
    def score_repositories(self, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Score and rank repositories based on search terms.
        
        Args:
            repositories: List of repository dictionaries
            search_terms: Dictionary containing search terms including languages
            
        Returns:
            List of repositories sorted by relevance score
        """
        logger.info(f"Scoring {len(repositories)} repositories")
        
        scored_repos = []
        language_terms = search_terms.get('language_terms', [])
        context_terms = search_terms.get('context_terms', {})
        
        for repo in repositories:
            try:
                # Process language data
                repo = process_language_data(repo)
                
                # Calculate individual scores
                repo_context = extract_repo_data(repo, 'repoContext', {})
                
                # Language scoring
                language_score = calculate_language_score(
                    repo.get('languages', {}),
                    language_terms,
                    repo.get('total_language_bytes', 0)
                )
                
                # Context-based scoring
                tech_score = calculate_tech_score(
                    repo_context.get('tech_stack', {}),
                    context_terms
                )
                
                skill_score = calculate_skill_score(
                    repo_context.get('skill_manifest', {}),
                    context_terms
                )
                
                component_score = calculate_component_score(
                    repo_context.get('components', {}),
                    context_terms
                )
                
                project_score = calculate_project_score(
                    repo_context.get('project_identity', {}),
                    context_terms
                )
                
                general_score = calculate_general_score(repo, context_terms)
                bonus_score = calculate_bonus_score(repo, context_terms)
                
                # Store individual scores
                repo['relevance_scores'] = {
                    'language': language_score,
                    'tech': tech_score,
                    'skill': skill_score,
                    'component': component_score,
                    'project': project_score,
                    'general': general_score,
                    'bonus': bonus_score
                }
                
                # Calculate total score
                total_score = (
                    language_score + tech_score + skill_score + 
                    component_score + project_score + general_score + bonus_score
                )
                
                repo['total_relevance_score'] = total_score
                repo['language_relevance_score'] = language_score
                
                scored_repos.append(repo)
                
            except Exception as e:
                logger.error(f"Error scoring repository {repo.get('name', 'unknown')}: {str(e)}")
                # Add repo with zero score to maintain list completeness
                repo['total_relevance_score'] = 0.0
                repo['language_relevance_score'] = 0.0
                repo['relevance_scores'] = {}
                scored_repos.append(repo)
        
        # Sort by total relevance score
        scored_repos.sort(key=lambda x: x.get('total_relevance_score', 0), reverse=True)
        
        # Log results
        self._log_scoring_results(scored_repos, language_terms)
        
        return scored_repos
    
    def process_repositories_with_scoring(self, repositories: List[Dict], search_terms: Dict, limit: int = 10) -> List[Dict]:
        """
        Process repositories with language data and return top matches by relevance.
        
        Args:
            repositories: List of repository dictionaries
            search_terms: Dictionary containing search terms including languages
            limit: Maximum number of repositories to return
            
        Returns:
            List of top repositories with AI-specific enhancements sorted by relevance
        """
        processed_repos = []
        language_terms = search_terms.get('languages', [])

        for repo in repositories:
            try:
                # Process language data
                processed_repo = process_language_data(repo.copy())
                
                # Calculate all relevance scores
                relevance_scores = self._calculate_all_scores(processed_repo, search_terms)
                processed_repo.update(relevance_scores)
                
                # Add language matches for enhanced context
                language_matches = get_language_matches(
                    processed_repo.get('languages', {}),
                    language_terms,
                    processed_repo.get('relevance_scores', {})
                )
                processed_repo['language_matches'] = language_matches
                
                processed_repos.append(processed_repo)
                
            except Exception as e:
                logger.error(f"Error processing repository {repo.get('name', 'unknown')}: {str(e)}")
                # Add repo with minimal scoring to maintain list completeness
                processed_repo = repo.copy()
                processed_repo['total_relevance_score'] = 0.0
                processed_repo['language_relevance_score'] = 0.0
                processed_repo['relevance_scores'] = {}
                processed_repo['language_matches'] = []
                processed_repos.append(processed_repo)
        
        # Sort by total relevance score and apply limit
        processed_repos.sort(key=lambda x: x.get('total_relevance_score', 0), reverse=True)
        limited_repos = processed_repos[:limit]
        
        # Log results
        self._log_processing_results(limited_repos, len(processed_repos), language_terms)
        
        return limited_repos

    def get_fallback_repositories(self, repositories: List[Dict], limit: int = 5) -> List[Dict]:
        """
        Get fallback repositories when no specific matches are found.
        
        Args:
            repositories: List of all repositories
            limit: Maximum number of repositories to return
            
        Returns:
            List of fallback repositories
        """
        logger.info(f"Using fallback repository selection (limit: {limit})")
        
        # Sort by a combination of factors: recent activity, stars, size
        fallback_repos = []
        
        for repo in repositories:
            try:
                # Calculate fallback score
                fallback_score = 0.0
                
                # Recent activity bonus
                updated_at = repo.get('updated_at', '')
                if updated_at:
                    try:
                        from datetime import datetime
                        updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        now = datetime.now().replace(tzinfo=updated_date.tzinfo)
                        days_since_update = (now - updated_date).days
                        
                        if days_since_update < 30:
                            fallback_score += 10.0
                        elif days_since_update < 90:
                            fallback_score += 5.0
                        elif days_since_update < 365:
                            fallback_score += 2.0
                    except:
                        pass
                
                # Popularity bonus
                stars = repo.get('stargazers_count', 0)
                fallback_score += min(stars * 0.5, 10.0)
                
                # Size bonus (not too small, not too large)
                size = repo.get('size', 0)
                if 100 <= size <= 50000:
                    fallback_score += 3.0
                elif size > 50:
                    fallback_score += 1.0
                
                # Documentation bonus
                if repo.get('has_readme'):
                    fallback_score += 2.0
                
                # Language diversity bonus
                languages = repo.get('languages', {})
                if len(languages) >= 2:
                    fallback_score += 2.0
                elif len(languages) == 1:
                    fallback_score += 1.0
                
                repo['fallback_score'] = fallback_score
                fallback_repos.append(repo)
                
            except Exception as e:
                logger.error(f"Error calculating fallback score for {repo.get('name', 'unknown')}: {str(e)}")
                repo['fallback_score'] = 0.0
                fallback_repos.append(repo)
        
        # Sort by fallback score and return top repositories
        fallback_repos.sort(key=lambda x: x.get('fallback_score', 0), reverse=True)
        selected_repos = fallback_repos[:limit]
        
        logger.info(f"Selected {len(selected_repos)} fallback repositories")
        return selected_repos

    def get_difficulty_score(self, repo: Dict) -> Dict[str, Any]:
        """
        Get difficulty score with caching.
        
        Args:
            repo: Repository dictionary
            
        Returns:
            Dictionary with difficulty analysis
        """
        # For now, delegate to calculate_difficulty_score
        return self.calculate_difficulty_score(repo)

    def calculate_difficulty_score(self, repo: Dict) -> Dict[str, Any]:
        """
        Calculate comprehensive difficulty score for a repository.
        
        Args:
            repo: Repository dictionary with context
            
        Returns:
            Dictionary with difficulty analysis
        """
        try:
            repo_context = extract_repo_data(repo, 'repoContext', {})
            
            # Check for explicit difficulty rating
            explicit_difficulty = repo_context.get('difficulty', {}).get('level', '').lower()
            if explicit_difficulty:
                normalized_difficulty = self._normalize_difficulty(explicit_difficulty)
                explicit_score = self._map_explicit_difficulty(normalized_difficulty)
                
                return {
                    'overall_score': explicit_score,
                    'difficulty_level': self._determine_difficulty_level(explicit_score),
                    'source': 'explicit',
                    'explicit_rating': explicit_difficulty,
                    'confidence_scores': {'explicit': 1.0}
                }
            
            # Calculate difficulty from various factors
            scores = {
                'curriculum_level': self._calculate_curriculum_level(repo),
                'architecture_complexity': self._calculate_architecture_complexity(repo),
                'skill_requirements': self._calculate_skill_requirements(repo),
                'implementation_complexity': self._calculate_implementation_complexity(repo),
                'deployment_complexity': self._calculate_deployment_complexity(repo),
                'technology_complexity': self._calculate_technology_complexity(repo),
                'integration_complexity': self._calculate_integration_complexity(repo),
                'repo_metrics': self._calculate_repo_metrics(repo)
            }
            
            # Calculate weighted average
            weights = {
                'curriculum_level': 0.20,
                'architecture_complexity': 0.15,
                'skill_requirements': 0.15,
                'implementation_complexity': 0.15,
                'deployment_complexity': 0.10,
                'technology_complexity': 0.10,
                'integration_complexity': 0.10,
                'repo_metrics': 0.05
            }
            
            overall_score = sum(scores[key] * weights[key] for key in scores)
            difficulty_level = self._determine_difficulty_level(overall_score)
            
            # Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(scores, repo_context)
            
            return {
                'overall_score': round(overall_score, 2),
                'difficulty_level': difficulty_level,
                'source': 'calculated',
                'component_scores': scores,
                'confidence_scores': confidence_scores,
                'weights_used': weights
            }
            
        except Exception as e:
            logger.error(f"Error calculating difficulty for {repo.get('name', 'unknown')}: {str(e)}")
            return self._default_difficulty_response()

    def _calculate_all_scores(self, processed_repo: Dict, search_terms: Dict) -> Dict:
        """Calculate all relevance scores for a repository."""
        repo_context = extract_repo_data(processed_repo, 'repoContext', {})
        context_terms = search_terms.get('context_terms', {})
        language_terms = search_terms.get('language_terms', [])
        
        # Calculate individual scores
        language_score = calculate_language_score(
            processed_repo.get('languages', {}),
            language_terms,
            processed_repo.get('total_language_bytes', 0)
        )
        
        tech_score = calculate_tech_score(
            repo_context.get('tech_stack', {}),
            context_terms
        )
        
        skill_score = calculate_skill_score(
            repo_context.get('skill_manifest', {}),
            context_terms
        )
        
        component_score = calculate_component_score(
            repo_context.get('components', {}),
            context_terms
        )
        
        project_score = calculate_project_score(
            repo_context.get('project_identity', {}),
            context_terms
        )
        
        general_score = calculate_general_score(processed_repo, context_terms)
        bonus_score = calculate_bonus_score(processed_repo, context_terms)
        
        # Store individual scores
        relevance_scores = {
            'language': language_score,
            'tech': tech_score,
            'skill': skill_score,
            'component': component_score,
            'project': project_score,
            'general': general_score,
            'bonus': bonus_score
        }
        
        # Calculate total score
        total_score = sum(relevance_scores.values())
        
        return {
            'relevance_scores': relevance_scores,
            'total_relevance_score': total_score,
            'language_relevance_score': language_score
        }

    def _log_scoring_results(self, scored_repos: List[Dict], language_terms: List[str]) -> None:
        """Log scoring results for debugging."""
        if scored_repos:
            top_3 = scored_repos[:3]
            scores = [repo.get('total_relevance_score', 0) for repo in top_3]
            names = [repo.get('name', 'unknown') for repo in top_3]
            
            logger.info(f"Top 3 scored repositories: {list(zip(names, scores))}")
            logger.info(f"Language terms used: {language_terms}")

    def _log_processing_results(self, limited_repos: List[Dict], total_processed: int, language_terms: List[str]) -> None:
        """Log processing results for debugging."""
        logger.info(f"Processed {total_processed} repositories, returning top {len(limited_repos)}")
        
        if limited_repos:
            top_repo = limited_repos[0]
            logger.info(f"Top repository: {top_repo.get('name')} (score: {top_repo.get('total_relevance_score', 0)})")

    # Difficulty calculation helper methods
    def _default_difficulty_response(self) -> Dict[str, Any]:
        """Return default difficulty response for errors."""
        return {
            'overall_score': 3.0,
            'difficulty_level': 'intermediate',
            'source': 'default',
            'error': 'Could not calculate difficulty',
            'confidence_scores': {'default': 0.1}
        }

    def _normalize_difficulty(self, difficulty: str) -> str:
        """Normalize difficulty string."""
        difficulty = difficulty.lower().strip()
        
        # Map variations to standard levels
        mappings = {
            'beginner': ['beginner', 'basic', 'easy', 'simple', 'intro', 'starter'],
            'intermediate': ['intermediate', 'medium', 'moderate', 'standard'],
            'advanced': ['advanced', 'hard', 'difficult', 'complex', 'expert', 'professional']
        }
        
        for level, variations in mappings.items():
            if difficulty in variations:
                return level
        
        return 'intermediate'  # Default

    def _map_explicit_difficulty(self, difficulty: str) -> float:
        """Map explicit difficulty to numeric score."""
        mapping = {
            'beginner': 2.0,
            'intermediate': 5.0,
            'advanced': 8.0
        }
        return mapping.get(difficulty, 5.0)

    def _determine_difficulty_level(self, score: float) -> str:
        """Determine difficulty level from numeric score."""
        if score <= 3.0:
            return 'beginner'
        elif score <= 6.0:
            return 'intermediate'
        else:
            return 'advanced'

    def _calculate_confidence_scores(self, scores: Dict[str, float], repo_context: Dict) -> Dict[str, float]:
        """Calculate confidence scores for difficulty assessment."""
        confidence = {}
        
        # Base confidence on available data
        if repo_context.get('tech_stack'):
            confidence['tech_stack'] = 0.8
        if repo_context.get('skill_manifest'):
            confidence['skills'] = 0.8
        if repo_context.get('components'):
            confidence['architecture'] = 0.7
        
        # Overall confidence based on data completeness
        data_completeness = len([v for v in scores.values() if v > 0]) / len(scores)
        confidence['overall'] = data_completeness * 0.8
        
        return confidence

    def _calculate_curriculum_level(self, repo: Dict) -> float:
        """Calculate curriculum level complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        skill_manifest = repo_context.get('skill_manifest', {})
        
        # Count advanced skills and concepts
        technical_skills = skill_manifest.get('technical', [])
        domain_skills = skill_manifest.get('domain', [])
        
        advanced_keywords = [
            'machine learning', 'deep learning', 'ai', 'distributed',
            'microservices', 'kubernetes', 'docker', 'cloud',
            'blockchain', 'cryptography', 'big data', 'analytics'
        ]
        
        score = 3.0  # Base intermediate level
        
        # Check for advanced concepts
        all_skills = technical_skills + domain_skills
        for skill in all_skills:
            skill_lower = skill.lower()
            for keyword in advanced_keywords:
                if keyword in skill_lower:
                    score += 1.0
        
        return min(score, 10.0)

    def _calculate_architecture_complexity(self, repo: Dict) -> float:
        """Calculate architecture complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        components = repo_context.get('components', {})
        
        # Base complexity on number and type of components
        num_components = len(components)
        
        if num_components == 0:
            return 2.0
        elif num_components <= 3:
            return 4.0
        elif num_components <= 6:
            return 6.0
        else:
            return 8.0

    def _calculate_skill_requirements(self, repo: Dict) -> float:
        """Calculate skill requirements complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        tech_stack = repo_context.get('tech_stack', {})
        
        # Count technologies
        primary_tech = len(tech_stack.get('primary', []))
        secondary_tech = len(tech_stack.get('secondary', []))
        libraries = len(tech_stack.get('key_libraries', []))
        
        total_tech = primary_tech + secondary_tech + libraries
        
        if total_tech <= 2:
            return 3.0
        elif total_tech <= 5:
            return 5.0
        elif total_tech <= 10:
            return 7.0
        else:
            return 9.0

    def _calculate_implementation_complexity(self, repo: Dict) -> float:
        """Calculate implementation complexity (0-10)."""
        # Use language diversity as a proxy
        languages = repo.get('languages', {})
        num_languages = len(languages)
        
        if num_languages <= 1:
            return 3.0
        elif num_languages <= 3:
            return 5.0
        elif num_languages <= 5:
            return 7.0
        else:
            return 9.0

    def _calculate_deployment_complexity(self, repo: Dict) -> float:
        """Calculate deployment complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        components = repo_context.get('components', {})
        
        # Look for deployment-related components
        deployment_indicators = [
            'dockerfile', 'docker-compose', 'kubernetes', 'helm',
            'terraform', 'ansible', 'ci/cd', 'pipeline'
        ]
        
        score = 3.0  # Base score
        
        for comp_name, comp_data in components.items():
            comp_name_lower = comp_name.lower()
            for indicator in deployment_indicators:
                if indicator in comp_name_lower:
                    score += 1.0
        
        return min(score, 10.0)

    def _calculate_technology_complexity(self, repo: Dict) -> float:
        """Calculate technology stack complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        tech_stack = repo_context.get('tech_stack', {})
        
        # Advanced technologies
        advanced_tech = [
            'tensorflow', 'pytorch', 'react', 'angular', 'vue',
            'kubernetes', 'docker', 'aws', 'azure', 'gcp',
            'redis', 'elasticsearch', 'mongodb', 'postgresql'
        ]
        
        score = 3.0  # Base score
        
        all_tech = []
        for category in ['primary', 'secondary', 'key_libraries', 'development_tools']:
            all_tech.extend(tech_stack.get(category, []))
        
        for tech in all_tech:
            tech_lower = tech.lower()
            for advanced in advanced_tech:
                if advanced in tech_lower:
                    score += 0.5
        
        return min(score, 10.0)

    def _calculate_integration_complexity(self, repo: Dict) -> float:
        """Calculate integration complexity (0-10)."""
        repo_context = extract_repo_data(repo, 'repoContext', {})
        components = repo_context.get('components', {})
        
        # Look for integration patterns
        integration_patterns = [
            'api', 'rest', 'graphql', 'webhook', 'message',
            'queue', 'event', 'stream', 'microservice'
        ]
        
        score = 3.0  # Base score
        
        for comp_name, comp_data in components.items():
            comp_str = str(comp_data).lower()
            for pattern in integration_patterns:
                if pattern in comp_str:
                    score += 0.5
        
        return min(score, 10.0)

    def _calculate_repo_metrics(self, repo: Dict) -> float:
        """Calculate repository metrics complexity (0-10)."""
        # Use repository size and structure as indicators
        size = repo.get('size', 0)
        
        if size < 100:
            return 2.0
        elif size < 1000:
            return 4.0
        elif size < 10000:
            return 6.0
        else:
            return 8.0
