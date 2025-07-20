import tiktoken
import logging
import re
from data_filter import technical_terms_structured, extract_language_terms
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger('portfolio.api')

# ==============================================================================
# TOKEN AND TEXT PROCESSING
# ==============================================================================

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens in text using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to rough estimation
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
        
        # Direct language match (highest priority)
        for repo_lang, bytes_count in repo_languages.items():
            if query_lang_lower == repo_lang.lower():
                # Score based on percentage of codebase
                if total_bytes > 0:
                    percentage = (bytes_count / total_bytes) * 100
                    # Higher score for languages that make up more of the codebase
                    lang_score = min(percentage / 5, 20)  # Max 20 points per direct match
                    score += lang_score
                else:
                    score += 10  # Default score if no byte data
                break
        
        # Partial language match (lower priority)
        else:
            for repo_lang, bytes_count in repo_languages.items():
                if query_lang_lower in repo_lang.lower() or repo_lang.lower() in query_lang_lower:
                    if total_bytes > 0:
                        percentage = (bytes_count / total_bytes) * 100
                        lang_score = min(percentage / 10, 5)  # Max 5 points for partial match
                        score += lang_score
                    else:
                        score += 3  # Reduced score for partial matches
                    break

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
        
        # Check for direct matches first
        for repo_lang, bytes_count in repo_languages.items():
            if query_lang_lower == repo_lang.lower():
                # Add enhanced confidence based on relevance score
                confidence = "high"
                if relevance_scores:
                    if language_relevance > 10:
                        confidence = "very high"
                    elif language_relevance > 5:
                        confidence = "high"
                    else:
                        confidence = "medium"
                
                matches.append({
                    'query_language': query_lang,
                    'repo_language': repo_lang,
                    'match_type': 'direct',
                    'bytes': bytes_count,
                    'confidence': confidence
                })
                break
        else:
            # Check for partial matches
            for repo_lang, bytes_count in repo_languages.items():
                if query_lang_lower in repo_lang.lower() or repo_lang.lower() in query_lang_lower:
                    # Add enhanced confidence based on relevance score
                    confidence = "medium"
                    if relevance_scores:
                        if language_relevance > 8:
                            confidence = "high"
                        elif language_relevance > 3:
                            confidence = "medium"
                        else:
                            confidence = "low"
                    
                    matches.append({
                        'query_language': query_lang,
                        'repo_language': repo_lang,
                        'match_type': 'partial',
                        'bytes': bytes_count,
                        'confidence': confidence
                    })
                    break
    
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
# SCORING FUNCTIONS (moved from original implementation)
# ==============================================================================

def calculate_tech_score(tech_stack: Dict, search_terms: Dict) -> float:
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

def calculate_skill_score(skill_manifest: Dict, search_terms: Dict) -> float:
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

def calculate_component_score(components: Dict, search_terms: Dict) -> float:
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

def calculate_project_score(project_identity: Dict, search_terms: Dict) -> float:
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

def calculate_general_score(repo: Dict, search_terms: Dict) -> float:
    """Calculate general terms relevance score."""
    score = 0.0
    
    repo_name = normalize_string(repo.get('name', ''))
    repo_description = normalize_string(repo.get('description', ''))
    repo_language = normalize_string(repo.get('language', ''))
    repo_topics = repo.get('topics', [])
    
    for term in search_terms.get('general', []):
        if (term in repo_name or 
            term in repo_description or 
            term in repo_language or 
            any(term in normalize_string(topic) for topic in repo_topics)):
            score += 0.8
    
    return score

def calculate_bonus_score(repo: Dict, search_terms: Dict) -> float:
    """Calculate comprehensive bonus score using repository relevance scores."""
    score = 0.0
    repo_context = repo.get('repoContext', {})
    relevance_scores = repo.get('relevance_scores', {})
    
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
    
    # Enhanced scoring based on relevance_scores
    if relevance_scores:
        # Cross-category scoring
        non_zero_categories = sum(1 for cat_score in relevance_scores.values() if cat_score > 0)
        if non_zero_categories >= 3:
            score += 0.8
        elif non_zero_categories == 2:
            score += 0.4
        
        # High-relevance bonus
        high_scores = sum(1 for cat_score in relevance_scores.values() if cat_score > 5.0)
        if high_scores >= 2:
            score += 1.0
        elif high_scores == 1:
            score += 0.5
        
        # Language-specific scoring
        language_score = relevance_scores.get('language', 0)
        if language_score > 10:
            score += 0.9
        elif language_score > 5:
            score += 0.6
        elif language_score > 0:
            score += 0.3
    
    # Recency bonus
    if repo.get('updated_at'):
        try:
            updated_date = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
            days_since_update = (datetime.now().replace(tzinfo=updated_date.tzinfo) - updated_date).days
            if days_since_update < 90:
                score += 0.7
            elif days_since_update < 365:
                score += 0.4
        except:
            pass
    
    return score

