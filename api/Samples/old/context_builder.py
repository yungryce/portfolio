import logging
from typing import Dict, List, Optional
from github_client import GitHubClient
from .helpers import (
    truncate_text,
    extract_component_info
)

# Use the existing logger from function_app.py
logger = logging.getLogger('portfolio.api')


def extract_repo_data(repo: Dict, path: str, default: any = None, as_type: type = None) -> any:
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


class ContextBuilder:
    """
    Handles building context for AI queries from repository data.
    Responsible for creating comprehensive context strings with size management.
    """
    
    # Context size constants
    MAX_CONTEXT_CHARS = 25000  # Character limit for context
    DEFAULT_REPO_LIMIT = 5  # Default number of repos to include
    
    def __init__(self, github_client: Optional[GitHubClient] = None, username: str = 'yungryce'):
        """
        Initialize the ContextBuilder.
        
        Args:
            github_client: GitHub client for fetching repository files
            username: GitHub username for repository queries
        """
        self.gh_client = github_client
        self.username = username
        logger.info(f"ContextBuilder initialized for user: {self.username}")
    
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
                
                # Build repository summary
                repo_info = self._build_repo_summary(repo, i, repo_name)
                
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
    
    def _build_repo_summary(self, repo: Dict, index: int, repo_name: str) -> List[str]:
        """
        Enhanced repository summary with prioritized language information.
        
        Args:
            repo: Repository dictionary
            index: Repository index number
            repo_name: Name of the repository
            
        Returns:
            List of strings containing repository summary information
        """
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
        
        # Project details
        if project_identity := extract_repo_data(repo, 'repoContext.project_identity', {}):
            repo_info.append(f"\nPROJECT DETAILS:")
            for key, label in [('type', 'Type'), ('scope', 'Scope'), ('description', 'Description')]:
                if project_identity.get(key):
                    value = truncate_text(project_identity[key], 150) if key == 'description' else project_identity[key]
                    repo_info.append(f"  {label}: {value}")
        
        # Components (limited)
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
        """
        Add context files to repo info with character limits.
        
        Args:
            repo_name: Name of the repository
            repo_info: List to append context file information to
            max_chars: Maximum characters allowed for context files
        """
        if not self.gh_client:
            return
        
        additional_files = self._fetch_repository_context_files(repo_name)
        
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
    
    def _fetch_repository_context_files(self, repo_name: str) -> Dict[str, str]:
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
            'architecture': ['ARCHITECTURE.md', 'architecture.md', 'Architecture.md', 'ARCHITECHURE.md']
            # 'project_manifest': ['PROJECT-MANIFEST.md', 'project-manifest.md', 'Project-Manifest.md']
        }
        
        # Track fetch attempts for logging
        attempted_files = []
        
        # Try to fetch each type of file
        for file_type, possible_names in file_mappings.items():
            for file_name in possible_names:
                try:
                    attempted_files.append(file_name)
                    file_content = self.gh_client.get_file_content(self.username, repo_name, file_name)
                    if file_content and isinstance(file_content, str):
                        context_files[file_type] = file_content
                        content_length = len(file_content)
                        logger.info(f"Fetched {file_name} for {repo_name} ({content_length} chars)")
                        break
                except Exception as e:
                    logger.debug(f"Failed to fetch {file_name} from {repo_name}: {str(e)}")
                    continue
        
        # Log summary of fetched files
        if context_files:
            file_details = [f"{ftype} ({len(content)} chars)" for ftype, content in context_files.items()]
            logger.info(f"Repository {repo_name}: Found {len(context_files)} context files: {', '.join(file_details)}")
            total_chars = sum(len(content) for content in context_files.values())
            logger.debug(f"Repository {repo_name}: Total context size: {total_chars} characters")
        else:
            logger.warning(f"Repository {repo_name}: No context files found after attempting {len(set(attempted_files))} file variations")
        
        return context_files
    
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