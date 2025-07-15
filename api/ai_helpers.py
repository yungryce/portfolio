import tiktoken
import logging
import re
from data_fiter import technical_terms_structured, extract_language_terms
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
    This is a utility function for processing repository language data.
    
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
    # logger.debug(f"Processing languages for repo {repo.get('name', 'unknown')}: {languages} (Total bytes: {total_bytes})")
    
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

def validate_component_data(comp_data: Any) -> bool:
    """Validate component data structure."""
    if isinstance(comp_data, dict):
        return True
    elif isinstance(comp_data, list):
        return all(isinstance(item, dict) for item in comp_data)
    return False

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
# KEYWORD EXTRACTION FUNCTIONS
# ==============================================================================

def extract_tech_keywords(tech_stack: Dict) -> set:
    """Extract technology keywords from tech stack."""
    keywords = set()
    
    for key in ['primary', 'secondary', 'key_libraries', 'development_tools']:
        if key in tech_stack and tech_stack[key]:
            keywords.update(tech.lower() for tech in tech_stack[key] if tech)
    return keywords

def extract_skill_keywords(skill_manifest: Dict) -> set:
    """Extract skill keywords from skill manifest."""
    keywords = set()
    
    for key in ['technical', 'domain']:
        if key in skill_manifest and skill_manifest[key]:
            keywords.update(skill.lower() for skill in skill_manifest[key] if skill)
    
    return keywords

def extract_component_keywords(components: Dict) -> set:
    """Extract component keywords from components data."""
    keywords = set()
    
    for comp_name, comp_data in components.items():
        keywords.add(comp_name)
        # Handle different component data structures
        comp_items = extract_component_info(comp_data)
        
        for item in comp_items:
            comp_type = item.get('type', '')
            comp_desc = item.get('description', '')
            comp_path = item.get('path', '')
            comp_source = item.get('source', '')
            comp_name = item.get('name', '')
            comp_key_files = item.get('key_files', [])
            comp_dependencies = item.get('dependencies', [])

            if comp_type:
                keywords.add(comp_type.lower())
            
            if comp_desc:
                keywords.update(extract_keywords_from_text(comp_desc))
                
            if comp_path:
                keywords.add(comp_path.lower())
                
            if comp_name:
                keywords.add(comp_name.lower())
                
            if comp_source:
                keywords.add(comp_source.lower())
            if comp_key_files:
                for file in comp_key_files:
                    if isinstance(file, str):
                        keywords.add(file.lower())
                    elif isinstance(file, dict):
                        keywords.update(extract_keywords_from_text(file.get('name', '')))
            if comp_dependencies:
                for dep in comp_dependencies:
                    if isinstance(dep, str):
                        keywords.add(dep.lower())
                    elif isinstance(dep, dict):
                        keywords.update(extract_keywords_from_text(dep.get('name', '')))
    
    return keywords

def extract_project_keywords(project_identity: Dict) -> set:
    """Extract project keywords from project identity."""
    keywords = set()
    
    for key in ['type', 'scope', 'name', 'description']:
        value = project_identity.get(key, '')
        if value:
            keywords.update(extract_keywords_from_text(value))
    
    return keywords

