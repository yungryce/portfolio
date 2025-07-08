import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from openai import OpenAI
from github_client import GitHubClient
from helpers import (
    count_tokens, 
    safe_get_nested_value, 
    truncate_text, 
    normalize_string,
    extract_keywords_from_text,
    validate_component_data,
    extract_component_info
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
    
    def _extract_tech_keywords(self, tech_stack: Dict) -> set:
        """Extract technology keywords from tech stack."""
        keywords = set()
        
        for key in ['primary', 'secondary', 'key_libraries', 'development_tools']:
            if key in tech_stack and tech_stack[key]:
                keywords.update(tech.lower() for tech in tech_stack[key] if tech)
        
        return keywords
    
    def _extract_skill_keywords(self, skill_manifest: Dict) -> set:
        """Extract skill keywords from skill manifest."""
        keywords = set()
        
        for key in ['technical', 'domain']:
            if key in skill_manifest and skill_manifest[key]:
                keywords.update(skill.lower() for skill in skill_manifest[key] if skill)
        
        return keywords
    
    def _extract_component_keywords(self, components: Dict) -> set:
        """Extract component keywords from components data."""
        keywords = set()
        
        for comp_name, comp_data in components.items():
            keywords.add(comp_name.lower())
            
            # Handle different component data structures
            comp_items = extract_component_info(comp_data)
            for item in comp_items:
                comp_type = item.get('type', '')
                comp_desc = item.get('description', '')
                
                if comp_type:
                    keywords.add(comp_type.lower())
                
                if comp_desc:
                    keywords.update(extract_keywords_from_text(comp_desc))
        
        return keywords
    
    def _extract_project_keywords(self, project_identity: Dict) -> set:
        """Extract project keywords from project identity."""
        keywords = set()
        
        for key in ['type', 'scope', 'name']:
            value = project_identity.get(key, '')
            if value:
                keywords.update(extract_keywords_from_text(value))
        
        return keywords
    
    def _find_matching_terms(self, query: str, keywords: set) -> List[str]:
        """Find matching terms between query and keywords."""
        query_lower = query.lower()
        return [term for term in keywords if term in query_lower]
    
    def _calculate_tech_score(self, tech_stack: Dict, search_terms: Dict) -> float:
        """Calculate technology stack relevance score."""
        score = 0.0
        
        # Primary tech stack scoring
        if 'primary' in tech_stack:
            primary_tech = [tech.lower() for tech in tech_stack['primary']]
            for term in search_terms.get('tech', []):
                if any(term in tech for tech in primary_tech):
                    score += 3.0
        
        # Secondary tech stack scoring
        if 'secondary' in tech_stack:
            secondary_tech = [tech.lower() for tech in tech_stack['secondary']]
            for term in search_terms.get('tech', []):
                if any(term in tech for tech in secondary_tech):
                    score += 2.0
        
        # Key libraries scoring
        if 'key_libraries' in tech_stack:
            key_libraries = [lib.lower() for lib in tech_stack['key_libraries']]
            for term in search_terms.get('tech', []):
                if any(term in lib for lib in key_libraries):
                    score += 2.5
        
        return score
    
    def _calculate_skill_score(self, skill_manifest: Dict, search_terms: Dict) -> float:
        """Calculate skill manifest relevance score."""
        score = 0.0
        
        # Technical skills scoring
        if 'technical' in skill_manifest:
            technical_skills = [skill.lower() for skill in skill_manifest['technical']]
            for term in search_terms.get('skills', []):
                if any(term in skill for skill in technical_skills):
                    score += 1.8
        
        # Domain skills scoring
        if 'domain' in skill_manifest:
            domain_skills = [skill.lower() for skill in skill_manifest['domain']]
            for term in search_terms.get('skills', []):
                if any(term in skill for skill in domain_skills):
                    score += 1.5
        
        return score
    
    def _calculate_component_score(self, components: Dict, search_terms: Dict) -> float:
        """Calculate component relevance score."""
        score = 0.0
        
        for comp_name, comp_data in components.items():
            comp_items = extract_component_info(comp_data)
            
            for item in comp_items:
                comp_type = normalize_string(item.get('type', ''))
                comp_desc = normalize_string(item.get('description', ''))
                comp_name_norm = normalize_string(comp_name)
                
                for term in search_terms.get('components', []):
                    if (term in comp_type or 
                        term in comp_desc or 
                        term in comp_name_norm):
                        score += 1.2
        
        return score
    
    def _calculate_project_score(self, project_identity: Dict, search_terms: Dict) -> float:
        """Calculate project identity relevance score."""
        score = 0.0
        
        project_name = normalize_string(project_identity.get('name', ''))
        project_type = normalize_string(project_identity.get('type', ''))
        project_desc = normalize_string(project_identity.get('description', ''))
        
        for term in search_terms.get('project', []):
            if (term in project_name or 
                term in project_type or 
                term in project_desc):
                score += 1.0
        
        return score
    
    def _calculate_general_score(self, repo: Dict, search_terms: Dict) -> float:
        """Calculate general terms relevance score."""
        score = 0.0
        
        repo_name = normalize_string(repo.get('name', ''))
        repo_description = normalize_string(repo.get('description', ''))
        repo_language = normalize_string(repo.get('language', ''))
        repo_topics = [normalize_string(topic) for topic in (repo.get('topics') or [])]
        
        for term in search_terms.get('general', []):
            if (term in repo_name or 
                term in repo_description or 
                term in repo_language or 
                any(term in topic for topic in repo_topics)):
                score += 0.8
        
        return score
    
    def _calculate_bonus_score(self, repo_context: Dict, repo: Dict) -> float:
        """Calculate bonus scores for comprehensive repos."""
        score = 0.0
        
        # Context completeness bonuses
        if repo_context:
            tech_stack = repo_context.get('tech_stack', {})
            skill_manifest = repo_context.get('skill_manifest', {})
            components = repo_context.get('components', {})
            project_identity = repo_context.get('project_identity', {})
            
            if tech_stack.get('primary'):
                score += 0.5
            if skill_manifest.get('technical'):
                score += 0.3
            if components:
                score += 0.2
            if project_identity.get('description'):
                score += 0.2
        
        # Recency bonus
        if repo.get('updated_at'):
            try:
                from datetime import datetime
                updated_date = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                days_since_update = (datetime.now().replace(tzinfo=updated_date.tzinfo) - updated_date).days
                if days_since_update < 365:
                    score += 0.5
            except:
                pass
        
        return score
    
    def _build_repo_summary(self, repo: Dict, index: int) -> List[str]:
        """Build a summary section for a repository."""
        repo_name = repo.get('name', 'Unknown')
        repo_context = repo.get('repoContext', {}) or {}
        
        repo_info = []
        repo_info.append(f"\n{'='*60}")
        repo_info.append(f"REPOSITORY {index}: {repo_name}")
        repo_info.append(f"{'='*60}")
        
        # Basic metadata
        if repo.get('description'):
            repo_info.append(f"Description: {truncate_text(repo['description'], 200)}")
        
        if repo.get('language'):
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
    
    def extract_context_search_terms(self, query: str, repositories: List[Dict] = None) -> Dict[str, List[str]]:
        """
        Dynamic search term extraction from repository contexts without hardcoded keywords.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries with context
            
        Returns:
            Dictionary of categorized search terms
        """
        # Initialize dynamic keyword collections
        dynamic_keywords = {
            'tech': set(),
            'skills': set(), 
            'components': set(),
            'project': set()
        }
        
        # Extract keywords from repository contexts if provided
        if repositories:
            for repo in repositories:
                repo_context = repo.get('repoContext', {})
                
                # Extract different types of keywords
                dynamic_keywords['tech'].update(
                    self._extract_tech_keywords(repo_context.get('tech_stack', {}))
                )
                dynamic_keywords['skills'].update(
                    self._extract_skill_keywords(repo_context.get('skill_manifest', {}))
                )
                dynamic_keywords['components'].update(
                    self._extract_component_keywords(repo_context.get('components', {}))
                )
                dynamic_keywords['project'].update(
                    self._extract_project_keywords(repo_context.get('project_identity', {}))
                )
        
        # Extract matching terms from query
        found_terms = {
            'tech': self._find_matching_terms(query, dynamic_keywords['tech']),
            'skills': self._find_matching_terms(query, dynamic_keywords['skills']),
            'components': self._find_matching_terms(query, dynamic_keywords['components']),
            'project': self._find_matching_terms(query, dynamic_keywords['project']),
            'general': []
        }
        
        # Extract general terms
        query_words = query.lower().split()
        all_known_terms = (dynamic_keywords['tech'] | 
                          dynamic_keywords['skills'] | 
                          dynamic_keywords['components'] | 
                          dynamic_keywords['project'])
        
        for word in query_words:
            if len(word) > 3 and word not in all_known_terms:
                found_terms['general'].append(word)

        logger.info(f"Extracted context search terms: {found_terms}")
        return found_terms
    
    def filter_repositories_with_terms(self, query: str, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Filter repositories using pre-extracted search terms (optimized version).
        
        Args:
            query: User query string
            repositories: List of repository dictionaries
            search_terms: Pre-extracted search terms
            
        Returns:
            List of filtered repositories sorted by relevance
        """
        logger.info(f"Filtering {len(repositories)} repositories using pre-extracted search terms")
        
        scored_repos = []
        
        for repo in repositories:
            score = self.calculate_repo_relevance_score(repo, query.lower(), search_terms)
            
            if score > 0:
                scored_repos.append({
                    'repo': repo,
                    'relevance_score': score,
                    'matched_categories': self.get_matched_categories(repo, search_terms)
                })
        
        # Sort by relevance score and return top repositories
        scored_repos.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Log scoring details
        logger.info(f"Top scoring repositories:")
        for i, item in enumerate(scored_repos[:5]):
            logger.info(f"  {i+1}. {item['repo']['name']}: {item['relevance_score']:.2f}")
        
        return [item['repo'] for item in scored_repos[:10]]
    
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
        
        # Calculate individual scores
        tech_score = self._calculate_tech_score(repo_context.get('tech_stack', {}), search_terms)
        skill_score = self._calculate_skill_score(repo_context.get('skill_manifest', {}), search_terms)
        component_score = self._calculate_component_score(repo_context.get('components', {}), search_terms)
        project_score = self._calculate_project_score(repo_context.get('project_identity', {}), search_terms)
        general_score = self._calculate_general_score(repo, search_terms)
        bonus_score = self._calculate_bonus_score(repo_context, repo)
        
        # Total score
        total_score = tech_score + skill_score + component_score + project_score + general_score + bonus_score
        
        logger.info(f"Calculated relevance score for repo '{repo_name}': {total_score:.2f}")
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
        Main method to process a query with complete pipeline.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries with context
            
        Returns:
            Tuple of (AI response, metadata dictionary)
        """
        logger.info(f"Processing query: {query[:100]}...")
        
        # Stage 1: Extract search terms
        search_terms = self.extract_context_search_terms(query.lower(), repositories)
        logger.info(f"Extracted search terms: {dict(search_terms)}")
        
        # Stage 2: Filter repositories
        relevant_repos = self.filter_repositories_with_terms(query, repositories, search_terms)
        logger.info(f"Found {len(relevant_repos)} relevant repositories")
        
        # Stage 3: Build enhanced context
        enhanced_context = self.build_enhanced_context(relevant_repos)
        
        # Stage 4: Query AI
        ai_response = self.query_ai_with_context(query, enhanced_context)
        
        # Build metadata
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
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
        
        return ai_response, metadata

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
