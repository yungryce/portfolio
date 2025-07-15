import logging
import os
import time
import math
from typing import Any, Dict, List, Optional, Union, TypeVar, Type, Tuple
from openai import OpenAI
from github_client import GitHubClient
from data_fiter import extract_language_terms, advanced_skills, complexity_indicators
from ai_helpers import (
    # Text processing
    count_tokens, truncate_text, normalize_string,
    
    # Language processing
    calculate_language_score, get_language_matches,
    process_language_data,
    
    # Component processing
    extract_component_info, validate_component_data,
    
    # Keyword extraction
    extract_tech_keywords, extract_skill_keywords, extract_component_keywords,
    extract_project_keywords, find_matching_terms,
    
    # Search and scoring
    extract_context_terms, calculate_tech_score, calculate_skill_score,
    calculate_component_score, calculate_project_score, calculate_general_score,
    calculate_bonus_score,
    
    # Difficulty calculation
    calculate_tech_difficulty, calculate_architecture_difficulty,
    calculate_skill_difficulty, calculate_project_difficulty,
    calculate_metrics_difficulty
)
from repo_utils import extract_repo_data

# Use the existing logger from function_app.py
logger = logging.getLogger('portfolio.api')
T = TypeVar('T')

class AIAssistant:
    """
    Modular AI Assistant class for portfolio query processing with repository context management.
    Handles search term extraction, repository filtering, and enhanced AI query processing.
    """
    
    # Class constants
    MAX_TOKENS = 8000  # Safe limit for context window
    MAX_CONTEXT_CHARS = 25000  # Character limit for context
    DEFAULT_REPO_LIMIT = 5  # Default number of repos to include
    
    def __init__(self, github_token: str = None, username: str = 'yungryce'):
        """
        Initialize the AI Assistant with GitHub client and configuration.
        
        Args:
            github_token: GitHub API token for repository access
            username: GitHub username for repository queries
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Initialize GitHub client
        self.gh_client = self._initialize_github_client()
        
        # Initialize OpenAI client for Groq
        self.openai_client = self._initialize_openai_client()
        
        logger.info(f"AI Assistant initialized for user: {self.username}")
    
    def _initialize_github_client(self) -> Optional[GitHubClient]:
        """Initialize GitHub client with error handling."""
        if self.github_token:
            return GitHubClient(token=self.github_token, username=self.username)
        else:
            logger.warning("GitHub token not configured - file fetching disabled")
            return None
    
    def _initialize_openai_client(self) -> OpenAI:
        """Initialize OpenAI client for Groq with validation."""
        if not self.groq_api_key:
            logger.error("GROQ_API_KEY not configured in environment")
            raise ValueError("GROQ_API_KEY environment variable is not set")
        
        return OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        ) 
    def _build_repo_summary(self, repo: Dict, index: int) -> List[str]:
        """Enhanced repository summary with prioritized language information."""
        repo_name = extract_repo_data(repo, 'name', 'Unknown')
        
        repo_info = []
        repo_info.append(f"\n{'='*60}")
        repo_info.append(f"REPOSITORY {index}: {repo_name}")
        repo_info.append(f"{'='*60}")
        
        # Basic metadata
        if description := extract_repo_data(repo, 'description'):
            repo_info.append(f"Description: {truncate_text(description, 200)}")
        
        # Enhanced language information (prioritized)
        if languages := extract_repo_data(repo, 'languages', {}):
            total_bytes = extract_repo_data(repo, 'total_language_bytes', 0)
            language_percentages = extract_repo_data(repo, 'language_percentages', {})
            
            if total_bytes > 0:
                # Use pre-sorted languages if available
                languages_sorted = extract_repo_data(repo, 'languages_sorted', [])
                if not languages_sorted:
                    languages_sorted = sorted(languages.items(), key=lambda x: x[1], reverse=True)
                
                repo_info.append(f"Programming Languages (by usage):")
                for i, (lang, bytes_count) in enumerate(languages_sorted[:5]):  # Top 5 languages
                    percentage = language_percentages.get(lang, 0)
                    repo_info.append(f"  {i+1}. {lang}: {percentage}% ({bytes_count:,} bytes)")
            else:
                repo_info.append(f"Primary Language: {extract_repo_data(repo, 'language', 'Not specified')}")
        elif primary_lang := extract_repo_data(repo, 'language'):
            repo_info.append(f"Primary Language: {primary_lang}")
    
        if topics := extract_repo_data(repo, 'topics', []):
            repo_info.append(f"Topics: {', '.join(topics[:5])}")
        
        # Technology stack
        if tech_stack := extract_repo_data(repo, 'repoContext.tech_stack', {}):
            repo_info.append(f"\nTECHNOLOGY STACK:")
            for key, label in [('primary', 'Primary'), ('secondary', 'Secondary'), ('key_libraries', 'Key Libraries')]:
                if tech_items := extract_repo_data(tech_stack, key, []):
                    repo_info.append(f"  {label}: {', '.join(tech_items[:5])}")
        
        # Skills
        if skill_manifest := extract_repo_data(repo, 'repoContext.skill_manifest', {}):
            repo_info.append(f"\nSKILLS DEMONSTRATED:")
            if technical_skills := extract_repo_data(skill_manifest, 'technical', []):
                repo_info.append(f"  Technical: {', '.join(technical_skills[:5])}")
            if domain_skills := extract_repo_data(skill_manifest, 'domain', []):
                repo_info.append(f"  Domain: {', '.join(domain_skills[:3])}")
        
        # Project details - FIX: Use extract_repo_data instead of undefined repo_context
        if project_identity := extract_repo_data(repo, 'repoContext.project_identity', {}):
            repo_info.append(f"\nPROJECT DETAILS:")
            for key, label in [('type', 'Type'), ('scope', 'Scope'), ('description', 'Description')]:
                if project_identity.get(key):
                    value = truncate_text(project_identity[key], 150) if key == 'description' else project_identity[key]
                    repo_info.append(f"  {label}: {value}")
        
        # Components (limited) - FIX: Use extract_repo_data instead of undefined repo_context
        if components := extract_repo_data(repo, 'repoContext.components', {}):
            repo_info.append(f"\nARCHITECTURE COMPONENTS:")
            for comp_name, comp_data in list(components.items())[:3]:  # Limit to 3
                comp_items = extract_component_info(comp_data)
                for idx, item in enumerate(comp_items[:2]):  # Max 2 per component
                    comp_type = item.get('type', 'Unknown')
                    comp_desc = truncate_text(item.get('description', 'No description'), 100)
                    display_name = f"{comp_name}[{idx}]" if len(comp_items) > 1 else comp_name
                    repo_info.append(f"  {display_name} ({comp_type}): {comp_desc}")
        
        return repo_info

    def _add_context_files(self, repo_name: str, repo_info: List[str], max_chars: int = 1000) -> None:
        """Add context files to repo info with character limits."""
        if not self.gh_client:
            return
        
        additional_files = self.fetch_repository_context_files(repo_name)
        
        file_configs = [
            ('readme', 'README CONTENT', 800),
            ('skills_index', 'SKILLS INDEX', 500),
            ('architecture', 'ARCHITECTURE DOCUMENTATION', 500),
            ('project_manifest', 'PROJECT MANIFEST', 500)
        ]
        
        for file_key, section_name, char_limit in file_configs:
            if additional_files.get(file_key):
                repo_info.append(f"\n{section_name}:")
                content = truncate_text(additional_files[file_key], char_limit)
                repo_info.append(content)
    
    
    def get_matched_categories(self, repo: Dict, search_terms: Dict) -> List[str]:
        """
        Get categories that matched for this repository (for debugging/explanation).
        
        Args:
            repo: Repository dictionary
            search_terms: Pre-extracted search terms
            
        Returns:
            List of matched category names
        """
        matched = []
        
        # Check what categories had matches
        category_mapping = {
            'tech': 'technology',
            'skills': 'skills',
            'components': 'components',
            'project': 'project_type'
        }
        
        for key, display_name in category_mapping.items():
            if search_terms.get(key):
                matched.append(display_name)
        
        repo_name = extract_repo_data(repo, 'name', 'Unknown')
        logger.debug(f"Matched categories for repo '{repo_name}': {matched}")
        return matched
    
    def fetch_repository_context_files(self, repo_name: str) -> Dict[str, str]:
        """
        Fetch additional context files for a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            Dictionary of context files content
        """
        if not self.gh_client:
            logger.warning("GitHub client not available for file fetching")
            return {}
        
        context_files = {}
        
        # Define the files we want to fetch
        file_mappings = {
            'readme': ['README.md', 'readme.md', 'Readme.md'],
            'skills_index': ['SKILLS-INDEX.md', 'skills-index.md', 'Skills-Index.md'],
            'architecture': ['ARCHITECTURE.md', 'architecture.md', 'Architecture.md', 'ARCHITECHURE.md'],
            'project_manifest': ['PROJECT-MANIFEST.md', 'project-manifest.md', 'Project-Manifest.md']
        }
        
        # Try to fetch each type of file
        for file_type, possible_names in file_mappings.items():
            for file_name in possible_names:
                try:
                    file_content = self.gh_client.get_file_content(self.username, repo_name, file_name)
                    if file_content and isinstance(file_content, str):
                        context_files[file_type] = file_content
                        logger.debug(f"Fetched {file_name} for {repo_name}")
                        break
                except Exception as e:
                    logger.debug(f"Failed to fetch {file_name} from {repo_name}: {str(e)}")
                    continue
        
        return context_files
    
    def build_enhanced_context(self, repositories: List[Dict], max_chars: int = None) -> str:
        """
        Build comprehensive context for AI from filtered repositories with size limits.
        
        Args:
            repositories: List of filtered repository dictionaries
            max_chars: Maximum characters for context (default: class constant)
            
        Returns:
            Enhanced context string for AI processing
        """
        if max_chars is None:
            max_chars = self.MAX_CONTEXT_CHARS
        
        context_parts = []
        current_length = 0
        
        if repositories:
            summary = f"Found {len(repositories)} relevant repositories for your query."
            context_parts.append(summary)
            current_length += len(summary)
            
            # Process repositories with size constraints
            for i, repo in enumerate(repositories[:self.DEFAULT_REPO_LIMIT], 1):
                repo_name = extract_repo_data(repo, 'name', 'Unknown')
                logger.info(f"Building context for repository: {repo_name}")
                
                # Build repository summary
                repo_info = self._build_repo_summary(repo, i)
                
                # Add context files if space allows
                if current_length < max_chars * 0.7:  # Reserve 30% for context files
                    self._add_context_files(repo_name, repo_info, 600)
                
                repo_text = '\n'.join(repo_info)
                
                # Check if adding this repo would exceed limit
                if current_length + len(repo_text) > max_chars:
                    logger.warning(f"Context size limit reached. Stopping at {i-1} repositories.")
                    break
                
                context_parts.append(repo_text)
                current_length += len(repo_text)
        
        enhanced_context = '\n\n'.join(context_parts)
        logger.info(f"Built enhanced context with {len(enhanced_context)} characters for {len(repositories)} repositories")
        
        return enhanced_context
    
    
    def process_query(self, query: str, repositories: List[Dict]) -> Tuple[str, Dict]:
        """
        Enhanced query processing with language-first filtering.
        
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
        logger.info(f"Extracted search terms: {dict(search_terms)}")
        
        # Stage 2: Process repositories with unified scoring (replaces both process_languages and filter_repositories_with_terms)
        relevant_repos = self.process_languages(repositories, search_terms, limit=10)
        
        # Fallback: if no strong matches found, get top repos by difficulty and bytes
        fallback_used = len(relevant_repos) == 0
        if fallback_used:
            logger.info("No strong matches found, using fallback strategy")
            relevant_repos = self._get_fallback_repositories(repositories, 5)
        
        logger.info(f"Found {len(relevant_repos)} relevant repositories")
        
        # Stage 3: Build enhanced context
        enhanced_context = self.build_enhanced_context(relevant_repos)
        
        # Stage 4: Query AI (context message will be handled in query_ai_with_context based on fallback_used)
        ai_response = self.query_ai_with_context(query, enhanced_context, fallback_used)
            
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
            "detected_languages": language_terms,
            "language_based_filtering": len(language_terms) > 0,
            "fallback_used": fallback_used,
            "search_terms_found": {
                "tech": len(search_terms.get('tech', [])),
                "skills": len(search_terms.get('skills', [])),
                "components": len(search_terms.get('components', [])),
                "project": len(search_terms.get('project', [])),
                "general": len(search_terms.get('general', []))
            },
            "repositories_analyzed": [extract_repo_data(repo, 'name', 'Unknown') for repo in relevant_repos[:5]],
            "context_size_chars": len(enhanced_context),
        }
        
        # Add language-specific metadata if applicable
        if language_terms and relevant_repos: 
            language_matches = []
            for repo in relevant_repos[:5]:  # Limit to top 5 for efficiency
                repo_languages = extract_repo_data(repo, 'languages', {})
                total_bytes = extract_repo_data(repo, 'total_language_bytes', 0)

                # Get detailed language matches with error handling
                try:
                    # FIXED: Pass relevance_scores to get_language_matches
                    matches = get_language_matches(
                        repo_languages, 
                        language_terms,
                        extract_repo_data(repo, 'relevance_scores', {})
                    )
                    
                    if matches:
                        language_matches.append({
                            "repository": extract_repo_data(repo, 'name', 'Unknown'),
                            "language_matches": matches,
                            "total_languages": len(repo_languages),
                            "primary_language": extract_repo_data(repo, 'language', 'Unknown'),
                            "total_bytes": total_bytes
                        })
                except Exception as e:
                    logger.error(f"Error getting language matches for {extract_repo_data(repo, 'name', 'Unknown')}: {str(e)}")

            metadata["language_matches"] = language_matches
            
            # Add detailed score breakdown for top matches
            if relevant_repos:
                top_matches_details = []
                for repo in relevant_repos[:3]:
                    scores = extract_repo_data(repo, 'relevance_scores', {})
                    top_matches_details.append({
                        "name": extract_repo_data(repo, 'name', 'Unknown'),
                        "total_score": extract_repo_data(repo, 'total_relevance_score', 0),
                        "score_breakdown": {
                            "language": scores.get('language', 0),
                            "tech": scores.get('tech', 0),
                            "skill": scores.get('skill', 0),
                            "component": scores.get('component', 0),
                            "project": scores.get('project', 0),
                            "general": scores.get('general', 0),
                            "bonus": scores.get('bonus', 0)
                        }
                    })
                metadata["top_matches_details"] = top_matches_details
        
        return ai_response, metadata

    def process_languages(self, repositories: List[Dict], search_terms: Dict, limit: int = 10) -> List[Dict]:
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
            
            # Calculate repository difficulty Scoring
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
        logger.info(f"Top {min(3, len(limited_repos))} repositories by total relevance score:")
        
        for i, repo in enumerate(limited_repos[:3]):
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


    def _get_fallback_repositories(self, repositories: List[Dict], limit: int = 5) -> List[Dict]:
        """
        Get fallback repositories based on difficulty and total bytes when no strong matches found.
        
        Args:
            repositories: List of all repositories
            limit: Maximum number of repositories to return
            
        Returns:
            List of top repositories by difficulty and size
        """
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
        logger.debug(f"Calculating difficulty score for {extract_repo_data(repo, 'name', 'Unknown')}")
        difficulty_data = self.calculate_difficulty_score(repo)
        
        # Cache the result in the repository object
        repo['difficulty_analysis'] = difficulty_data
        
        return difficulty_data

    def query_ai_with_context(self, query: str, enhanced_context: str) -> str:
        """
        Query the AI assistant with enhanced context and size management.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            
        Returns:
            AI response string
        """
        logger.info("Starting enhanced AI assistant query")
        
        request_id = f"req-{int(time.time())}"
        logger.info(f"Request ID: {request_id} - Processing enhanced query: {query[:100]}...")
        
        # Create system message with size management
        system_template = """You are an AI assistant that helps users understand Chigbu Joshua's portfolio projects.
Use the following comprehensive information about the GitHub repositories to answer questions.

PORTFOLIO REPOSITORY ANALYSIS:
{context}

When answering:
1. Reference specific projects, technologies, and demonstrated skills from the detailed context above
2. Highlight architecture patterns, components, and technical implementations when relevant
3. Draw connections between different projects and technologies
4. Use the README content to understand project goals and features
5. Reference the skills indexes and project manifests to identify competencies
6. Organize your response with clear sections and specific examples
7. Be specific about technical implementations and challenges solved

Respond specifically and accurately about the projects listed above.
If asked about a specific technology, framework, or skill, reference the detailed context provided.
Use the architecture documentation and project manifests to give comprehensive answers about project scope and complexity.
"""
        
        system_message = system_template.format(context=enhanced_context)
        
        # Check token count and truncate if necessary
        total_tokens = count_tokens(system_message + query)
        if total_tokens > self.MAX_TOKENS:
            logger.warning(f"Context too large ({total_tokens} tokens). Truncating...")
            # Truncate context to fit within limits
            available_chars = self.MAX_CONTEXT_CHARS - len(system_template) - len(query) - 500  # Buffer
            enhanced_context = truncate_text(enhanced_context, available_chars)
            system_message = system_template.format(context=enhanced_context)
        
        logger.info(f"Request ID: {request_id} - Created system prompt ({len(system_message)} chars)")
        
        # Call Groq API
        try:
            api_start = time.time()
            response = self.openai_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query}
                ],
                max_tokens=2048,
                temperature=0.3
            )
            api_time = time.time() - api_start
            
            if response.choices and len(response.choices) > 0:
                answer = response.choices[0].message.content
                logger.info(f"Request ID: {request_id} - Received AI response in {api_time:.2f}s ({len(answer)} chars)")
                return answer
            else:
                logger.error(f"Request ID: {request_id} - Empty response from AI API")
                return "I'm sorry, I couldn't generate a response based on the portfolio information."
                
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Error calling AI API: {str(e)}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
    
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
        
        # Use the comprehensive advanced skills set from data_fiter.py
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
        """Calculate deployment workflow complexity."""
        workflow = extract_repo_data(repo, 'repoContext.deployment_workflow', [])
        
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