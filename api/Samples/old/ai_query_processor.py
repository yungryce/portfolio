import logging
import time
import os
from typing import Dict, Tuple
from openai import OpenAI
from .helpers import count_tokens, truncate_text, get_language_matches, get_language_matches

# Use the existing logger from function_app.py
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
    
    def _initialize_openai_client(self) -> OpenAI:
        """Initialize OpenAI client for Groq with validation."""
        if not self.groq_api_key:
            logger.error("GROQ_API_KEY not configured in environment")
            raise ValueError("GROQ_API_KEY environment variable is not set")
        
        return OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    
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
            system_template += "\n\nNOTE: Your query didn't have strong matches in the portfolio. Showing best available projects."
        
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
            logger.warning(f"Context too large ({total_tokens} tokens). Truncating...")
            
            # Calculate available space for context
            system_template_base = system_message.replace(enhanced_context, "{context}")
            available_chars = self.MAX_CONTEXT_CHARS - len(system_template_base) - len(query) - 500  # Buffer
            
            # Truncate context to fit within limits
            truncated_context = truncate_text(enhanced_context, available_chars)
            system_message = system_template_base.format(context=truncated_context)
            
            logger.info(f"Context truncated from {len(enhanced_context)} to {len(truncated_context)} chars")
        
        return system_message
    
    def _call_groq_api(self, system_message: str, query: str, request_id: str) -> str:
        """
        Make the actual API call to Groq.
        
        Args:
            system_message: Prepared system message
            query: User query
            request_id: Request identifier for logging
            
        Returns:
            AI response string
        """
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
    
    def process_query_with_metadata(self, query: str, enhanced_context: str, fallback_used: bool, 
                                   repositories: list, relevant_repos: list, search_terms: dict, 
                                   language_terms: list) -> Tuple[str, Dict]:
        """
        Process a query and return both the AI response and comprehensive metadata.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            fallback_used: Whether fallback repositories were used
            repositories: Original list of all repositories
            relevant_repos: List of relevant repositories found
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
        
        def extract_repo_data(repo: Dict, path: str, default=None):
            """Helper to extract repo data safely."""
            if repo is None:
                return default
            
            current = repo
            for part in path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current.get(part)
                else:
                    return default
            return current if current is not None else default
        
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
            "detected_languages": language_terms,
            "language_based_filtering": len(language_terms) > 0,
            "fallback_used": fallback_used,
            "search_terms_found": {
                "tech": len(search_terms.get('tech', [])),
                "skills": len(search_terms.get('skills', [])),
                "components": len(search_terms.get('components', [])),
                "project": len(search_terms.get('project', [])),
                "general": len(search_terms.get('general', []))
            },
            "repositories_analyzed": [extract_repo_data(repo, 'name', 'Unknown') for repo in relevant_repos[:5]],
            "context_size_chars": len(enhanced_context),
        }
        
        # Add language-specific metadata if applicable
        if language_terms and relevant_repos:
            metadata.update(self._build_language_metadata(relevant_repos, language_terms))
        
        return metadata
    
    def _build_language_metadata(self, relevant_repos: list, language_terms: list) -> Dict:
        """
        Build language-specific metadata for repositories.
        
        Args:
            relevant_repos: List of relevant repositories
            language_terms: Detected language terms
            
        Returns:
            Dictionary with language-specific metadata
        """
        
        def extract_repo_data(repo: Dict, path: str, default=None):
            """Helper to extract repo data safely."""
            if repo is None:
                return default
            
            current = repo
            for part in path.split('.'):
                if isinstance(current, dict) and part in current:
                    current = current.get(part)
                else:
                    return default
            return current if current is not None else default
        
        language_matches = []
        
        for repo in relevant_repos[:5]:  # Limit to top 5 for efficiency
            repo_languages = extract_repo_data(repo, 'languages', {})
            total_bytes = extract_repo_data(repo, 'total_language_bytes', 0)

            # Get detailed language matches with error handling
            try:
                matches = get_language_matches(
                    repo_languages, 
                    language_terms,
                    extract_repo_data(repo, 'relevance_scores', {})
                )
                
                if matches:
                    language_matches.append({
                        "repository": extract_repo_data(repo, 'name', 'Unknown'),
                        "language_matches": matches,
                        "total_languages": len(repo_languages),
                        "primary_language": extract_repo_data(repo, 'language', 'Unknown'),
                        "total_bytes": total_bytes
                    })
            except Exception as e:
                logger.error(f"Error getting language matches for {extract_repo_data(repo, 'name', 'Unknown')}: {str(e)}")

        # Build detailed score breakdown for top matches
        top_matches_details = []
        for repo in relevant_repos[:3]:
            scores = extract_repo_data(repo, 'relevance_scores', {})
            top_matches_details.append({
                "name": extract_repo_data(repo, 'name', 'Unknown'),
                "total_score": extract_repo_data(repo, 'total_relevance_score', 0),
                "score_breakdown": {
                    "language": scores.get('language', 0),
                    "tech": scores.get('tech', 0),
                    "skill": scores.get('skill', 0),
                    "component": scores.get('component', 0),
                    "project": scores.get('project', 0),
                    "general": scores.get('general', 0),
                    "bonus": scores.get('bonus', 0)
                }
            })
        
        return {
            "language_matches": language_matches,
            "top_matches_details": top_matches_details
        }
    
    def validate_api_configuration(self) -> bool:
        """
        Validate that the AI API is properly configured.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            if not self.groq_api_key:
                logger.error("GROQ_API_KEY is not configured")
                return False
            
            if not self.openai_client:
                logger.error("OpenAI client is not initialized")
                return False
            
            # Test connection with a simple query
            test_response = self.openai_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            
            if test_response.choices and len(test_response.choices) > 0:
                logger.info("AI API configuration validated successfully")
                return True
            else:
                logger.error("AI API test failed - no response received")
                return False
                
        except Exception as e:
            logger.error(f"AI API configuration validation failed: {str(e)}")
            return False
    
    def get_api_status(self) -> Dict:
        """
        Get the current status of the AI API connection.
        
        Returns:
            Dictionary with API status information
        """
        status = {
            "api_key_configured": bool(self.groq_api_key),
            "client_initialized": bool(self.openai_client),
            "connection_status": "unknown"
        }
        
        if status["api_key_configured"] and status["client_initialized"]:
            try:
                # Quick test to check API connectivity
                start_time = time.time()
                test_response = self.openai_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1
                )
                response_time = time.time() - start_time
                
                if test_response.choices and len(test_response.choices) > 0:
                    status["connection_status"] = "healthy"
                    status["response_time_ms"] = round(response_time * 1000, 2)
                else:
                    status["connection_status"] = "error"
                    status["error"] = "No response received"
                    
            except Exception as e:
                status["connection_status"] = "error"
                status["error"] = str(e)
        else:
            status["connection_status"] = "not_configured"
        
        return status