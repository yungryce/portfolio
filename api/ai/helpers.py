import re
import logging
from typing import Dict, List, Any, Tuple, Type, TypeVar
from datetime import datetime

logger = logging.getLogger('portfolio.api')
T = TypeVar('T')

# ==============================================================================
# TOKEN AND TEXT PROCESSING
# ==============================================================================

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in text using simple estimation (no tiktoken dependency)."""
    # Simple estimation: ~4 characters per token for most models
    return len(text) // 4

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def normalize_string(value: Any) -> str:
    """Safely normalize any value to a lowercase string."""
    if value is None:
        return ""
    return str(value).lower()

def extract_keywords_from_text(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text, filtering by minimum length."""
    if not text:
        return []
    
    words = text.lower().split()
    return [word for word in words if len(word) >= min_length]

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate basic text similarity using word overlap."""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)

# ==============================================================================
# LANGUAGE DETECTION AND PROCESSING
# ==============================================================================

def process_language_data(repo: dict) -> dict:
    """
    Process language data for a repository to add calculated fields.
    
    Args:
        repo: Repository dictionary with 'languages' field
        
    Returns:
        dict: Repository with processed language data added
    """
    if not repo.get('languages'):
        # Ensure consistent structure even without languages
        repo['total_language_bytes'] = 0
        repo['language_percentages'] = {}
        repo['languages_sorted'] = []
        return repo
    
    languages = repo['languages']
    total_bytes = sum(languages.values())
    repo['total_language_bytes'] = total_bytes
    
    if total_bytes > 0:
        # Calculate language percentages
        repo['language_percentages'] = {
            lang: round((bytes_count / total_bytes) * 100, 1)
            for lang, bytes_count in languages.items()
        }
        
        # Sort languages by usage (most used first)
        repo['languages_sorted'] = sorted(
            languages.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
    else:
        repo['language_percentages'] = {}
        repo['languages_sorted'] = []
    
    return repo

def calculate_language_score(repo_languages: Dict[str, int], query_languages: List[str], 
                           total_bytes: int = 0) -> float:
    """
    Calculate enhanced language relevance score for a repository.
    
    Args:
        repo_languages: Dictionary of language names to byte counts
        query_languages: List of languages from user query
        total_bytes: Total bytes in repository
    
    Returns:
        Language relevance score (higher = more relevant)
    """
    if not query_languages or not repo_languages:
        return 0.0
    
    score = 0.0
    
    for query_lang in query_languages:
        query_lang_lower = query_lang.lower()
        
        for repo_lang, bytes_count in repo_languages.items():
            repo_lang_lower = repo_lang.lower()
            
            # Direct match
            if query_lang_lower == repo_lang_lower:
                percentage = (bytes_count / total_bytes * 100) if total_bytes > 0 else 0
                score += 10.0 + (percentage * 0.1)  # Base score + usage bonus
            # Partial match
            elif query_lang_lower in repo_lang_lower or repo_lang_lower in query_lang_lower:
                percentage = (bytes_count / total_bytes * 100) if total_bytes > 0 else 0
                score += 5.0 + (percentage * 0.05)  # Lower base score + usage bonus

    return score

def get_language_matches(repo_languages: Dict[str, int], query_languages: List[str], 
                         relevance_scores: Dict = None) -> List[Dict]:
    """
    Get matched languages between repository and user query with enhanced context.
    
    Args:
        repo_languages: Dictionary of repository languages and their byte counts
        query_languages: List of languages from user query
        relevance_scores: Optional dictionary of category relevance scores
        
    Returns:
        List of matched language dictionaries with enhanced context
    """
    matches = []
    language_relevance = relevance_scores.get('language', 0) if relevance_scores else 0
    
    for query_lang in query_languages:
        query_lang_lower = query_lang.lower()
        
        for repo_lang, bytes_count in repo_languages.items():
            repo_lang_lower = repo_lang.lower()
            
            # Check for matches
            if query_lang_lower == repo_lang_lower:
                matches.append({
                    'query_language': query_lang,
                    'repo_language': repo_lang,
                    'bytes_count': bytes_count,
                    'match_type': 'exact',
                    'confidence': 'high',
                    'relevance_score': language_relevance
                })
            elif query_lang_lower in repo_lang_lower or repo_lang_lower in query_lang_lower:
                matches.append({
                    'query_language': query_lang,
                    'repo_language': repo_lang,
                    'bytes_count': bytes_count,
                    'match_type': 'partial',
                    'confidence': 'medium',
                    'relevance_score': language_relevance * 0.7
                })
    
    return matches

# ==============================================================================
# COMPONENT AND CONTEXT PROCESSING
# ==============================================================================

def extract_component_info(comp_data: Any) -> List[Dict[str, str]]:
    """Extract component information from various data structures."""
    if isinstance(comp_data, dict):
        return [comp_data]
    elif isinstance(comp_data, list):
        return [item for item in comp_data if isinstance(item, dict)]
    return []

def safe_get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation."""
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    
    return current


