import os
import time
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from ...ai.helpers import count_tokens, truncate_text

logger = logging.getLogger('portfolio.api')

class AIQueryProcessor:
    """
    Handles AI query processing and interaction with the Groq API.
    Responsible for managing AI conversations, context preparation, and response generation.
    """
    
    # AI processing constants
    MAX_TOKENS = 8000  # Safe limit for context window
    MAX_CONTEXT_CHARS = 25000  # Character limit for context
    
    def __init__(self, groq_api_key: str = None):
        """
        Initialize the AI Query Processor.
        
        Args:
            groq_api_key: Groq API key for AI processing
        """
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        
        # Initialize OpenAI client for Groq
        self.openai_client = self._initialize_openai_client()
        
        logger.info("AIQueryProcessor initialized")
    
    def _initialize_openai_client(self) -> Optional[OpenAI]:
        """Initialize OpenAI client for Groq with validation."""
        if not self.groq_api_key:
            logger.warning("Groq API key not configured - AI processing disabled")
            return None
        
        return OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    
    def process_query(self, context: str, query: str) -> str:
        """
        Process a query with given context.
        
        Args:
            context: Built context from repositories
            query: User query string
            
        Returns:
            AI response string
        """
        logger.info("Starting AI query processing")
        
        request_id = f"req-{int(time.time())}"
        logger.info(f"Request ID: {request_id} - Processing query: {query[:100]}...")
        
        # Create system message with size management
        system_message = self._build_system_message(context)
        
        # Check token count and truncate if necessary
        system_message = self._manage_context_size(system_message, query, context)
        
        logger.info(f"Request ID: {request_id} - Created system prompt ({len(system_message)} chars)")
        
        # Call Groq API
        return self._call_groq_api(system_message, query, request_id)
    
    def query_ai_with_context(self, query: str, enhanced_context: str, fallback_used: bool = False) -> str:
        """
        Query the AI assistant with enhanced context and size management.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            fallback_used: Flag indicating if fallback repositories were used
            
        Returns:
            AI response string
        """
        logger.info("Starting enhanced AI assistant query")
        
        request_id = f"req-{int(time.time())}"
        logger.info(f"Request ID: {request_id} - Processing enhanced query: {query[:100]}...")
        
        # Create system message with size management
        system_message = self._build_system_message(enhanced_context, fallback_used)
        
        # Check token count and truncate if necessary
        system_message = self._manage_context_size(system_message, query, enhanced_context)
        
        logger.info(f"Request ID: {request_id} - Created system prompt ({len(system_message)} chars)")
        
        # Call Groq API
        return self._call_groq_api(system_message, query, request_id)
    
    def _build_system_message(self, enhanced_context: str, fallback_used: bool = False) -> str:
        """
        Build the system message for AI processing.
        
        Args:
            enhanced_context: Repository context information
            fallback_used: Whether fallback repositories were used
            
        Returns:
            Formatted system message string
        """
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
        
        # Add fallback notice if fallback repositories were used
        if fallback_used:
            fallback_notice = """
NOTE: The query was broad or didn't match specific technical criteria, so I've selected a diverse set of representative projects from the portfolio to provide a comprehensive overview.
"""
            system_template = fallback_notice + system_template
        
        return system_template.format(context=enhanced_context)
    
    def _manage_context_size(self, system_message: str, query: str, enhanced_context: str) -> str:
        """
        Manage context size to fit within token limits.
        
        Args:
            system_message: Original system message
            query: User query
            enhanced_context: Repository context
            
        Returns:
            Size-managed system message
        """
        total_tokens = count_tokens(system_message + query)
        
        if total_tokens > self.MAX_TOKENS:
            logger.warning(f"Context too large ({total_tokens} tokens), truncating...")
            
            # Calculate available space for context
            template_tokens = count_tokens(system_message.replace(enhanced_context, ""))
            query_tokens = count_tokens(query)
            available_tokens = self.MAX_TOKENS - template_tokens - query_tokens - 100  # Buffer
            
            # Truncate context to fit
            if available_tokens > 0:
                available_chars = available_tokens * 4  # Rough estimation
                truncated_context = truncate_text(enhanced_context, available_chars)
                system_message = system_message.replace(enhanced_context, truncated_context)
                logger.info(f"Context truncated to {len(truncated_context)} characters")
            else:
                logger.error("Cannot fit context within token limits")
        
        return system_message
    
    def _call_groq_api(self, system_message: str, query: str, request_id: str) -> str:
        """
        Call the Groq API with the prepared messages.
        
        Args:
            system_message: System message with context
            query: User query
            request_id: Request identifier for logging
            
        Returns:
            AI response string
        """
        if not self.openai_client:
            return "I'm sorry, but the AI service is not configured. Please check the Groq API key."
        
        try:
            logger.info(f"Request ID: {request_id} - Calling Groq API")
            
            response = self.openai_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query}
                ],
                max_tokens=1000,
                temperature=0.7,
                stream=False
            )
            
            ai_response = response.choices[0].message.content
            
            logger.info(f"Request ID: {request_id} - Received AI response ({len(ai_response)} chars)")
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Groq API error: {str(e)}")
            return f"I encountered an error while processing your query with the AI service: {str(e)}"
    
    def process_query_with_metadata(self, query: str, enhanced_context: str, fallback_used: bool,
                                   repositories: list, relevant_repos: list, search_terms: dict,
                                   language_terms: list) -> tuple[str, Dict]:
        """
        Process query and return response with comprehensive metadata.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            fallback_used: Whether fallback repositories were used
            repositories: All repositories searched
            relevant_repos: Relevant repositories found
            search_terms: Extracted search terms
            language_terms: Detected language terms
            
        Returns:
            Tuple of (AI response, metadata dictionary)
        """
        # Get AI response
        ai_response = self.query_ai_with_context(query, enhanced_context, fallback_used)
        
        # Build comprehensive metadata
        metadata = self._build_query_metadata(
            query, repositories, relevant_repos, search_terms,
            language_terms, fallback_used, enhanced_context
        )
        
        return ai_response, metadata
    
    def _build_query_metadata(self, query: str, repositories: list, relevant_repos: list,
                             search_terms: dict, language_terms: list, fallback_used: bool,
                             enhanced_context: str) -> Dict:
        """
        Build comprehensive metadata for the query processing.
        
        Args:
            query: Original user query
            repositories: All repositories searched
            relevant_repos: Relevant repositories found
            search_terms: Extracted search terms
            language_terms: Detected language terms
            fallback_used: Whether fallback was used
            enhanced_context: Built context string
            
        Returns:
            Dictionary containing comprehensive metadata
        """
        
        # Helper function for safe data extraction
        def extract_repo_data(repo: Dict, path: str, default=None):
            """Extract nested repository data safely."""
            current = repo
            for part in path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default
            return current
        
        # Build language analysis
        language_metadata = self._build_language_metadata(relevant_repos, language_terms)
        
        # Repository analysis
        repo_analysis = {
            'total_repositories_searched': len(repositories),
            'relevant_repositories_found': len(relevant_repos),
            'fallback_strategy_used': fallback_used,
            'repositories_in_context': [
                {
                    'name': repo.get('name'),
                    'relevance_score': repo.get('total_relevance_score', 0),
                    'primary_language': list(repo.get('languages', {}).keys())[0] if repo.get('languages') else None,
                    'has_context': bool(extract_repo_data(repo, 'repoContext'))
                }
                for repo in relevant_repos
            ]
        }
        
        # Search analysis
        search_analysis = {
            'extracted_terms': search_terms,
            'language_terms_detected': language_terms,
            'technical_content_detected': bool(
                language_terms or 
                search_terms.get('tech') or 
                search_terms.get('skills') or 
                search_terms.get('components') or 
                search_terms.get('project')
            )
        }
        
        # Context analysis
        context_analysis = {
            'context_length_chars': len(enhanced_context),
            'context_length_tokens': count_tokens(enhanced_context),
            'query_length_tokens': count_tokens(query)
        }
        
        return {
            'query_metadata': {
                'original_query': query,
                'processing_timestamp': time.time(),
                'query_length': len(query)
            },
            'language_analysis': language_metadata,
            'repository_analysis': repo_analysis,
            'search_analysis': search_analysis,
            'context_analysis': context_analysis,
            'processing_notes': {
                'fallback_used': fallback_used,
                'context_truncated': len(enhanced_context) > self.MAX_CONTEXT_CHARS
            }
        }
    
    def _build_language_metadata(self, relevant_repos: list, language_terms: list) -> Dict:
        """
        Build language-specific metadata for the response.
        
        Args:
            relevant_repos: List of relevant repositories
            language_terms: List of detected language terms
            
        Returns:
            Dictionary with language analysis
        """
        # Collect all languages from relevant repositories
        all_languages = {}
        language_matches = []
        
        for repo in relevant_repos:
            repo_languages = repo.get('languages', {})
            
            # Update language totals
            for lang, bytes_count in repo_languages.items():
                all_languages[lang] = all_languages.get(lang, 0) + bytes_count
            
            # Check for language matches
            repo_matches = repo.get('language_matches', [])
            language_matches.extend(repo_matches)
        
        # Calculate language distribution
        total_bytes = sum(all_languages.values())
        language_distribution = {}
        if total_bytes > 0:
            language_distribution = {
                lang: round((bytes_count / total_bytes) * 100, 1)
                for lang, bytes_count in all_languages.items()
            }
        
        return {
            'detected_languages': language_terms,
            'repository_languages': list(all_languages.keys()),
            'language_distribution': language_distribution,
            'language_matches': language_matches,
            'primary_language': max(all_languages.items(), key=lambda x: x[1])[0] if all_languages else None
        }
    
    def validate_api_configuration(self) -> bool:
        """
        Validate API configuration.
        
        Returns:
            True if API is properly configured
        """
        return bool(self.groq_api_key and self.openai_client)
    
    def get_api_status(self) -> Dict[str, Any]:
        """
        Get API status information.
        
        Returns:
            Dictionary with API status
        """
        return {
            'groq_api_configured': bool(self.groq_api_key),
            'openai_client_initialized': bool(self.openai_client),
            'api_ready': self.validate_api_configuration()
        }