def find_matching_terms(query: str, keywords: set) -> List[str]:
    """Find matching terms between query and keywords using regex for exact matching."""
    query_lower = query.lower()
    found_terms = []
    
    for term in keywords:
        # Use regex to match whole words
        if re.search(rf'\b{re.escape(term)}\b', query_lower):
            found_terms.append(term)

    return found_terms




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
        'general': []
    }
    
    # Skip extraction if no repositories provided
    if not repositories:
        return found_terms
    
    # Extract all technical keywords from repositories into a single set
    tech_keywords = set()

    for repo in repositories:
        repo_context = repo.get('repoContext', {})
        
        # Extract all technical keywords
        tech_keywords.update(extract_tech_keywords(repo_context.get('tech_stack', {})))
        tech_keywords.update(extract_skill_keywords(repo_context.get('skill_manifest', {})))
        tech_keywords.update(extract_component_keywords(repo_context.get('components', {})))
        tech_keywords.update(extract_project_keywords(repo_context.get('project_identity', {})))
    
    # Process compound terms to extract individual components
    expanded_keywords = set(tech_keywords)

    for term in tech_keywords:
        # Handle dot-separated terms (like filenames)
        if '.' in term:
            parts = term.split('.')
            for part in parts:
                if len(part) > 2 and part in technical_terms_structured["technical_keywords"]:
                    expanded_keywords.add(part)
                    
            # Add file extension if present
            if len(parts) > 1 and parts[-1] in technical_terms_structured["file_extensions"]:
                expanded_keywords.add(parts[-1])
        
        # Handle hyphenated terms
        elif '-' in term:
            for part in term.split('-'):
                if len(part) > 2 and part in technical_terms_structured["technical_keywords"]:
                    expanded_keywords.add(part)
        
        # Handle space-separated terms
        elif ' ' in term:
            for part in term.split():
                if len(part) > 2 and part in technical_terms_structured["technical_keywords"]:
                    expanded_keywords.add(part)
    
    # Filter keywords for meaningful terms
    filtered_keywords = {
        term for term in expanded_keywords if is_meaningful_term(term)
    }
    logger.debug(f"===--: Extracted technical keywords: {filtered_keywords}")
    
    # Process the query to find matches
    query_words = re.findall(r'\b[a-zA-Z0-9_-]+\b', query.lower())
    
    # First pass: Find direct matches with keywords
    for word in query_words:
        # Skip very short terms
        if len(word) <= 2:
            continue
            
        # Check if it's a technical keyword or in our filtered keywords
        if word in technical_terms_structured["technical_keywords"] or word in filtered_keywords:
            if word not in found_terms['tech']:
                found_terms['tech'].append(word)
    
    # Second pass: Add remaining terms to general
    for word in query_words:
        if len(word) > 3 and word not in found_terms['tech'] and word not in found_terms['general']:
            found_terms['general'].append(word)
    
    return found_terms

def is_meaningful_term(term: str) -> bool:
    """
    Optimized function to determine if a term is meaningful using technical patterns.
    Improved to handle filenames, hyphenated terms, and special technical formats.
    
    Args:
        term: The term to evaluate
        
    Returns:
        bool: True if the term is considered meaningful
    """
    # Early return for empty terms
    if not term:
        return False
    
    # Check if the entire term is a recognized programming language
    if term in extract_language_terms(term):
        return True
    
    # Check for file extension pattern (e.g., app.py, index.html)
    parts = term.split('.')
    if len(parts) > 1 and parts[-1] in technical_terms_structured["file_extensions"]:
        return True
    
    # Check for hyphenated technical terms (e.g., react-router)
    if '-' in term:
        hyphen_parts = term.split('-')
        for part in hyphen_parts:
            if part in technical_terms_structured["technical_keywords"]:
                return True
    
    # Continue with regular space-separated term processing
    term_parts = term.split()
    
    # No parts (empty string or just whitespace)
    if not term_parts:
        return False
    
    # Flag to track if we found a technical keyword in the term
    has_technical_keyword = False
    has_version_pattern = False
    
    # Check each part for technical keywords and version patterns
    for part in term_parts:
        # Skip the term if any part is a stop word
        if part in technical_terms_structured["stop_words"]:
            return False
        
        # Check if part is a technical keyword
        if part in technical_terms_structured["technical_keywords"]:
            has_technical_keyword = True
        
        # Check if part is a file extension
        if part in technical_terms_structured["file_extensions"]:
            has_technical_keyword = True  # Treat file extensions like technical keywords
        
        # Check if part matches a version pattern
        for pattern in technical_terms_structured["version_patterns"]:
            if pattern.match(part):
                has_version_pattern = True
                break
    
    # If term has only one part and it's just a version number, reject it
    if len(term_parts) == 1 and has_version_pattern and not has_technical_keyword:
        return False
    
    # Accept the term if it has a technical keyword
    if has_technical_keyword:
        return True
    
    # If we reach here, the term wasn't found to be meaningful
    return False

