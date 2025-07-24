from typing import Dict, Any, Union, List, Set
import logging
import re
from ai.extractor import flatten_repo_context_to_natural_language
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from data_filter import extract_language_terms
        
logger = logging.getLogger('portfolio.api')

def keyword_overlap_score(query: str, context_str: str) -> float:
    """
    Compute keyword overlap between query and context using regex tokenization.
    Returns ratio of overlapping unique words (case-insensitive, ignores punctuation).
    """
    query_tokens = set(re.findall(r'\b\w+\b', query.lower()))
    context_tokens = set(re.findall(r'\b\w+\b', context_str.lower()))
    overlap = query_tokens & context_tokens
    if not query_tokens:
        return 0.0
    return len(overlap) / len(query_tokens)

class SemanticScorer:
    """
    Scores repositories using semantic similarity between user query and repo context.
    Uses sentence-transformers (MiniLM) for embedding-based similarity.
    """
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def score_context_similarity(self, query: str, repo_context: Dict) -> float:
        # Use natural language flattening for context
        context_str = flatten_repo_context_to_natural_language(repo_context)
        if not context_str or context_str.strip() == "" or "None" in context_str:
            logger.debug("Skipping context scoring due to empty or meaningless context string.")
            return 0.0
        query_emb = self.model.encode([query])
        context_emb = self.model.encode([context_str])
        semantic_score = cosine_similarity(query_emb, context_emb)[0][0]
        keyword_score = keyword_overlap_score(query, context_str)
        return (semantic_score * 0.8) + (keyword_score * 0.2)

    def score_language_matches(self, query: str, repo_languages: Dict) -> float:
        """
        Returns a normalized score [0, 1] based on the proportion of query language matches
        to the number of query language terms. Ignores size.
        """
        query_terms = [t.lower() for t in extract_language_terms(query)]
        if not query_terms:
            return 0.0
        repo_langs = [lang.lower() for lang in repo_languages.keys()]
        matches = set(query_terms) & set(repo_langs)
        score = len(matches) / len(query_terms)
        return min(score, 1.0)

    def score_language_size(self, query: str, repo_languages: Dict) -> float:
        """
        Returns a normalized score [0, 1] based on the total size of matching languages
        divided by the total size of all languages in the repo.
        """
        query_terms = [t.lower() for t in extract_language_terms(query)]
        if not query_terms or not repo_languages:
            return 0.0
        total_size = sum(repo_languages.values())
        if total_size == 0:
            return 0.0
        match_size = sum(size for lang, size in repo_languages.items() if lang.lower() in query_terms)
        score = match_size / total_size
        return min(score, 1.0)

    def aggregate_scores(self, context_score: float, language_score: float) -> float:
        return context_score + language_score