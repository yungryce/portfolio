import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from github_client import GitHubClient
from data_fiter import extract_language_terms
from ai_helpers import (
    # Text processing
    count_tokens, truncate_text, normalize_string,
    
    # Language processing
    calculate_language_score, get_language_matches,
    process_language_data,
    
    # Component processing
    extract_component_info, validate_component_data, trim_processed_repo,
    
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

# Use the existing logger from function_app.py
logger = logging.getLogger('portfolio.api')


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
    
    def _filter_by_language_priority(self, repositories: List[Dict]) -> List[Dict]:
        """
        Filter repositories with language-first priority.

        Args:
            repositories: List of repository dictionaries (already processed)

        Returns:
            List of repositories sorted by language relevance.
        """
        # Filter repositories with a positive language relevance score
        language_scored_repos = [
            repo for repo in repositories if repo.get('language_relevance_score', 0) > 0
        ]

        # Sort by language relevance score (descending)
        language_scored_repos.sort(key=lambda x: x['language_relevance_score'], reverse=True)

        # Log top results
        logger.info("Language-first filtering results:")
        for i, repo in enumerate(language_scored_repos[:5]):
            matched_languages = repo.get('matched_query_languages', [])
            lang_info = f"Languages: {[m['repo_lang'] for m in matched_languages]}" if matched_languages else "No language match"
            logger.info(f"  {i+1}. {repo['name']}: Language Relevance={repo['language_relevance_score']:.2f} {lang_info}")

        return language_scored_repos


    def _build_repo_summary(self, repo: Dict, index: int) -> List[str]:
        """Enhanced repository summary with prioritized language information."""
        repo_name = repo.get('name', 'Unknown')
        repo_context = repo.get('repoContext', {}) or {}
        
        repo_info = []
        repo_info.append(f"\n{'='*60}")
        repo_info.append(f"REPOSITORY {index}: {repo_name}")
        repo_info.append(f"{'='*60}")
        
        # Basic metadata
        if repo.get('description'):
            repo_info.append(f"Description: {truncate_text(repo['description'], 200)}")
        
        # Enhanced language information (prioritized)
        if repo.get('languages'):
            languages = repo['languages']
            total_bytes = repo.get('total_language_bytes', 0)
            language_percentages = repo.get('language_percentages', {})
            
            if total_bytes > 0:
                # Use pre-sorted languages if available
                languages_sorted = repo.get('languages_sorted', [])
                if not languages_sorted:
                    languages_sorted = sorted(languages.items(), key=lambda x: x[1], reverse=True)
                
                repo_info.append(f"Programming Languages (by usage):")
                for i, (lang, bytes_count) in enumerate(languages_sorted[:5]):  # Top 5 languages
                    percentage = language_percentages.get(lang, 0)
                    repo_info.append(f"  {i+1}. {lang}: {percentage}% ({bytes_count:,} bytes)")
            else:
                repo_info.append(f"Primary Language: {repo.get('language', 'Not specified')}")
        elif repo.get('language'):
            repo_info.append(f"Primary Language: {repo['language']}")
        
        if repo.get('topics'):
            repo_info.append(f"Topics: {', '.join(repo['topics'][:5])}")
        
        # Technology stack
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            repo_info.append(f"\nTECHNOLOGY STACK:")
            for key, label in [('primary', 'Primary'), ('secondary', 'Secondary'), ('key_libraries', 'Key Libraries')]:
                if tech_stack.get(key):
                    repo_info.append(f"  {label}: {', '.join(tech_stack[key][:5])}")
        
        # Skills
        skill_manifest = repo_context.get('skill_manifest', {})
        if skill_manifest:
            repo_info.append(f"\nSKILLS DEMONSTRATED:")
            if skill_manifest.get('technical'):
                repo_info.append(f"  Technical: {', '.join(skill_manifest['technical'][:5])}")
            if skill_manifest.get('domain'):
                repo_info.append(f"  Domain: {', '.join(skill_manifest['domain'][:3])}")
        
        # Project details
        project_identity = repo_context.get('project_identity', {})
        if project_identity:
            repo_info.append(f"\nPROJECT DETAILS:")
            for key, label in [('type', 'Type'), ('scope', 'Scope'), ('description', 'Description')]:
                if project_identity.get(key):
                    value = truncate_text(project_identity[key], 150) if key == 'description' else project_identity[key]
                    repo_info.append(f"  {label}: {value}")
        
        # Components (limited)
        components = repo_context.get('components', {})
        if components:
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
        
        logger.debug(f"Matched categories for repo '{repo.get('name', 'Unknown')}': {matched}")
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
                repo_name = repo.get('name', 'Unknown')
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

        # Combine language terms into the search terms dictionary
        search_terms['languages'] = language_terms
        logger.info(f"Extracted search terms: {dict(search_terms)}")
        
        # Stage 2: Process repositories with enhanced filtering
        start_time = time.time()
        processed_repos = self.process_languages(repositories, search_terms)
        relevant_repos = self.filter_repositories_with_terms(processed_repos, search_terms)
        processing_time = time.time() - start_time
        
        logger.info(f"Repository processing completed in {processing_time:.2f}s")

        # Fallback: if no strong matches found, get top repos by difficulty and bytes
        if len(relevant_repos) == 0:
            logger.info("No strong matches found, using fallback strategy")
            # Add fallback repo with message 
            relevant_repos = self._get_fallback_repositories(repositories, 5)
            fallback_message = "No direct matches found for your query, but here are some notable repositories that may be relevant:"
        else:
            fallback_message = "I found the following repositories that match your query:"
        
        logger.info(f"Found {len(relevant_repos)} relevant repositories")
        
        # Stage 3: Build enhanced context
        enhanced_context = self.build_enhanced_context(relevant_repos)
        
        # Stage 4: Query AI with fallback message if needed
        if fallback_message:
            query_with_context = f"{query}\n\nNote: {fallback_message}"
            ai_response = self.query_ai_with_context(query_with_context, enhanced_context)
        else:
            ai_response = self.query_ai_with_context(query, enhanced_context)
            
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
            "detected_languages": language_terms,  # FIXED: Use language_terms instead
            "language_based_filtering": len(language_terms) > 0,  # FIXED: Use language_terms
            "fallback_used": fallback_message is not None,
            "search_terms_found": {
                "tech": len(search_terms.get('tech', [])),
                "skills": len(search_terms.get('skills', [])),
                "components": len(search_terms.get('components', [])),
                "project": len(search_terms.get('project', [])),
                "general": len(search_terms.get('general', []))
            },
            "repositories_analyzed": [repo.get('name', 'Unknown') for repo in relevant_repos[:5]],
            "context_size_chars": len(enhanced_context),
            "processing_time_seconds": round(processing_time, 2)
        }
        
        # Add language-specific metadata if applicable
        if language_terms and relevant_repos:  # FIXED: Use language_terms
            language_matches = []
            for repo in relevant_repos[:5]:  # Limit to top 5 for efficiency
                repo_languages = repo.get('languages', {})
                total_bytes = repo.get('total_language_bytes', 0)
                
                # Get detailed language matches with error handling
                try:
                    # FIXED: Pass relevance_scores to get_language_matches
                    matches = get_language_matches(
                        repo_languages, 
                        language_terms,
                        repo.get('relevance_scores', {})
                    )
                    
                    if matches:
                        language_matches.append({
                            "repository": repo.get('name', 'Unknown'),
                            "language_matches": matches,
                            "total_languages": len(repo_languages),
                            "primary_language": repo.get('language', 'Unknown'),
                            "total_bytes": total_bytes
                        })
                except Exception as e:
                    logger.error(f"Error getting language matches for {repo.get('name', 'Unknown')}: {str(e)}")
            
            metadata["language_matches"] = language_matches
            
            # Add detailed score breakdown for top matches
            if relevant_repos:
                top_matches_details = []
                for repo in relevant_repos[:3]:
                    scores = repo.get('relevance_scores', {})
                    top_matches_details.append({
                        "name": repo.get('name', 'Unknown'),
                        "total_score": repo.get('total_relevance_score', 0),
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


    def process_languages(self, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Process repositories with language data and optional query language filtering.
        
        Args:
            repositories: List of repository dictionaries
            query_languages: Optional list of programming languages from query for filtering
            
        Returns:
            List of repositories with AI-specific enhancements and optional language filtering
        """
        processed_repos = []
        language_terms = search_terms.get('languages', [])

        for repo in repositories:
            # Create a copy to avoid modifying the original
            processed_repo = repo.copy()
            
            # add a function that trims down processed_repo
            processed_repo = trim_processed_repo(processed_repo)

            # Add language processing data
            processed_repo = process_language_data(processed_repo)
            
            # Calculate relevance scores for each category in search_terms
            repo_languages = processed_repo.get('languages', {})
            total_bytes = processed_repo.get('total_language_bytes', 0)
            
            # Calculate all category scores
            language_score = calculate_language_score(repo_languages, language_terms, total_bytes)
            tech_score = calculate_tech_score(processed_repo.get('repoContext', {}).get('tech_stack', {}), search_terms)
            skill_score = calculate_skill_score(processed_repo.get('repoContext', {}).get('skill_manifest', {}), search_terms)
            component_score = calculate_component_score(processed_repo.get('repoContext', {}).get('components', {}), search_terms)
            project_score = calculate_project_score(processed_repo.get('repoContext', {}).get('project_identity', {}), search_terms)
            general_score = calculate_general_score(processed_repo, search_terms)
        
            # Store category-specific scores in a structured format
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
                language_terms, 
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
            
            processed_repos.append(processed_repo)
        
        # Sort repositories by total relevance score
        processed_repos.sort(key=lambda x: x.get('total_relevance_score', 0), reverse=True)
        logger.debug(f"Total Processed length {len(processed_repos)} repositories with relevance scores")
        logger.info(f"Top 3 processed repositories by total relevance score:")
        for i, repo in enumerate(processed_repos[:3]):
            scores = repo.get('relevance_scores', {})
            logger.info(f"  {i+1}. {repo.get('name', 'Unknown')}: "
                        f"Total={repo.get('total_relevance_score', 0):.2f} "
                        f"[lang:{scores.get('language', 0):.1f}, "
                        f"tech:{scores.get('tech', 0):.1f}, "
                        f"skill:{scores.get('skill', 0):.1f}, "
                        f"comp:{scores.get('component', 0):.1f}, "
                        f"proj:{scores.get('project', 0):.1f}, "
                        f"gen:{scores.get('general', 0):.1f}, "
                        f"bonus:{scores.get('bonus', 0):.1f}]")
        return processed_repos

    def filter_repositories_with_terms(self, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Enhanced filtering with language-based prioritization.
        """
        # Use language terms already extracted in search_terms
        language_terms = search_terms.get('languages', [])

        # Decide filtering strategy
        if language_terms and any(repo.get('language_relevance_score', 0) > 0 for repo in repositories):
            logger.info(f"Using language-first filtering for: {language_terms}")
            
            # Just filter by positive language score and take top results
            language_filtered = [
                repo for repo in repositories if repo.get('language_relevance_score', 0) > 0
            ]
            
            # Only re-sort if we really want language to be the primary factor
            language_filtered.sort(key=lambda x: x.get('language_relevance_score', 0), reverse=True)
            
            # FIXED: Safe access to matched_languages with explicit error handling
            for repo in language_filtered:
                matched_languages = repo.get('matched_query_languages', [])
                
                # Defensive approach to extract language information
                language_names = []
                try:
                    if matched_languages:
                        for m in matched_languages:
                            if isinstance(m, dict):
                                # Check for various possible key names
                                if 'repo_language' in m:
                                    language_names.append(m['repo_language'])
                                elif 'language' in m:
                                    language_names.append(m['language'])
                                else:
                                    # Add all keys for debugging
                                    language_names.append(f"Unknown({','.join(m.keys()) if m else 'empty'})")
                            else:
                                language_names.append(str(m))
                except Exception as e:
                    logger.error(f"Error processing language info: {str(e)}")
                    language_names = ["Error processing languages"]
                
                # Format language info safely
                lang_info = f"Languages: {language_names}" if language_names else "No language match"
            
            logger.info("Language-first filtering results:")
            return language_filtered[:10]  # Limit to top 10
        else:
            logger.info("Using traditional relevance filtering")
            # Just take top repos by total relevance (already sorted)
            return repositories[:10]  # Limit to top 10

    def _filter_by_relevance_only(self, query: str, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """Filter repositories using traditional relevance scoring only."""
        scored_repos = []
        
        for repo in repositories:
            score = self.calculate_repo_relevance_score(repo, query.lower(), search_terms)
            
            if score > 0:
                scored_repos.append({
                    'repo': repo,
                    'relevance_score': score,
                    'matched_categories': self.get_matched_categories(repo, search_terms)
                })
        
        # Sort by relevance score
        scored_repos.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Log results
        logger.info(f"Traditional filtering results:")
        for i, item in enumerate(scored_repos[:5]):
            logger.info(f"  {i+1}. {item['repo']['name']}: {item['relevance_score']:.2f}")
        
        return [item['repo'] for item in scored_repos[:10]]

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
            # Calculate difficulty score
            difficulty_data = self.calculate_difficulty_score(repo)
            difficulty_score = difficulty_data.get('score', 0)
            
            # Get total language bytes
            total_bytes = repo.get('total_language_bytes', 0)
            if total_bytes == 0:
                # Calculate if not already processed
                languages = repo.get('languages', {})
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
            logger.info(f"  {i+1}. {item['repo']['name']}: "
                    f"Combined={item['combined_score']:.1f} "
                    f"(Difficulty={item['difficulty_score']}, Bytes={item['total_bytes']})")
        
        return [item['repo'] for item in scored_repos[:limit]]


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
    
    def calculate_repo_relevance_score(self, repo: Dict, query: str, search_terms: Dict) -> float:
        """
        Calculate relevance score for a repository based on query using repo context structure.
        
        Args:
            repo: Repository dictionary with context
            query: User query string
            search_terms: Pre-extracted search terms
            
        Returns:
            Relevance score as float
        """
        repo_context = repo.get('repoContext', {}) or {}
        repo_name = normalize_string(repo.get('name', ''))
        
        # Calculate individual scores using helper functions
        tech_score = calculate_tech_score(repo_context.get('tech_stack', {}), search_terms)
        skill_score = calculate_skill_score(repo_context.get('skill_manifest', {}), search_terms)
        component_score = calculate_component_score(repo_context.get('components', {}), search_terms)
        project_score = calculate_project_score(repo_context.get('project_identity', {}), search_terms)
        general_score = calculate_general_score(repo, search_terms)
        bonus_score = calculate_bonus_score(repo, search_terms)
        
        # Total score
        total_score = tech_score + skill_score + component_score + project_score + general_score + bonus_score
        
        logger.debug(f"Calculated relevance score for repo '{repo_name}': {total_score:.2f}")
        return total_score
    
    

    def calculate_difficulty_score(self, repo: Dict) -> Dict[str, Any]:
        """
        Calculate difficulty score for a repository using enhanced context analysis.
        
        Args:
            repo: Repository dictionary with context
            
        Returns:
            Dictionary containing difficulty rating, score, and reasoning
        """
        if not repo:
            return {
                'difficulty': 'unknown',
                'score': 0,
                'confidence': 0.0,
                'reasoning': ['No repository data available']
            }
        
        repo_context = repo.get('repoContext', {})
        difficulty_score = 0
        reasoning = []
        confidence_factors = []
        
        # 1. Technology Stack Complexity (0-30 points)
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            tech_score, tech_reasoning, tech_confidence = self._calculate_tech_difficulty(tech_stack)
            difficulty_score += tech_score
            reasoning.extend(tech_reasoning)
            confidence_factors.append(tech_confidence)
        
        # 2. Architecture Complexity (0-25 points)
        components = repo_context.get('components', {})
        if components:
            arch_score, arch_reasoning, arch_confidence = self._calculate_architecture_difficulty(components)
            difficulty_score += arch_score
            reasoning.extend(arch_reasoning)
            confidence_factors.append(arch_confidence)
        
        # 3. Skill Requirements (0-20 points)
        skill_manifest = repo_context.get('skill_manifest', {})
        if skill_manifest:
            skill_score, skill_reasoning, skill_confidence = self._calculate_skill_difficulty(skill_manifest)
            difficulty_score += skill_score
            reasoning.extend(skill_reasoning)
            confidence_factors.append(skill_confidence)
        
        # 4. Project Scope (0-15 points)
        project_identity = repo_context.get('project_identity', {})
        if project_identity:
            project_score, project_reasoning, project_confidence = self._calculate_project_difficulty(project_identity)
            difficulty_score += project_score
            reasoning.extend(project_reasoning)
            confidence_factors.append(project_confidence)
        
        # 5. Repository Metrics (0-10 points)
        metrics_score, metrics_reasoning, metrics_confidence = self._calculate_metrics_difficulty(repo)
        difficulty_score += metrics_score
        reasoning.extend(metrics_reasoning)
        confidence_factors.append(metrics_confidence)
        
        # Calculate final metrics
        normalized_score = min(difficulty_score, 100)
        avg_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.3
        
        # Determine difficulty level
        if normalized_score >= 75:
            difficulty_level = 'expert'
        elif normalized_score >= 50:
            difficulty_level = 'advanced'
        elif normalized_score >= 25:
            difficulty_level = 'intermediate'
        else:
            difficulty_level = 'beginner'
        
        return {
            'difficulty': difficulty_level,
            'score': normalized_score,
            'confidence': round(avg_confidence, 2),
            'reasoning': reasoning,
            'breakdown': {
                'technology_complexity': min(tech_score if 'tech_score' in locals() else 0, 30),
                'architecture_complexity': min(arch_score if 'arch_score' in locals() else 0, 25),
                'skill_requirements': min(skill_score if 'skill_score' in locals() else 0, 20),
                'project_scope': min(project_score if 'project_score' in locals() else 0, 15),
                'repository_metrics': min(metrics_score if 'metrics_score' in locals() else 0, 10)
            }
        }
    
    def _calculate_tech_difficulty(self, tech_stack: Dict) -> Tuple[int, List[str], float]:
        """Calculate technology difficulty score."""
        score = 0
        reasoning = []
        confidence = 0.8
        
        # Advanced and intermediate technology lists
        advanced_techs = {
            'kubernetes', 'docker', 'microservices', 'distributed', 'blockchain', 
            'machine learning', 'ai', 'tensorflow', 'pytorch', 'react native', 'flutter'
        }
        intermediate_techs = {
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 
            'spring', 'laravel', 'mongodb', 'postgresql', 'redis'
        }
        
        # Primary technologies
        primary_tech = tech_stack.get('primary', [])
        if primary_tech:
            tech_complexity = 0
            for tech in primary_tech:
                tech_lower = tech.lower()
                if any(adv in tech_lower for adv in advanced_techs):
                    tech_complexity += 3
                elif any(inter in tech_lower for inter in intermediate_techs):
                    tech_complexity += 2
                else:
                    tech_complexity += 1
            
            score += min(tech_complexity, 15)
            reasoning.append(f"Primary technologies: {', '.join(primary_tech)}")
        
        # Secondary technologies and libraries
        secondary_tech = tech_stack.get('secondary', [])
        key_libraries = tech_stack.get('key_libraries', [])
        
        if secondary_tech or key_libraries:
            additional_complexity = len(secondary_tech) + len(key_libraries)
            score += min(additional_complexity, 10)
            reasoning.append(f"Additional technologies: {additional_complexity} tools/libraries")
        
        # Development tools
        dev_tools = tech_stack.get('development_tools', [])
        if dev_tools:
            tools_complexity = len(dev_tools)
            score += min(tools_complexity, 5)
            reasoning.append(f"Development tools: {tools_complexity} specialized tools")
        
        return score, reasoning, confidence
    
    def _calculate_architecture_difficulty(self, components: Dict) -> Tuple[int, List[str], float]:
        """Calculate architecture difficulty score."""
        score = 0
        reasoning = []
        confidence = 0.9
        
        # Number of components
        component_count = len(components)
        score += min(component_count * 2, 10)
        
        # Component complexity
        complex_components = 0
        complex_types = {'service', 'api', 'microservice', 'database', 'cache', 'queue'}
        
        for comp_name, comp_data in components.items():
            comp_items = extract_component_info(comp_data)
            for item in comp_items:
                comp_type = normalize_string(item.get('type', ''))
                if any(term in comp_type for term in complex_types):
                    complex_components += 1
                    break  # Count component only once
        
        score += min(complex_components * 3, 15)
        reasoning.append(f"Architecture: {component_count} components, {complex_components} complex components")
        
        return score, reasoning, confidence
    
    def _calculate_skill_difficulty(self, skill_manifest: Dict) -> Tuple[int, List[str], float]:
        """Calculate skill difficulty score."""
        score = 0
        reasoning = []
        confidence = 0.7
        
        technical_skills = skill_manifest.get('technical', [])
        domain_skills = skill_manifest.get('domain', [])
        
        if technical_skills or domain_skills:
            skill_complexity = len(technical_skills) + len(domain_skills)
            score += min(skill_complexity, 15)
            
            # Advanced skills
            advanced_skills = {
                'devops', 'cloud', 'aws', 'azure', 'gcp', 'security', 
                'performance', 'scalability', 'testing', 'ci/cd'
            }
            advanced_count = sum(
                1 for skill in technical_skills + domain_skills
                if any(adv in skill.lower() for adv in advanced_skills)
            )
            
            score += min(advanced_count, 5)
            reasoning.append(f"Skills: {skill_complexity} total skills, {advanced_count} advanced skills")
        
        return score, reasoning, confidence
    
    def _calculate_project_difficulty(self, project_identity: Dict) -> Tuple[int, List[str], float]:
        """Calculate project difficulty score."""
        score = 0
        reasoning = []
        confidence = 0.6
        
        project_type = normalize_string(project_identity.get('type', ''))
        project_scope = normalize_string(project_identity.get('scope', ''))
        
        # Project type complexity
        complex_types = {'full-stack', 'enterprise', 'distributed', 'real-time'}
        medium_types = {'web application', 'api', 'service'}
        
        if any(term in project_type for term in complex_types):
            score += 5
            reasoning.append(f"Complex project type: {project_type}")
        elif any(term in project_type for term in medium_types):
            score += 3
        
        # Project scope complexity
        complex_scopes = {'large', 'complex', 'enterprise', 'production'}
        medium_scopes = {'medium', 'moderate'}
        
        if any(term in project_scope for term in complex_scopes):
            score += 5
            reasoning.append(f"Complex project scope: {project_scope}")
        elif any(term in project_scope for term in medium_scopes):
            score += 2
        
        return score, reasoning, confidence
    
    def _calculate_metrics_difficulty(self, repo: Dict) -> Tuple[int, List[str], float]:
        """Calculate repository metrics difficulty score."""
        score = 0
        reasoning = []
        confidence = 0.5
        
        repo_language = repo.get('language', '')
        repo_size = repo.get('size', 0)
        
        # Size complexity
        if repo_size > 50000:
            score += 5
            reasoning.append(f"Large repository size: {repo_size} KB")
        elif repo_size > 10000:
            score += 2
        
        # Language complexity
        complex_languages = {'c', 'c++', 'rust', 'go', 'scala', 'haskell', 'assembly'}
        if repo_language and repo_language.lower() in complex_languages:
            score += 3
            reasoning.append(f"Complex primary language: {repo_language}")
        
        return score, reasoning, confidence
    
    def get_difficulty_rating(self, repo: Dict) -> str:
        """
        Get simple difficulty rating for a repository.
        
        Args:
            repo: Repository dictionary with context
            
        Returns:
            String difficulty rating ('beginner', 'intermediate', 'advanced', 'expert')
        """
        difficulty_data = self.calculate_difficulty_score(repo)
        return difficulty_data['difficulty']
    


