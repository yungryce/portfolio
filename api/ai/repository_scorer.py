import logging
import math
import re
from typing import Any, Dict, List, Tuple, Type, TypeVar
from data_filter import extract_language_terms, advanced_skills, complexity_indicators
from ai.helpers import (
    # Language processing
    calculate_language_score, get_language_matches,
    process_language_data,
    
    # Search and scoring
    extract_context_terms, calculate_tech_score, calculate_skill_score,
    calculate_component_score, calculate_project_score, calculate_general_score,
    calculate_bonus_score
)

# Use the existing logger from function_app.py
logger = logging.getLogger('portfolio.api')
T = TypeVar('T')


def extract_repo_data(repo: Dict, path: str, default: Any = None, as_type: Type[T] = None) -> Any:
    """
    Extract data from repository using dot notation path with type conversion.
    
    Args:
        repo: Repository dictionary
        path: Dot-separated path to the data (e.g., "repoContext.tech_stack.primary")
        default: Default value if path doesn't exist
        as_type: Optional type to convert the result to (e.g., int, float, list)
        
    Returns:
        The extracted data or default value
    """
    if repo is None:
        return default
    
    current = repo
    parts = path.split('.')
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current.get(part)
        else:
            return default
    
    # Handle type conversion if requested
    if as_type is not None and current is not None:
        try:
            if as_type == bool and isinstance(current, str):
                return current.lower() in ('true', 'yes', '1')
            return as_type(current)
        except (ValueError, TypeError):
            return default
    
    return current if current is not None else default


