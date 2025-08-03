def extract_query_concepts(query: str) -> dict[str, set]:
    """
    Extracts a wide range of technical concepts from a query string.

    This function analyzes the query against predefined lists of languages,
    technical keywords, advanced skills, and tool ecosystems.

    Args:
        query: The user's query string.

    Returns:
        A dictionary containing sets of found 'languages', 'skills', and 'tools'.
    """
    query_lower = query.lower()
    
    # Use existing function for languages
    found_languages = set(extract_language_terms(query_lower))
    
    # Find matches in skills and tools
    found_skills = {skill for skill in advanced_skills if re.search(r'\b' + re.escape(skill) + r'\b', query_lower)}
    found_tools = {tool for tool in technical_keywords if re.search(r'\b' + re.escape(tool) + r'\b', query_lower)}
    
    # Also check against the names of tool ecosystems
    found_tools.update({tool for tool in tool_ecosystems if re.search(r'\b' + re.escape(tool) + r'\b', query_lower)})

    return {
        "languages": found_languages,
        "skills": found_skills,
        "tools": found_tools
    }

def score_concept_matches(self, query: str, repo_context: Dict) -> float:
    """
    Scores repository based on overlap between query concepts and repo context.
    """
    query_concepts = extract_query_concepts(query)
    total_query_concepts = sum(len(v) for v in query_concepts.values())

    if total_query_concepts == 0:
        return 0.2  # Return a neutral score for generic queries

    repo_langs = {lang.lower() for lang in repo_context.get('languages', {})}
    repo_context_str = flatten_repo_context_to_natural_language(repo_context)
    
    # Check for language matches
    lang_matches = query_concepts['languages'] & repo_langs
    
    # Check for skill and tool matches in the repo's context string
    # This is a simple but effective way to see if the repo mentions the concepts
    skill_matches = {skill for skill in query_concepts['skills'] if skill in repo_context_str}
    tool_matches = {tool for tool in query_concepts['tools'] if tool in repo_context_str}
    
    total_matches = len(lang_matches) + len(skill_matches) + len(tool_matches)
    
    score = total_matches / total_query_concepts if total_query_concepts > 0 else 0.0
    logger.debug(f"Concept match score for repo '{repo_context.get('name')}': {score} ({total_matches}/{total_query_concepts} matches)")
    return min(score, 1.0)
