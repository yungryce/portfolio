import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from github_client import GitHubClient
from ai_helpers import (
    # Text processing
    count_tokens, truncate_text, normalize_string,
    
    # Language processing
    extract_language_terms, calculate_language_score, get_language_matches,
    process_language_data,
    
    # Component processing
    extract_component_info, validate_component_data,
    
    # Keyword extraction
    extract_tech_keywords, extract_skill_keywords, extract_component_keywords,
    extract_project_keywords, find_matching_terms,
    
    # Search and scoring
    extract_context_search_terms, calculate_tech_score, calculate_skill_score,
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
    
    def _filter_by_language_priority(self, query: str, repositories: List[Dict], 
                                   search_terms: Dict, query_languages: List[str]) -> List[Dict]:
        """Filter repositories with language-first priority."""
        language_scored_repos = []
        
        for repo in repositories:
            # Get language data
            languages = repo.get('languages', {})
            total_bytes = repo.get('total_language_bytes', 0)
            
            # Calculate language score (primary factor)
            language_score = calculate_language_score(languages, query_languages, total_bytes)
            
            # Calculate traditional relevance score (secondary factor)
            traditional_score = self.calculate_repo_relevance_score(repo, query.lower(), search_terms)
            
            # Language-first scoring: language matches are heavily weighted
            if language_score > 0:
                # Base score from language match, boosted by relevance
                combined_score = (language_score * 10) + (traditional_score * 0.3)
                
                # Get matched languages for metadata
                matched_languages = []
                for lang in query_languages:
                    for repo_lang in languages.keys():
                        if lang.lower() == repo_lang.lower():
                            matched_languages.append({
                                'query_lang': lang,
                                'repo_lang': repo_lang,
                                'bytes': languages[repo_lang],
                                'percentage': repo.get('language_percentages', {}).get(repo_lang, 0)
                            })
                            break
                        elif lang.lower() in repo_lang.lower() or repo_lang.lower() in lang.lower():
                            matched_languages.append({
                                'query_lang': lang,
                                'repo_lang': repo_lang,
                                'bytes': languages[repo_lang],
                                'percentage': repo.get('language_percentages', {}).get(repo_lang, 0)
                            })
                            break
                
                # Sort matched languages by bytes (most used first)
                matched_languages.sort(key=lambda x: x['bytes'], reverse=True)
                
                language_scored_repos.append({
                    'repo': repo,
                    'combined_score': combined_score,
                    'language_score': language_score,
                    'traditional_score': traditional_score,
                    'matched_languages': matched_languages,
                    'has_language_match': True
                })
            else:
                # No language match, use traditional scoring with penalty
                combined_score = traditional_score * 0.1  # Heavily penalized
                
                if combined_score > 0:  # Only include if there's some relevance
                    language_scored_repos.append({
                        'repo': repo,
                        'combined_score': combined_score,
                        'language_score': 0,
                        'traditional_score': traditional_score,
                        'matched_languages': [],
                        'has_language_match': False
                    })
        
        # Sort by combined score (language-first)
        language_scored_repos.sort(key=lambda x: (x['has_language_match'], x['combined_score']), reverse=True)
        
        # Log top results
        logger.info(f"Language-first filtering results:")
        for i, item in enumerate(language_scored_repos[:5]):
            repo = item['repo']
            lang_info = f"Languages: {[m['repo_lang'] for m in item['matched_languages']]}" if item['matched_languages'] else "No language match"
            logger.info(f"  {i+1}. {repo['name']}: Combined={item['combined_score']:.2f} "
                       f"(Lang={item['language_score']:.2f}, Traditional={item['traditional_score']:.2f}) "
                       f"{lang_info}")
        
        return [item['repo'] for item in language_scored_repos[:10]]


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
    
    def filter_repositories_with_terms(self, query: str, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Enhanced filtering with language-based prioritization.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries
            search_terms: Pre-extracted search terms
            
        Returns:
            List of filtered repositories sorted by relevance (language-first if applicable)
        """
        logger.info(f"Filtering {len(repositories)} repositories using enhanced language-aware filtering")
        
        # Extract language terms from query
        query_languages = extract_language_terms(query)
        
        if query_languages:
            logger.info(f"Detected programming languages in query: {query_languages}")
            return self._filter_by_language_priority(query, repositories, search_terms, query_languages)
        else:
            logger.info("No programming languages detected, using traditional filtering")
            return self._filter_by_relevance_only(query, repositories, search_terms)


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
        bonus_score = calculate_bonus_score(repo_context, repo)
        
        # Total score
        total_score = tech_score + skill_score + component_score + project_score + general_score + bonus_score
        
        logger.debug(f"Calculated relevance score for repo '{repo_name}': {total_score:.2f}")
        return total_score
    
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
        query = query.lower()
        
        # Process repositories for AI usage (adds language calculations)
        processed_repos = self.get_repositories_for_ai(username=self.username)
        
        # Extract language terms early for metadata
        query_languages = extract_language_terms(query)
        
        # Stage 1: Extract search terms
        search_terms = extract_context_search_terms(query, processed_repos)
        logger.info(f"Extracted search terms: {dict(search_terms)}")
        return search_terms, []
        # Stage 2: Enhanced filtering with language-first priority
        relevant_repos = self.filter_repositories_with_terms(query, processed_repos, search_terms)
        logger.info(f"Found {len(relevant_repos)} relevant repositories")
        
        # Stage 3: Build enhanced context
        enhanced_context = self.build_enhanced_context(relevant_repos)
        
        # Stage 4: Query AI
        ai_response = self.query_ai_with_context(query, enhanced_context)
        
        # Build enhanced metadata
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
            "detected_languages": query_languages,
            "language_based_filtering": len(query_languages) > 0,
            "search_terms_found": {
                "tech": len(search_terms.get('tech', [])),
                "skills": len(search_terms.get('skills', [])),
                "components": len(search_terms.get('components', [])),
                "project": len(search_terms.get('project', [])),
                "general": len(search_terms.get('general', []))
            },
            "repositories_analyzed": [repo.get('name', 'Unknown') for repo in relevant_repos[:5]],
            "context_size_chars": len(enhanced_context)
        }
        
        # Add language-specific metadata if applicable
        if query_languages:
            language_matches = []
            for repo in relevant_repos[:5]:
                repo_languages = repo.get('languages', {})
                total_bytes = repo.get('total_language_bytes', 0)
                
                # Get detailed language matches
                from api.fa_helpers import get_language_matches
                matches = get_language_matches(repo_languages, query_languages)
                
                if matches:
                    language_matches.append({
                        "repository": repo['name'],
                        "language_matches": matches,
                        "total_languages": len(repo_languages),
                        "primary_language": repo.get('language', 'Unknown'),
                        "total_bytes": total_bytes
                    })
            
            metadata["language_matches"] = language_matches
        
        return ai_response, metadata

    def get_repositories_for_ai(self, username: str = None, include_languages: bool = True) -> List[Dict]:
        """
        Convenience method to get repositories optimized for AI Assistant.
        This combines data fetching with AI-specific processing.
        
        Args:
            username: GitHub username
            include_languages: Whether to include language data
            
        Returns:
            list: Repositories with AI-specific enhancements
        """
        if not self.gh_client:
            logger.error("GitHub client not available for repository fetching")
            return []
        
        username = username or self.username
        
        # Get raw repository data
        repos = self.gh_client.get_all_repos_with_context(username, include_languages)

        processed_repos = []
        
        for repo in repos:
            # Create a copy to avoid modifying the original
            processed_repo = repo.copy()
            
            # Process language data using helper function
            processed_repo = process_language_data(processed_repo)
            
            # Add other AI-specific enhancements here if needed
            # For example, you could add:
            # - Calculated complexity scores
            # - Normalized tech stack data
            # - Extracted keywords
            # - Difficulty ratings
            
            processed_repos.append(processed_repo)
        logger.debug(f"-----------------------------processed_repos: {len(processed_repos)}")
        return processed_repos

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
    


