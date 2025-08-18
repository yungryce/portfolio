import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from .helpers import count_tokens, truncate_text

logger = logging.getLogger('portfolio.api')

class AIContextBuilder:
    """
    Builds rich context from tiered repository context for AI processing and handles Groq API calls.
    """

    MAX_TOKENS = 8000  # Safe limit for context window
    MAX_CONTEXT_CHARS = 25000  # Character limit for context

    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key
        self.openai_client = self._initialize_openai_client()
        logger.info("AIContextBuilder initialized.")

    def _initialize_openai_client(self) -> Optional[OpenAI]:
        """Initialize OpenAI client for Groq with validation."""
        if not self.groq_api_key:
            logger.warning("Groq API key not configured - AI processing disabled")
            return None
        return OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )

    def process_scored_repositories(self, query: str, scored_repos: List[Dict[str, Any]], max_repos: int = 3) -> Dict[str, Any]:
        """
        Processes pre-scored repositories to build context and generate AI responses.
        
        Args:
            query: User's query string
            scored_repos: List of repositories with scores already calculated
            max_repos: Maximum number of repositories to include in context
            
        Returns:
            Dictionary with AI response and metadata
        """
        try:
            logger.info(f"Processing AI response for query: {query[:100]}...")
            if not scored_repos:
                return {
                    "response": f"No repositories found for {self.username}.",
                    "repositories_used": [],
                    "total_repositories": 0,
                    "query": query
                }

            # Get top repositories
            top_repos = scored_repos[:max_repos]
            
            # Build tiered context for AI
            context = self.ai_context_builder.build_tiered_context(top_repos, max_repos=max_repos)
            
            # Generate AI system message with context
            system_message = self.ai_context_builder.build_rules_context(context)
            
            # Get LLM response
            groq_api_key = os.getenv("GROQ_API_KEY")
            if not groq_api_key:
                logger.warning("Groq API key not configured - AI processing disabled")
                repositories_used = [
                    {"name": repo.get("name", "Unknown"), "relevance_score": repo.get("total_relevance_score", 0)}
                    for repo in top_repos
                ]
                return {
                    "response": "AI processing is disabled: GROQ_API_KEY not configured.",
                    "repositories_used": repositories_used,
                    "total_repositories": len(scored_repos),
                    "query": query
                }
                
            # Call AI with context
            ai_response = self._get_ai_response(system_message, query)
            
            # Build response with metadata
            repositories_used = [
                {"name": repo.get("name", "Unknown"), "relevance_score": repo.get("total_relevance_score", 0)}
                for repo in top_repos
            ]
            
            return {
                "response": ai_response,
                "repositories_used": repositories_used,
                "total_repositories": len(scored_repos),
                "query": query
            }
        except Exception as e:
            logger.error(f"Error during AI processing: {str(e)}", exc_info=True)
            return {
                "response": f"Error processing query: {str(e)}",
                "repositories_used": [],
                "total_repositories": len(scored_repos) if scored_repos else 0,
                "query": query
            }
 
    def build_ai_query_context(self, tiered_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accepts the output of build_tiered_context and returns a dict with
        - primary_repo: full context, readme, skills_index, context_metadata
        - secondary_repo: partial context, truncated readme, context_metadata
        - tertiary_repo: further truncated, context_metadata
        """
        context = {}
        # Primary repo
        primary = tiered_context.get("primary_repo")
        if primary:
            context["primary_repo"] = {
                "name": primary.get("name"),
                "context_metadata": {
                    "project_identity": primary.get("context", {}).get("project_identity"),
                    "tech_stack": primary.get("context", {}).get("tech_stack"),
                },
                "readme": primary.get("readme", ""),
                "skills_index": primary.get("skills_index", "")
            }
        # Secondary repo
        secondary = tiered_context.get("secondary_repo")
        if secondary:
            readme = secondary.get("readme", "")
            context["secondary_repo"] = {
                "name": secondary.get("name"),
                "context_metadata": {
                    "project_identity": secondary.get("context", {}).get("project_identity"),
                    "tech_stack": secondary.get("context", {}).get("tech_stack"),
                },
                "readme": readme[:max(len(readme)//4, 500)]
            }
        # Tertiary repo
        tertiary = tiered_context.get("tertiary_repo")
        if tertiary:
            readme = tertiary.get("readme", "")
            context["tertiary_repo"] = {
                "name": tertiary.get("name"),
                "context_metadata": {
                    "project_identity": tertiary.get("context", {}).get("project_identity"),
                    "tech_stack": tertiary.get("context", {}).get("tech_stack"),
                },
                "readme": readme[:300]
            }
        return context

    def build_tiered_context(self, top_repos: List[Dict], max_repos: int = 3) -> Dict[str, Any]:
        """
        Builds a context dict for the top repositories using pre-fetched content from repo bundles.
        Returns structured context suitable for AI context building with tiered importance.
        
        Args:
            top_repos: List of repository bundles with pre-fetched content and scoring
            max_repos: Maximum number of repositories to include in context
        
        Returns:
            Dictionary with primary_repo, secondary_repo, and tertiary_repo context
        """
        context = {}
        for i, repo in enumerate(top_repos[:max_repos]):
            repo_name = repo.get("name")
            
            # Extract pre-fetched content directly from repo bundle
            readme = repo.get("readme", "")
            skills_index = repo.get("skills_index", "")
            architecture = repo.get("architecture", "")
            
            # Compose context for each repo
            repo_context = {
                "name": repo_name,
                "readme": readme,
                "skills_index": skills_index,
                "architecture": architecture,
                "context": repo.get("repoContext", {}),
                "score_metadata": {
                    "context_score": repo.get("context_score", 0),
                    "language_score": repo.get("language_score", 0),
                    "type_score": repo.get("type_score", 0),
                    "total_relevance_score": repo.get("total_relevance_score", 0),
                    "categorized_types": repo.get("categorized_types", {}),
                    "file_types": repo.get("file_types", {})
                }
            }
            
            # Assign to tiered context
            if i == 0:
                context['primary_repo'] = repo_context
            elif i == 1:
                context['secondary_repo'] = repo_context
            elif i == 2:
                context['tertiary_repo'] = repo_context
        
        return context

    def build_rules_context(self, tiered_context: Dict[str, Any], fallback_used: bool = False) -> str:
        """
        Build the system message/rules context for AI processing using tiered context.
        """
        def repo_section(repo: Dict[str, Any], label: str) -> str:
            if not repo:
                return ""
            lines = [f"{label.upper()} REPOSITORY: {repo.get('name', 'Unknown')}", "-"*40]
            if repo.get("readme"):
                lines.append(f"README\n{truncate_text(repo['readme'], 2000)}")
            if repo.get("skills_index"):
                lines.append(f"SKILLS INDEX\n{truncate_text(repo['skills_index'], 2000)}")
            return "\n".join(lines)

        context_parts = []
        for label in ["primary_repo", "secondary_repo", "tertiary_repo"]:
            repo = tiered_context.get(label)
            if repo:
                context_parts.append(repo_section(repo, label.replace("_repo", "")))

        # Optionally include architecture docs verbatim for frontend
        for label in ["primary_repo", "secondary_repo", "tertiary_repo"]:
            repo = tiered_context.get(label)
            if repo and repo.get("architecture"):
                context_parts.append(f"{label.upper()} ARCHITECTURE.md:\n{repo['architecture']}")

        return context_parts
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
        if fallback_used:
            fallback_notice = """
NOTE: The query was broad or didn't match specific technical criteria, so I've selected a diverse set of representative projects from the portfolio to provide a comprehensive overview.
"""
            system_template = fallback_notice + system_template

        context_str = "\n\n".join(context_parts)
        return system_template.format(context=context_str)

    def ensure_context_size(self, system_message: str, query: str, context_str: str) -> str:
        """
        Ensure the context fits within token limits, truncating if necessary.
        """
        total_tokens = count_tokens(system_message + query)
        if total_tokens > self.MAX_TOKENS:
            logger.warning(f"Context too large ({total_tokens} tokens), truncating...")
            template_tokens = count_tokens(system_message.replace(context_str, ""))
            query_tokens = count_tokens(query)
            available_tokens = self.MAX_TOKENS - template_tokens - query_tokens - 100  # Buffer
            if available_tokens > 0:
                available_chars = available_tokens * 4  # Rough estimation
                truncated_context = truncate_text(context_str, available_chars)
                system_message = system_message.replace(context_str, truncated_context)
                logger.info(f"Context truncated to {len(truncated_context)} characters")
            else:
                logger.error("Cannot fit context within token limits")
        return system_message

    def call_groq_api(self, system_message: str, query: str, request_id: str) -> str:
        """
        Call the Groq API with the prepared messages.
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

    def process_query_with_metadata(self, query: str, tiered_context: Dict[str, Any], fallback_used: bool,
                                   repositories: list, relevant_repos: list, search_terms: dict,
                                   language_terms: list) -> tuple[str, Dict]:
        """
        Process query and return response with comprehensive metadata.
        """
        import time
        # Build system message with rules and context
        system_message = self.build_rules_context(tiered_context, fallback_used)
        # Extract the context string for size management
        context_str = system_message.split("PORTFOLIO REPOSITORY ANALYSIS:")[-1]
        system_message = self.ensure_context_size(system_message, query, context_str)
        request_id = f"req-{int(time.time())}"
        ai_response = self.call_groq_api(system_message, query, request_id)
        # Build metadata
        metadata = {
            "query": query,
            "fallback_used": fallback_used,
            "repositories_searched": len(repositories),
            "relevant_repositories": len(relevant_repos),
            "search_terms": search_terms,
            "language_terms": language_terms,
            "context_length_chars": len(context_str),
            "context_length_tokens": count_tokens(context_str),
            "ai_response_length": len(ai_response),
            "timestamp": request_id,
        }
        return ai_response, metadata