# ==============================================================================
# Extracting Data from Repositories
# ==============================================================================


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




# ==============================================================================
# SEARCH TERM EXTRACTION
# ==============================================================================

def extract_context_terms(query: str, repositories: List[Dict] = None) -> Dict[str, List[str]]:
    """
    Dynamic search term extraction from repository contexts without hardcoded keywords.
    
    Args:
        query: User query string
        repositories: List of repository dictionaries with context
        
    Returns:
        Dictionary of categorized search terms
    """
    # Initialize result structure with empty lists
    found_terms = {
        'tech': [],
        'skills': [],
        'components': [],
        'project': [],
        'general': []
    }
    
    # Skip extraction if no repositories provided
    if not repositories:
        return found_terms
    
    # Extract all technical keywords from repositories
    tech_keywords = set()
    skill_keywords = set()
    component_keywords = set()
    project_keywords = set()

    for repo in repositories:
        repo_context = repo.get('repoContext', {})
        
        # Extract keywords by category
        tech_keywords.update(_extract_tech_keywords(repo_context.get('tech_stack', {})))
        skill_keywords.update(_extract_skill_keywords(repo_context.get('skill_manifest', {})))
        component_keywords.update(_extract_component_keywords(repo_context.get('components', {})))
        project_keywords.update(_extract_project_keywords(repo_context.get('project_identity', {})))
    
    # Process query to find matches
    query_words = re.findall(r'\b[a-zA-Z0-9_.-]+\b', query.lower())
    
    # Find matches in each category
    for word in query_words:
        if len(word) <= 2:
            continue
            
        # Check each category
        if word in tech_keywords and word not in found_terms['tech']:
            found_terms['tech'].append(word)
        elif word in skill_keywords and word not in found_terms['skills']:
            found_terms['skills'].append(word)
        elif word in component_keywords and word not in found_terms['components']:
            found_terms['components'].append(word)
        elif word in project_keywords and word not in found_terms['project']:
            found_terms['project'].append(word)
        elif len(word) > 3 and word not in found_terms['general']:
            found_terms['general'].append(word)
    
    return found_terms

def _extract_tech_keywords(tech_stack: Dict) -> set:
    """Extract technology keywords from tech stack."""
    keywords = set()
    
    for key in ['primary', 'secondary', 'key_libraries', 'development_tools']:
        if key in tech_stack and tech_stack[key]:
            keywords.update(tech.lower() for tech in tech_stack[key] if tech)
    return keywords

def _extract_skill_keywords(skill_manifest: Dict) -> set:
    """Extract skill keywords from skill manifest."""
    keywords = set()
    
    for key in ['technical', 'domain']:
        if key in skill_manifest and skill_manifest[key]:
            keywords.update(skill.lower() for skill in skill_manifest[key] if skill)
    
    return keywords

def _extract_component_keywords(components: Dict) -> set:
    """Extract component keywords from components data."""
    keywords = set()
    
    for comp_name, comp_data in components.items():
        keywords.add(comp_name.lower())
        # Handle different component data structures
        comp_items = extract_component_info(comp_data)
        
        for item in comp_items:
            for field in ['type', 'description', 'path', 'name', 'source']:
                value = item.get(field, '')
                if value:
                    keywords.update(extract_keywords_from_text(value))
    
    return keywords

def _extract_project_keywords(project_identity: Dict) -> set:
    """Extract project keywords from project identity."""
    keywords = set()
    
    for key in ['type', 'scope', 'name', 'description']:
        value = project_identity.get(key, '')
        if value:
            keywords.update(extract_keywords_from_text(value))
    
    return keywords

# ==============================================================================
# SCORING FUNCTIONS
# ==============================================================================

def calculate_tech_score(tech_stack: Dict, search_terms: Dict) -> float:
    """Calculate technology stack relevance score."""
    if not tech_stack or not search_terms:
        return 0.0
    
    score = 0.0
    tech_terms = search_terms.get('tech', [])
    
    # Check primary technologies (higher weight)
    primary_tech = tech_stack.get('primary', [])
    for tech in primary_tech:
        for term in tech_terms:
            if term.lower() in tech.lower():
                score += 5.0
    
    # Check secondary technologies
    secondary_tech = tech_stack.get('secondary', [])
    for tech in secondary_tech:
        for term in tech_terms:
            if term.lower() in tech.lower():
                score += 3.0
    
    # Check libraries and tools
    for key in ['key_libraries', 'development_tools']:
        items = tech_stack.get(key, [])
        for item in items:
            for term in tech_terms:
                if term.lower() in item.lower():
                    score += 2.0
    
    return score

def calculate_skill_score(skill_manifest: Dict, search_terms: Dict) -> float:
    """Calculate skill manifest relevance score."""
    if not skill_manifest or not search_terms:
        return 0.0
    
    score = 0.0
    skill_terms = search_terms.get('skills', [])
    
    # Check technical skills
    technical_skills = skill_manifest.get('technical', [])
    for skill in technical_skills:
        for term in skill_terms:
            if term.lower() in skill.lower():
                score += 4.0
    
    # Check domain skills
    domain_skills = skill_manifest.get('domain', [])
    for skill in domain_skills:
        for term in skill_terms:
            if term.lower() in skill.lower():
                score += 3.0
    
    return score

