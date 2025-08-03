from typing import Dict, Any, Union, List, Set, Tuple
import logging
import re
from ai.extractor import flatten_repo_context_to_natural_language
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from data_filter import extract_language_terms, technical_terms_structured
        
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
    def __init__(self, model_path: str):
        self.model = SentenceTransformer(model_path)

    def extract_technical_terms_from_query(self, query: str) -> Tuple[List[str], Dict[str, float]]:
        """
        Extract technical terms and domain concepts from the query using structured data.
        
        Returns:
            tuple: (list of extracted terms, dict of term categories with weights)
                - extracted_terms: All technical terms found in the query
                - term_categories: Dictionary mapping categories to their weights in the query
        """
        query_lower = query.lower()
        query_tokens = set(re.findall(r'\b\w+\b', query_lower))
        
        # Extract all relevant terms
        extracted_terms = []
        
        # Track which categories of terms were found (for debugging and weighting)
        term_categories = {
            'language': 0.0,
            'domain': 0.0,
            'advanced_tool': 0.0,
            'complexity': 0.0
        }
        
        # 1. Check for programming languages
        language_terms = extract_language_terms(query)
        if language_terms:
            extracted_terms.extend(language_terms)
            term_categories['language'] = 1.0
        
        # 2. Check for advanced technical skills
        domain_matches = [term for term in technical_terms_structured['domain'] if term in query_lower]
        if domain_matches:
            extracted_terms.extend(domain_matches)
            term_categories['domain'] = len(domain_matches) / len(query_tokens) if query_tokens else 0
        
        # 3. Check for technical keywords
        keyword_matches = [term for term in technical_terms_structured['advanced_skills'] if term in query_lower]
        if keyword_matches:
            extracted_terms.extend(keyword_matches)
            term_categories['advanced_tool'] = len(keyword_matches) / len(query_tokens) if query_tokens else 0

        # 5. Check for complexity indicators
        complexity_matches = [term for term in technical_terms_structured['complexity_indicators'] if term in query_lower]
        if complexity_matches:
            extracted_terms.extend(complexity_matches)
            term_categories['complexity'] = len(complexity_matches) / len(query_tokens) if query_tokens else 0
        
        # Log the findings
        if extracted_terms:
            logger.debug(f"Enhanced query terms extracted: {extracted_terms}")
            logger.debug(f"Term category distribution: {term_categories}")
        else:
            logger.debug(f"No technical terms found in query: '{query}'")
        
        return extracted_terms, term_categories

    def enrich_query_with_domain(self, query: str) -> str:
        """
        Enriches the query using high-similarity tokens from the 'domain' field in technical_terms_structured.

        Args:
            query (str): Original query.

        Returns:
            str: Enriched query.
        """
        # Tokenize the query and remove stop words
        query_tokens = [token for token in re.findall(r'\b\w+\b', query.lower()) if token not in technical_terms_structured['stop_words']]

        # Extract domain terms from technical_terms_structured
        domain_terms = list(technical_terms_structured['domain'])

        # Compute similarity scores between query tokens and domain terms
        query_embeddings = self.model.encode(query_tokens)
        domain_embeddings = self.model.encode(domain_terms)
        similarity_matrix = cosine_similarity(query_embeddings, domain_embeddings)

        # Rank domain terms by similarity and filter by threshold
        similarity_scores = {term: max(similarity_matrix[:, i]) for i, term in enumerate(domain_terms)}
        ranked_tokens = [term for term, score in sorted(similarity_scores.items(), key=lambda x: x[1], reverse=True) if score >= 0.7]

        # Enrich the query with high-similarity domain terms
        enriched_query = query + " " + " ".join(ranked_tokens)

        # Log the enriched query
        logger.debug(f"Original query: '{query}'")
        logger.debug(f"Enriched query: '{enriched_query}'")
        logger.debug(f"Ranked tokens added: {ranked_tokens}")

        return enriched_query

    def score_context_similarity(self, query: str, repo_context: Dict) -> float:
        """
        Scores the similarity between the query and the repository context using semantic embeddings.
        Also incorporates scoring between enriched query and the context string.

        Returns:
            float: Aggregated similarity score.
        """
        context_str = flatten_repo_context_to_natural_language(repo_context)
        if not context_str or context_str.strip() == "" or "None" in context_str:
            logger.debug(f"Skipping context scoring for {repo_context.get('name', 'Unknown')} due to empty or meaningless context string.")
            return 0.0

        # Enrich the query with domain terms
        enriched_query = self.enrich_query_with_domain(query)

        # Semantic similarity between original query and context
        query_emb = self.model.encode([enriched_query])
        context_emb = self.model.encode([context_str])
        semantic_score_query_context = cosine_similarity(query_emb, context_emb)[0][0]

        # Semantic similarity between enriched query and context
        enriched_query_emb = self.model.encode([enriched_query])
        semantic_score_enriched_context = cosine_similarity(enriched_query_emb, context_emb)[0][0]

        # Aggregate scores with dynamic weighting
        if semantic_score_query_context > 0.5:
            aggregated_score = (semantic_score_query_context * 0.7) + (semantic_score_enriched_context * 0.3)
        else:
            aggregated_score = (semantic_score_query_context * 0.4) + (semantic_score_enriched_context * 0.6)

        # Log the scores
        project_name = repo_context.get("project_identity", {}).get("name")
        logger.debug(f"Context similarity score for: '{project_name}'= {semantic_score_query_context}, enriched query score: {semantic_score_enriched_context}, aggregated score: {aggregated_score}")

        return aggregated_score

    def score_language_matches(self, query: str, repo_languages: Dict) -> float:
        """
        Returns a normalized score [0, 1] based on the proportion of query language matches
        to the number of query language terms. Ignores size.
        """
        logger.debug(f"Scoring language matches for: {repo_languages}")
        query_terms = [t.lower() for t in extract_language_terms(query)]
        if not query_terms:
            logger.debug(f"No language terms found in query: '{query}'")
            return 0.0
        repo_langs = [lang.lower() for lang in repo_languages.keys()]
        matches = set(query_terms) & set(repo_langs)
        score = len(matches) / len(query_terms)
        logger.debug(f"Language match score for query '{query}': {score} (matches: {matches})")
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
        logger.debug(f"Language size score for query '{query}': {match_size}/{total_size} = {match_size / total_size if total_size > 0 else 0.0}")
        score = match_size / total_size
        return min(score, 1.0)

    def aggregate_scores(self, context_score: float, language_score: float, type_score: float) -> float:
        return (context_score * 0.4) + (language_score * 0.3) + (type_score * 0.3)