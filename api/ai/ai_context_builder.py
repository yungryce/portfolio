import json
import logging
from typing import List, Dict, Any, Optional
from ...ai.helpers import extract_repo_data, truncate_text

logger = logging.getLogger('portfolio.api')

class ContextBuilder:
    """
    Builds rich context from repository metadata for AI processing.
    """
    
    def __init__(self, repo_manager=None, username: str = 'yungryce'):
        self.repo_manager = repo_manager
        self.username = username
        logger.info(f"ContextBuilder initialized for user: {self.username}")
    
    def build_context(self, repositories: List[Dict], query: str) -> str:
        """
        Build context string from repository data.
        
        Args:
            repositories: List of repository dictionaries
            query: The original query for context-aware building
            
        Returns:
            Formatted context string for AI processing
        """
        try:
            context_parts = []
            
            # Add header
            context_parts.append(f"Portfolio Context for {self.username}")
            context_parts.append("=" * 50)
            context_parts.append(f"User Query: {query}")
            context_parts.append("")
            
            # Add repository contexts
            for i, repo in enumerate(repositories, 1):
                repo_context = self._build_repo_context(repo, i)
                if repo_context:
                    context_parts.append(repo_context)
                    context_parts.append("")
            
            # Add summary
            summary = self._build_summary(repositories)
            if summary:
                context_parts.append("PORTFOLIO SUMMARY")
                context_parts.append("-" * 20)
                context_parts.append(summary)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error building context: {str(e)}")
            return f"Error building context for query: {query}"
    
    def build_enhanced_context(self, repositories: List[Dict], max_chars: int = None) -> str:
        """
        Build comprehensive context for AI from filtered repositories with size limits.
        
        Args:
            repositories: List of filtered repository dictionaries
            max_chars: Maximum characters for context (default: 25000)
            
        Returns:
            Enhanced context string for AI processing
        """
        if max_chars is None:
            max_chars = 25000
        
        context_parts = []
        current_length = 0
        
        if repositories:
            for index, repo in enumerate(repositories, 1):
                repo_name = repo.get('name', f'Repository {index}')
                repo_info = self._build_repo_summary(repo, index, repo_name)
                
                # Check if adding this repo would exceed the limit
                repo_text = '\n'.join(repo_info)
                if current_length + len(repo_text) > max_chars and context_parts:
                    logger.info(f"Context size limit reached, included {index-1} repositories")
                    break
                
                context_parts.extend(repo_info)
                current_length += len(repo_text)
        
        enhanced_context = '\n\n'.join(context_parts)
        logger.info(f"Built enhanced context with {len(enhanced_context)} characters for {len(repositories)} repositories")
        
        return enhanced_context
    
    def _build_repo_context(self, repo: Dict, index: int) -> str:
        """Build context for a single repository."""
        try:
            repo_name = repo.get('name', 'Unknown')
            description = truncate_text(repo.get('description', ''), 200)
            
            context_parts = [f"REPOSITORY {index}: {repo_name}"]
            context_parts.append("-" * 30)
            
            if description:
                context_parts.append(f"Description: {description}")
            
            # Add languages
            languages = repo.get('languages', {})
            if languages:
                lang_list = list(languages.keys())[:5]  # Top 5 languages
                context_parts.append(f"Languages: {', '.join(lang_list)}")
            
            # Add repository context if available
            repo_context = extract_repo_data(repo, 'repoContext', {})
            if repo_context:
                context_parts.append("Enhanced Context:")
                
                # Tech stack
                tech_stack = extract_repo_data(repo_context, 'tech_stack', {})
                if tech_stack:
                    primary = tech_stack.get('primary', [])
                    if primary:
                        context_parts.append(f"  Primary Technologies: {', '.join(primary)}")
                
                # Purpose
                purpose = extract_repo_data(repo_context, 'purpose', '')
                if purpose:
                    context_parts.append(f"  Purpose: {truncate_text(purpose, 150)}")
                
                # Key features
                features = extract_repo_data(repo_context, 'key_features', [])
                if features:
                    feature_text = ', '.join(features[:3])  # Top 3 features
                    context_parts.append(f"  Key Features: {feature_text}")
            
            # Add relevance score if available
            relevance_score = repo.get('language_relevance_score', 0)
            if relevance_score > 0:
                context_parts.append(f"Relevance Score: {relevance_score:.2f}")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.warning(f"Error building context for repo {repo.get('name', 'unknown')}: {str(e)}")
            return f"Repository: {repo.get('name', 'Unknown')} (context error)"
    
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
            total_bytes = sum(languages.values())
            lang_percentages = {lang: (bytes_count / total_bytes * 100) 
                              for lang, bytes_count in languages.items()}
            top_languages = sorted(lang_percentages.items(), key=lambda x: x[1], reverse=True)[:5]
            lang_summary = [f"{lang} ({pct:.1f}%)" for lang, pct in top_languages]
            repo_info.append(f"Languages: {', '.join(lang_summary)}")
        elif primary_lang := extract_repo_data(repo, 'language'):
            repo_info.append(f"Primary Language: {primary_lang}")
    
        if topics := extract_repo_data(repo, 'topics', []):
            repo_info.append(f"Topics: {', '.join(topics[:5])}")
        
        # Technology stack
        if tech_stack := extract_repo_data(repo, 'repoContext.tech_stack', {}):
            if primary := tech_stack.get('primary', []):
                repo_info.append(f"Primary Tech Stack: {', '.join(primary[:5])}")
            if secondary := tech_stack.get('secondary', []):
                repo_info.append(f"Supporting Technologies: {', '.join(secondary[:5])}")
        
        # Skills
        if skill_manifest := extract_repo_data(repo, 'repoContext.skill_manifest', {}):
            if technical := skill_manifest.get('technical', []):
                repo_info.append(f"Technical Skills: {', '.join(technical[:5])}")
        
        # Project details
        if project_identity := extract_repo_data(repo, 'repoContext.project_identity', {}):
            if project_type := project_identity.get('type'):
                repo_info.append(f"Project Type: {project_type}")
            if scope := project_identity.get('scope'):
                repo_info.append(f"Scope: {scope}")
        
        # Components (limited)
        if components := extract_repo_data(repo, 'repoContext.components', {}):
            component_count = len(components)
            if component_count > 0:
                repo_info.append(f"Components: {component_count} components defined")
        
        return repo_info
    
    def _build_summary(self, repositories: List[Dict]) -> str:
        """Build a summary of all repositories."""
        try:
            if not repositories:
                return ""
            
            summary_parts = []
            
            # Count languages across all repos
            all_languages = {}
            for repo in repositories:
                languages = repo.get('languages', {})
                for lang in languages:
                    all_languages[lang] = all_languages.get(lang, 0) + 1
            
            if all_languages:
                # Sort by frequency
                top_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)[:5]
                lang_summary = [f"{lang} ({count} repos)" for lang, count in top_languages]
                summary_parts.append(f"Most Used Languages: {', '.join(lang_summary)}")
            
            # Count by purpose/type if available
            purposes = {}
            for repo in repositories:
                repo_context = extract_repo_data(repo, 'repoContext', {})
                purpose = extract_repo_data(repo_context, 'purpose', '')
                if purpose:
                    purpose_key = purpose.split('.')[0].strip()  # First sentence
                    purposes[purpose_key] = purposes.get(purpose_key, 0) + 1
            
            if purposes and len(purposes) > 1:
                top_purposes = sorted(purposes.items(), key=lambda x: x[1], reverse=True)[:3]
                purpose_summary = [f"{purpose} ({count})" for purpose, count in top_purposes]
                summary_parts.append(f"Project Types: {', '.join(purpose_summary)}")
            
            summary_parts.append(f"Total Repositories Analyzed: {len(repositories)}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.warning(f"Error building summary: {str(e)}")
            return f"Portfolio contains {len(repositories)} repositories"