class RepositoryScorer:
    """
    Handles repository scoring, relevance calculation, and difficulty assessment.
    Responsible for ranking repositories based on search terms and calculating difficulty scores.
    """
    
    def __init__(self):
        """Initialize the RepositoryScorer."""
        logger.info("RepositoryScorer initialized")
    
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
            # Create a copy to avoid modifying the original
            processed_repo = repo.copy()
            
            # Trim and process repository data
            processed_repo = process_language_data(processed_repo)
            
            # Calculate repository difficulty scoring
            difficulty_data = self.get_difficulty_score(processed_repo)
            processed_repo['difficulty_analysis'] = difficulty_data

            # Add difficulty score as factor in relevance scoring
            # This makes high-difficulty projects slightly more relevant, all else being equal
            difficulty_boost = difficulty_data.get('score', 0) / 1000  # Small boost based on difficulty

            # Calculate all relevance scores
            processed_repo = self._calculate_all_scores(processed_repo, search_terms)
            
            # Apply difficulty boost to total score
            if 'total_relevance_score' in processed_repo:
                processed_repo['total_relevance_score'] += difficulty_boost
                
                # Note the difficulty boost in the scores
                if 'relevance_scores' in processed_repo:
                    processed_repo['relevance_scores']['difficulty_boost'] = difficulty_boost
            
            processed_repos.append(processed_repo)
        
        # Sort by total relevance score and apply limit
        processed_repos.sort(key=lambda x: x.get('total_relevance_score', 0), reverse=True)
        limited_repos = processed_repos[:limit]
        
        # Log results
        self._log_processing_results(limited_repos, len(processed_repos), language_terms)
        
        return limited_repos

    def get_fallback_repositories(self, repositories: List[Dict], limit: int = 5) -> List[Dict]:
        """
        Get fallback repositories based on difficulty and total bytes when no strong matches found.
        
        Args:
            repositories: List of all repositories
            limit: Maximum number of repositories to return
            
        Returns:
            List of top repositories by difficulty and size
        """
        logger.info("Using fallback strategy to select repositories by difficulty and size")
        scored_repos = []
        
        for repo in repositories:
            # Get difficulty score using the caching method
            difficulty_data = self.get_difficulty_score(repo)
            difficulty_score = difficulty_data.get('score', 0)
            
            # Get total language bytes
            total_bytes = extract_repo_data(repo, 'total_language_bytes', 0)
            if total_bytes == 0:
                # Calculate if not already processed
                languages = extract_repo_data(repo, 'languages', {})
                total_bytes = sum(languages.values()) if languages else 0
            
            # Combined score: difficulty (0-100) + normalized bytes
            # Normalize bytes to 0-50 scale for balance
            normalized_bytes = min(total_bytes / 100000, 50)  # 100KB = 50 points max
            combined_score = difficulty_score + normalized_bytes
            
            scored_repos.append({
                'repo': repo,
                'combined_score': combined_score,
                'difficulty_score': difficulty_score,
                'total_bytes': total_bytes
            })
        
        # Sort by combined score
        scored_repos.sort(key=lambda x: x['combined_score'], reverse=True)
        
        logger.info(f"Fallback: Selected top {limit} repositories by difficulty and size")
        for i, item in enumerate(scored_repos[:limit]):
            repo_name = extract_repo_data(item['repo'], 'name', 'Unknown')
            logger.info(f"  {i+1}. {repo_name}: "
                        f"Combined={item['combined_score']:.1f} "
                        f"(Difficulty={item['difficulty_score']}, Bytes={item['total_bytes']})")

        return [item['repo'] for item in scored_repos[:limit]]

    def get_difficulty_score(self, repo: Dict) -> Dict[str, Any]:
        """
        Get repository difficulty score with caching to avoid redundant calculations.
        
        Args:
            repo: Repository dictionary
            
        Returns:
            Dictionary with detailed difficulty analysis
        """
        # Return cached difficulty score if already calculated
        if 'difficulty_analysis' in repo:
            logger.debug(f"Using cached difficulty score for {extract_repo_data(repo, 'name', 'Unknown')}")
            return repo['difficulty_analysis']
        
        # Calculate difficulty score if not cached
        difficulty_data = self.calculate_difficulty_score(repo)
        
        # Cache the result in the repository object
        repo['difficulty_analysis'] = difficulty_data
        
        return difficulty_data

    def calculate_difficulty_score(self, repo: Dict) -> Dict[str, Any]:
        """
        Calculate comprehensive difficulty score using rich repository context.
        
        Args:
            repo: Repository dictionary with full context
            
        Returns:
            Dictionary with detailed difficulty analysis
        """
        if not repo:
            return self._default_difficulty_response()
        
        # Extract assessment data once for consistency
        explicit_assessment = extract_repo_data(repo, 'repoContext.assessment', {})
        
        # Direct difficulty indicators (if available)
        explicit_difficulty = self._normalize_difficulty(
            extract_repo_data(explicit_assessment, 'difficulty', '')
        )
        explicit_hours = extract_repo_data(explicit_assessment, 'estimated_hours', 0, as_type=int)
        
        # Initialize score components with error handling
        scores = {}
        score_methods = {
            'explicit_rating': lambda: self._map_explicit_difficulty(explicit_difficulty),
            'curriculum_level': lambda: self._calculate_curriculum_level(repo),
            'architecture_complexity': lambda: self._calculate_architecture_complexity(repo),
            'skill_requirements': lambda: self._calculate_skill_requirements(repo),
            'implementation_complexity': lambda: self._calculate_implementation_complexity(repo),
            'deployment_complexity': lambda: self._calculate_deployment_complexity(repo),
            'technology_complexity': lambda: self._calculate_technology_complexity(repo),
            'integration_complexity': lambda: self._calculate_integration_complexity(repo),
            'repo_metrics': lambda: self._calculate_repo_metrics(repo)
        }

        for score_name, score_method in score_methods.items():
            try:
                scores[score_name] = score_method()
            except Exception as e:
                logger.warning(f"Error calculating {score_name} for repo {extract_repo_data(repo, 'name', 'Unknown')}: {str(e)}")
                scores[score_name] = 0.0
        
        # Calculate confidence levels for each dimension
        confidence = self._calculate_confidence_scores(scores, repo)
        
        # Weighted calculation of final score
        weights = {
            'explicit_rating': 15,
            'curriculum_level': 10,
            'architecture_complexity': 15,
            'skill_requirements': 15,
            'implementation_complexity': 10,
            'deployment_complexity': 10,
            'technology_complexity': 15,
            'integration_complexity': 5,
            'repo_metrics': 5
        }
        
        # Calculate weighted score and normalize to 0-100 with validation
        total_weight = sum(weights.values())
        if total_weight > 0:
            weighted_score = sum(scores[key] * (weights[key]/total_weight) for key in weights)
            final_score = min(weighted_score * 100, 100)
        else:
            final_score = 0
        
        # Determine difficulty level
        difficulty_level = self._determine_difficulty_level(final_score)
        
        # Collect reasoning statements from component calculations
        reasoning = []
        for dimension, score in scores.items():
            if score > 0:
                reasoning.append(f"{dimension.replace('_', ' ').title()}: {score:.1f}/1.0")
        
        if explicit_hours > 0:
            reasoning.append(f"Estimated completion hours: {explicit_hours}")
        
        # Fixed: Use the properly defined explicit_assessment variable
        if explicit_assessment.get('complexity_factors'):
            reasoning.append(f"Key complexity factors: {', '.join(explicit_assessment.get('complexity_factors')[:3])}")
        
        # Calculate weighted confidence instead of simple average
        weighted_confidence = sum(confidence[key] * (weights[key]/total_weight) for key in weights if key in confidence and total_weight > 0)
        total_confidence = round(weighted_confidence if total_weight > 0 else 0, 2)
        
        return {
            'difficulty': difficulty_level,
            'score': round(final_score, 1),
            'confidence': total_confidence,
            'reasoning': reasoning,
            'dimensions': scores,
            'confidence_by_dimension': confidence,
            'explicit_assessment': {
                'difficulty': explicit_difficulty,
                'estimated_hours': explicit_hours
            }
        }

    def _calculate_all_scores(self, processed_repo: Dict, search_terms: Dict) -> Dict:
        """Extract score calculation logic for modularity."""
        repo_languages = extract_repo_data(processed_repo, 'languages', {})
        total_bytes = extract_repo_data(processed_repo, 'total_language_bytes', 0)
        
        # Calculate all category scores
        language_score = calculate_language_score(repo_languages, search_terms.get('languages', []), total_bytes)
        tech_score = calculate_tech_score(extract_repo_data(processed_repo, 'repoContext.tech_stack', {}), search_terms)
        skill_score = calculate_skill_score(extract_repo_data(processed_repo, 'repoContext.skill_manifest', {}), search_terms)
        component_score = calculate_component_score(extract_repo_data(processed_repo, 'repoContext.components', {}), search_terms)
        project_score = calculate_project_score(extract_repo_data(processed_repo, 'repoContext.project_identity', {}), search_terms)
        general_score = calculate_general_score(processed_repo, search_terms)

        # Store category-specific scores
        processed_repo['relevance_scores'] = {
            'language': language_score,
            'tech': tech_score,
            'skill': skill_score,
            'component': component_score,
            'project': project_score,
            'general': general_score
        }
        
        # Store language-specific data
        processed_repo['language_relevance_score'] = language_score
        
        # Enhanced: Pass relevance_scores to get_language_matches
        matched_languages = get_language_matches(
            repo_languages, 
            search_terms.get('languages', []), 
            processed_repo['relevance_scores']
        )
        processed_repo['matched_query_languages'] = matched_languages
        
        # Enhanced: Calculate bonus score using relevance_scores
        bonus_score = calculate_bonus_score(processed_repo, search_terms)
        processed_repo['relevance_scores']['bonus'] = bonus_score
        
        # Calculate total score
        total_relevance_score = (
            language_score + tech_score + skill_score + 
            component_score + project_score + general_score + bonus_score
        )
        processed_repo['total_relevance_score'] = total_relevance_score
        
        return processed_repo

    def _log_processing_results(self, limited_repos: List[Dict], total_processed: int, language_terms: List[str]) -> None:
        """Extract logging logic for modularity."""
        logger.debug(f"Total Processed {total_processed} repositories, returning top {len(limited_repos)}")
        logger.info(f"Top {min(5, len(limited_repos))} repositories by total relevance score:")

        for i, repo in enumerate(limited_repos[:5]):
            scores = extract_repo_data(repo, 'relevance_scores', {})
            difficulty = extract_repo_data(repo, 'difficulty_analysis.difficulty', 'Unknown')
            difficulty_score = extract_repo_data(repo, 'difficulty_analysis.score', 0)

            logger.info(f"  {i+1}. {extract_repo_data(repo, 'name', 'Unknown')}: "
                        f"Total={extract_repo_data(repo, 'total_relevance_score', 0):.2f} "
                        f"[lang:{scores.get('language', 0):.1f}, "
                        f"tech:{scores.get('tech', 0):.1f}, "
                        f"skill:{scores.get('skill', 0):.1f}, "
                        f"comp:{scores.get('component', 0):.1f}, "
                        f"proj:{scores.get('project', 0):.1f}, "
                        f"gen:{scores.get('general', 0):.1f}, "
                        f"bonus:{scores.get('bonus', 0):.1f}, "
                        f"diff_boost:{scores.get('difficulty_boost', 0):.3f}] "
                        f"Difficulty: {difficulty} ({difficulty_score:.1f})")

    # Difficulty calculation helper methods
    def _default_difficulty_response(self) -> Dict[str, Any]:
        """Generate default difficulty response for empty repositories."""
        return {
            'difficulty': 'Unknown',
            'score': 0,
            'confidence': 0,
            'reasoning': ['Repository data unavailable'],
            'dimensions': {},
            'confidence_by_dimension': {},
            'explicit_assessment': {
                'difficulty': '',
                'estimated_hours': 0
            }
        }

    def _normalize_difficulty(self, difficulty: str) -> str:
        """Normalize difficulty string values."""
        if not difficulty:
            return ""
        
        difficulty = difficulty.lower().strip()
        if difficulty in ('beginner', 'easy', 'simple'):
            return 'beginner'
        elif difficulty in ('intermediate', 'medium', 'moderate'):
            return 'intermediate'
        elif difficulty in ('advanced', 'hard', 'complex'):
            return 'advanced'
        elif difficulty in ('expert', 'very hard', 'very complex'):
            return 'expert'
        
        return difficulty

    def _map_explicit_difficulty(self, difficulty: str) -> float:
        """Map explicit difficulty string to a 0-1 score."""
        if not difficulty:
            return 0.0
        
        mapping = {
            'beginner': 0.25,
            'intermediate': 0.5, 
            'advanced': 0.75,
            'expert': 1.0
        }
        
        return mapping.get(difficulty.lower(), 0.0)

    def _determine_difficulty_level(self, score: float) -> str:
        """Map numeric score to difficulty level."""
        if score < 25:
            return 'Beginner'
        elif score < 50:
            return 'Intermediate'
        elif score < 75:
            return 'Advanced'
        else:
            return 'Expert'

    def _calculate_confidence_scores(self, scores: Dict[str, float], repo_context: Dict) -> Dict[str, float]:
        """Calculate confidence levels for each dimension."""
        confidence = {}
        
        # Default confidence based on data presence
        assessment_difficulty = extract_repo_data(repo_context, 'assessment.difficulty')
        if assessment_difficulty:
            confidence['explicit_rating'] = 1.0
        else:
            confidence['explicit_rating'] = 0.0

        confidence['curriculum_level'] = 1.0 if extract_repo_data(repo_context, 'project_identity.curriculum_stage') else 0.5
        confidence['architecture_complexity'] = 0.8 if extract_repo_data(repo_context, 'components') else 0.3
        confidence['skill_requirements'] = 0.8 if extract_repo_data(repo_context, 'skill_manifest') else 0.4
        confidence['implementation_complexity'] = 0.7 if extract_repo_data(repo_context, 'components') else 0.3
        confidence['deployment_complexity'] = 0.8 if extract_repo_data(repo_context, 'deployment_workflow') else 0.2
        confidence['technology_complexity'] = 0.9 if extract_repo_data(repo_context, 'tech_stack') else 0.4
        confidence['integration_complexity'] = 0.7 if extract_repo_data(repo_context, 'components.integration_points') else 0.3
        confidence['repo_metrics'] = 0.6  # Consistently available but less precise indicator
        
        return confidence

    def _calculate_curriculum_level(self, repo: Dict) -> float:
        """Calculate curriculum level score."""
        curriculum_stage = extract_repo_data(
            repo, 'repoContext.project_identity.curriculum_stage', ''
        ).lower()
        
        if curriculum_stage == 'capstone':
            return 1.0
        elif curriculum_stage == 'advanced':
            return 0.75
        elif curriculum_stage == 'intermediate':
            return 0.5
        elif curriculum_stage == 'beginner':
            return 0.25
        
        # If no explicit curriculum stage, look for clues
        repo_context_str = str(extract_repo_data(repo, 'repoContext', {})).lower()
        if 'capstone' in repo_context_str:
            return 0.9
        if 'advanced' in repo_context_str:
            return 0.7
        
        return 0.0

    def _calculate_architecture_complexity(self, repo: Dict) -> float:
        """Calculate architecture complexity score."""
        score = 0.0
        components = extract_repo_data(repo, 'repoContext.components', {})

        # Component count and complexity
        if 'main_directories' in components:
            dir_count = len(components.get('main_directories', []))
            complex_count = sum(1 for dir in components.get('main_directories', []) 
                                if extract_repo_data(dir, 'complexity', '').lower() in ['advanced', 'expert'])
            
            # Score based on directory count and complexity level
            score += min(dir_count / 10, 0.5)  # Max 0.5 for directory count
            score += min(complex_count / 5, 0.5)  # Max 0.5 for complex components
        
        # Integration points
        integration_points = components.get('integration_points', [])
        score += min(len(integration_points) / 10, 0.4)
        
        # Project structure complexity
        project_structure = extract_repo_data(repo, 'repoContext.projectStructure', {})
        file_types = len(project_structure) if isinstance(project_structure, dict) else 0
        score += min(file_types / 10, 0.1)
        
        return min(score, 1.0)

    def _calculate_skill_requirements(self, repo: Dict) -> float:
        """Calculate skill requirements score based on comprehensive skill analysis."""
        skill_manifest = extract_repo_data(repo, 'repoContext.skill_manifest', {})

        # Direct competency level assessment if available
        competency_level = extract_repo_data(skill_manifest, 'competency_level', '').lower()
        if 'expert' in competency_level:
            return 1.0
        elif 'advanced' in competency_level:
            return 0.75
        elif 'intermediate' in competency_level:
            return 0.5
        elif 'beginner' in competency_level:
            return 0.25
        
        # Count skills by type
        technical_skills = len(skill_manifest.get('technical', []))
        domain_skills = len(skill_manifest.get('domain', []))
        
        # Calculate score based on skill counts
        skill_count_score = min((technical_skills + domain_skills) / 20, 0.6)
        
        # Use the comprehensive advanced skills set from data_filter.py
        all_skills = skill_manifest.get('technical', []) + skill_manifest.get('domain', [])
        
        # Count advanced skills using the expanded set
        advanced_count = sum(
            1 for skill in all_skills
            if any(adv in skill.lower() for adv in advanced_skills)
        )
        
        # Adjust scoring to account for the larger advanced_skills set
        # Scale to ensure reasonable scoring with the expanded list
        advanced_score = min(advanced_count / 15, 0.4)  # Adjusted divisor from 10 to 15
        
        # Log detected advanced skills for debugging/analysis
        if advanced_count > 0:
            detected_skills = [skill for skill in all_skills 
                            if any(adv in skill.lower() for adv in advanced_skills)]
            logger.debug(f"Advanced skills detected in repository: {detected_skills[:5]}")
        
        return min(skill_count_score + advanced_score, 1.0)

    def _calculate_implementation_complexity(self, repo: Dict) -> float:
        """Calculate implementation complexity score."""
        # Check for explicit complexity factors in assessment
        complexity_factors = extract_repo_data(repo, 'repoContext.assessment.complexity_factors', [])
        if complexity_factors:
            return min(len(complexity_factors) / 10, 0.8)
        
        # Look at components implementation details
        components = extract_repo_data(repo, 'repoContext.components', {})
        if not components:
            return 0.0
        
        component_str = str(components).lower()
        feature_count = sum(1 for indicator in complexity_indicators if indicator in component_str)
        
        # Apply a logarithmic scale to account for the larger list (prevents over-scoring)
        if feature_count > 0:
            # Log base 2 scale: 1->0, 2->1, 4->2, 8->3, 16->4, etc.
            # Then normalize to 0-1 range with a divisor that keeps reasonable scores
            scaled_score = min(math.log2(feature_count + 1) / 5, 1.0)
            return scaled_score
        
        return 0.0

    def _calculate_deployment_complexity(self, repo: Dict) -> float:
        """Calculate deployment complexity based on presence of deployment files."""
                
        # 1. Check if we have file listing in the repo object itself
        files = extract_repo_data(repo, 'file_paths', [])
        if files:
            return self._score_deployment_files_from_listing(files)
        else:
            # 1. First check if deployment workflow info already exists in repo context
            workflow = extract_repo_data(repo, 'repoContext.deployment_workflow', [])
            if workflow:
                # Use existing workflow data for scoring
                return self._score_deployment_workflow(workflow)
            
            # 2. Next check if we already have files information in repo context
            files_info = extract_repo_data(repo, 'repoContext.files.key_files', [])
            if files_info:
                return self._score_deployment_files_from_context(files_info)
        
        return 0.0

    def _score_deployment_files_from_listing(self, files):
        """Score deployment complexity based on file listing."""
        if not files:
            logger.debug("No files provided for deployment complexity scoring")
            return 0.0
        
        # Handle both file path strings and raw directory listings
        file_paths = []
        if isinstance(files, list):
            # If we have a list of dictionaries (raw GitHub API response)
            if files and isinstance(files[0], dict):
                file_paths = [item.get('path') for item in files if isinstance(item, dict) and 'path' in item]
            # If we have a list of strings (already processed paths)
            else:
                file_paths = [f for f in files if isinstance(f, str)]
        
        # Import deployment patterns
        from data_filter import tool_ecosystems
        
        # Track matches by ecosystem
        ecosystem_matches = {}
        
        # Match files against patterns for each ecosystem
        for filepath in file_paths:
            for ecosystem_name, ecosystem_data in tool_ecosystems.items():
                patterns = ecosystem_data.get('patterns', [])
                
                for pattern in patterns:
                    if re.search(pattern, filepath, re.IGNORECASE):
                        # Add to ecosystem matches
                        if ecosystem_name not in ecosystem_matches:
                            ecosystem_matches[ecosystem_name] = {
                                'files': [],
                                'confidence_weight': ecosystem_data.get('confidence_weight', 0.5),
                                'coverage_weight': ecosystem_data.get('coverage_weight', 0.5)
                            }
                        
                        ecosystem_matches[ecosystem_name]['files'].append(filepath)
                        logger.debug(f"Matched {ecosystem_name} file: {filepath}")
                        break  # Only count each file once per ecosystem
        
        # Calculate ecosystem-based scores
        if not ecosystem_matches:
            logger.debug("No tool ecosystems detected in file listing")
            return 0.0
        
        # Calculate score based on:
        # 1. Number of distinct ecosystems detected
        ecosystem_count_score = min(len(ecosystem_matches) * 0.15, 0.45)  # Up to 0.45 for 3+ ecosystems
        
        # 2. Highest confidence ecosystem
        max_confidence = max([data.get('confidence_weight', 0) for data in ecosystem_matches.values()])
        
        # 3. Coverage (number of files) for top ecosystems
        coverage_scores = []
        for ecosystem_name, data in ecosystem_matches.items():
            file_count = len(data['files'])
            coverage_weight = data.get('coverage_weight', 0.5)
            ecosystem_coverage = min(file_count / 5, 1.0) * coverage_weight
            coverage_scores.append(ecosystem_coverage)
        
        # Take average of top 2 coverage scores if available
        top_coverage_score = sum(sorted(coverage_scores, reverse=True)[:2]) / min(len(coverage_scores), 2) if coverage_scores else 0
        top_coverage_contribution = top_coverage_score * 0.35  # Up to 0.35 for coverage
        
        # Total score calculation
        total_score = min(ecosystem_count_score + max_confidence * 0.2 + top_coverage_contribution, 1.0)
        
        logger.debug(f"Deployment score: {total_score:.2f} (ecosystems={len(ecosystem_matches)}, " 
                    f"max_confidence={max_confidence:.2f}, top_coverage={top_coverage_contribution:.2f})")
        
        # Log detected ecosystems for visibility
        for ecosystem, data in ecosystem_matches.items():
            logger.debug(f"  - {ecosystem}: {len(data['files'])} files, weight={data['confidence_weight']}")
        
        return total_score

    def _score_deployment_workflow(self, workflow: List[Dict]) -> float:
        """Score deployment complexity based on workflow details."""
        if not workflow:
            return 0.0
        
        # Number of deployment steps
        step_count = len(workflow)
        step_score = min(step_count / 10, 0.4)
        
        # Complexity of steps
        complex_steps = sum(1 for step in workflow 
                            if 'complexity' in step and extract_repo_data(step, 'complexity', '').lower() in ['advanced', 'complex'])
        complexity_score = min(complex_steps / 5, 0.3)
        
        # Duration of deployment
        try:
            total_duration = sum(
                int(extract_repo_data(step, 'estimated_duration', '0').split('-')[0]) 
                for step in workflow 
                if isinstance(extract_repo_data(step, 'estimated_duration', ''), str) and extract_repo_data(step, 'estimated_duration', '').split('-')[0].isdigit()
            )
            duration_score = min(total_duration / 60, 0.3)  # 60 minutes = 0.3
        except (ValueError, IndexError):
            duration_score = 0.0
        
        return min(step_score + complexity_score + duration_score, 1.0)

    def _score_deployment_files_from_context(self, files_info: List[Dict]) -> float:
        """Score deployment complexity based on files information in repo context."""
        if not files_info:
            return 0.0
        
        # Heuristic scoring based on file types and counts
        file_types = set()
        for file in files_info:
            file_type = extract_repo_data(file, 'type', '').lower()
            if file_type:
                file_types.add(file_type)
        
        # Score based on number of different file types
        return min(len(file_types) / 5, 1.0)

    def _calculate_technology_complexity(self, repo: Dict) -> float:
        """Calculate technology stack complexity."""
        tech_stack = extract_repo_data(repo, 'repoContext.tech_stack', {})
        if not tech_stack:
            return 0.0
        
        # Count technologies by category
        primary = len(extract_repo_data(tech_stack, 'primary', []))
        secondary = len(extract_repo_data(tech_stack, 'secondary', []))
        libraries = len(extract_repo_data(tech_stack, 'key_libraries', []))
        tools = len(extract_repo_data(tech_stack, 'development_tools', []))
        
        # Calculate complexity score
        base_score = primary * 0.2 + secondary * 0.1 + libraries * 0.05 + tools * 0.05
        
        tech_str = str(tech_stack).lower()
        complex_count = sum(1 for tech in advanced_skills if tech in tech_str)
        complex_score = min(complex_count / 5, 0.5)
        
        return min(base_score + complex_score, 1.0)

    def _calculate_integration_complexity(self, repo: Dict) -> float:
        """Calculate integration complexity score."""
        components = extract_repo_data(repo, 'repoContext.components', {})
        integration_points = extract_repo_data(components, 'integration_points', [])
    
        if not integration_points:
            return 0.0
        
        # Number of integration points
        point_count = len(integration_points)
        point_score = min(point_count / 10, 0.6)
        
        # Types of integrations (API, database, third-party services)
        integration_types = set()
        for point in integration_points:
            if isinstance(point, dict):
                point_type = extract_repo_data(point, 'type', '').lower()
                if point_type:
                    integration_types.add(point_type)
            elif isinstance(point, str):
                for type_name in ['api', 'database', 'service', 'messaging', 'event']:
                    if type_name in point.lower():
                        integration_types.add(type_name)
        
        type_score = min(len(integration_types) / 5, 0.4)
        
        return min(point_score + type_score, 1.0)

    def _calculate_repo_metrics(self, repo: Dict) -> float:
        """Calculate repository metrics score."""
        # Size-based metrics
        languages = extract_repo_data(repo, 'languages', {})
        total_bytes = sum(languages.values()) if languages else 0
        size_score = min(total_bytes / 1000000, 0.5)  # 1MB = 0.5 points
        
        # Language count
        language_count = len(languages) if languages else 0
        language_score = min(language_count / 10, 0.5)
        
        return min(size_score + language_score, 1.0)