# ==============================================================================
# SCORING FUNCTIONS
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
    repo_topics = normalize_string(repo.get('topics') or [])
    
    for term in search_terms.get('general', []):
        if (term in repo_name or 
            term in repo_description or 
            term in repo_language or 
            any(term in topic for topic in repo_topics)):
            score += 0.8
    
    return score

def calculate_bonus_score(repo: Dict, search_terms: Dict) -> float:
    """
    Calculate comprehensive bonus score using repository relevance scores.
    
    Args:
        repo: Repository dictionary with all metadata and relevance scores
        search_terms: Dictionary of search terms by category
        
    Returns:
        Total bonus score
    """
    score = 0.0
    repo_context = repo.get('repoContext', {})
    relevance_scores = repo.get('relevance_scores', {})
    
    # Context completeness bonuses (keep these as they're about repo quality)
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
    
    # Enhanced scoring based on relevance_scores if available
    if relevance_scores:
        # Cross-category scoring - repositories with balanced matches across categories
        non_zero_categories = sum(1 for cat_score in relevance_scores.values() if cat_score > 0)
        if non_zero_categories >= 3:
            score += 0.8  # Significant bonus for matching 3+ categories
        elif non_zero_categories == 2:
            score += 0.4  # Moderate bonus for matching 2 categories
        
        # High-relevance bonus - repositories with exceptionally high scores in any category
        high_scores = sum(1 for cat_score in relevance_scores.values() if cat_score > 5.0)
        if high_scores >= 2:
            score += 1.0  # Major bonus for high relevance in multiple categories
        elif high_scores == 1:
            score += 0.5  # Minor bonus for high relevance in one category
        
        # Language-specific scoring using relevance_scores instead of matched_query_languages
        language_score = relevance_scores.get('language', 0)
        if language_score > 10:
            score += 0.9  # Exceptional language match
        elif language_score > 5:
            score += 0.6  # Strong language match
        elif language_score > 0:
            score += 0.3  # Some language match
    else:
        # Fallback to original language matching if relevance_scores not available
        language_terms = search_terms.get('languages', [])
        if language_terms and repo.get('languages'):
            matched_languages = len(repo.get('matched_query_languages', []))
            if matched_languages > 1:
                score += 0.8
            elif matched_languages == 1:
                score += 0.4
    
    # Recency bonus (keep this as it's independent of matching)
    if repo.get('updated_at'):
        try:
            updated_date = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
            days_since_update = (datetime.now().replace(tzinfo=updated_date.tzinfo) - updated_date).days
            if days_since_update < 90:  # Very recent (3 months)
                score += 0.7
            elif days_since_update < 365:  # Within a year
                score += 0.4
        except:
            pass
    
    return score

# ==============================================================================
# DIFFICULTY CALCULATION FUNCTIONS
# ==============================================================================

def calculate_tech_difficulty(tech_stack: Dict) -> Tuple[int, List[str], float]:
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

def calculate_architecture_difficulty(components: Dict) -> Tuple[int, List[str], float]:
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

def calculate_skill_difficulty(skill_manifest: Dict) -> Tuple[int, List[str], float]:
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

def calculate_project_difficulty(project_identity: Dict) -> Tuple[int, List[str], float]:
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

def calculate_metrics_difficulty(repo: Dict) -> Tuple[int, List[str], float]:
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


# def sort_repos_by_language_relevance(repositories: List[Dict], query_languages: List[str]) -> List[Dict]:
#     """Sort repositories by language relevance score."""
#     if not query_languages:
#         return repositories
    
#     scored_repos = []
    
#     for repo in repositories:
#         languages = repo.get('languages', {})
#         total_bytes = repo.get('total_language_bytes', 0)
        
#         language_score = calculate_language_score(languages, query_languages, total_bytes)
        
#         scored_repos.append({
#             'repo': repo,
#             'language_score': language_score,
#             'matched_languages': [lang for lang in query_languages 
#                                 if any(lang.lower() in repo_lang.lower() 
#                                       for repo_lang in languages.keys())]
#         })
    
#     # Sort by language score (descending)
#     scored_repos.sort(key=lambda x: x['language_score'], reverse=True)
    
#     return [item['repo'] for item in scored_repos]