def calculate_component_score(components: Dict, search_terms: Dict) -> float:
    """Calculate component relevance score."""
    if not components or not search_terms:
        return 0.0
    
    score = 0.0
    component_terms = search_terms.get('components', [])
    
    for comp_name, comp_data in components.items():
        # Check component name
        for term in component_terms:
            if term.lower() in comp_name.lower():
                score += 3.0
        
        # Check component details
        comp_items = extract_component_info(comp_data)
        for item in comp_items:
            for field in ['type', 'description']:
                value = item.get(field, '')
                if value:
                    for term in component_terms:
                        if term.lower() in value.lower():
                            score += 2.0
    
    return score

def calculate_project_score(project_identity: Dict, search_terms: Dict) -> float:
    """Calculate project identity relevance score."""
    if not project_identity or not search_terms:
        return 0.0
    
    score = 0.0
    project_terms = search_terms.get('project', [])
    
    # Check project type and scope
    for key in ['type', 'scope']:
        value = project_identity.get(key, '')
        if value:
            for term in project_terms:
                if term.lower() in value.lower():
                    score += 4.0
    
    # Check project name and description
    for key in ['name', 'description']:
        value = project_identity.get(key, '')
        if value:
            for term in project_terms:
                if term.lower() in value.lower():
                    score += 3.0
    
    return score

def calculate_general_score(repo: Dict, search_terms: Dict) -> float:
    """Calculate general repository relevance score."""
    if not search_terms:
        return 0.0
    
    score = 0.0
    general_terms = search_terms.get('general', [])
    
    # Check repository name and description
    for field in ['name', 'description']:
        value = repo.get(field, '')
        if value:
            for term in general_terms:
                if term.lower() in value.lower():
                    score += 2.0
    
    # Check topics
    topics = repo.get('topics', [])
    for topic in topics:
        for term in general_terms:
            if term.lower() in topic.lower():
                score += 1.5
    
    return score

def calculate_bonus_score(repo: Dict, search_terms: Dict) -> float:
    """Calculate bonus points for special characteristics."""
    score = 0.0
    
    # Bonus for recent activity
    updated_at = repo.get('updated_at', '')
    if updated_at:
        try:
            from datetime import datetime
            updated_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            now = datetime.now().replace(tzinfo=updated_date.tzinfo)
            days_since_update = (now - updated_date).days
            
            # Bonus for recently updated repos
            if days_since_update < 30:
                score += 2.0
            elif days_since_update < 90:
                score += 1.0
        except:
            pass
    
    # Bonus for popular repositories
    stars = repo.get('stargazers_count', 0)
    if stars > 10:
        score += 1.0
    elif stars > 5:
        score += 0.5
    
    # Bonus for detailed documentation
    if repo.get('has_readme'):
        score += 0.5
    
    return score

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_language_distribution(repositories: List[Dict]) -> Dict[str, float]:
    """Get language distribution across all repositories."""
    language_totals = {}
    total_bytes = 0
    
    for repo in repositories:
        languages = repo.get('languages', {})
        for lang, bytes_count in languages.items():
            language_totals[lang] = language_totals.get(lang, 0) + bytes_count
            total_bytes += bytes_count
    
    if total_bytes == 0:
        return {}
    
    return {
        lang: round((bytes_count / total_bytes) * 100, 2)
        for lang, bytes_count in language_totals.items()
    }

def get_unique_technologies(repositories: List[Dict]) -> List[str]:
    """Get unique technologies across all repositories."""
    technologies = set()
    
    for repo in repositories:
        repo_context = repo.get('repoContext', {})
        tech_stack = repo_context.get('tech_stack', {})
        
        for key in ['primary', 'secondary', 'key_libraries', 'development_tools']:
            items = tech_stack.get(key, [])
            technologies.update(items)
    
    return sorted(list(technologies))

def get_combined_skills(repositories: List[Dict]) -> List[str]:
    """Get combined skills across all repositories."""
    skills = set()
    
    for repo in repositories:
        repo_context = repo.get('repoContext', {})
        skill_manifest = repo_context.get('skill_manifest', {})
        
        for key in ['technical', 'domain']:
            items = skill_manifest.get(key, [])
            skills.update(items)
    
    return sorted(list(skills))

def group_repos_by_type(repositories: List[Dict]) -> Dict[str, List[Dict]]:
    """Group repositories by project type."""
    grouped = {}
    
    for repo in repositories:
        repo_context = repo.get('repoContext', {})
        project_identity = repo_context.get('project_identity', {})
        project_type = project_identity.get('type', 'Unknown')
        
        if project_type not in grouped:
            grouped[project_type] = []
        grouped[project_type].append(repo)
    
    return grouped