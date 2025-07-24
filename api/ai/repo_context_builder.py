from typing import Dict, Any, List

class RepoContextBuilder:
    """
    Builds graduated AI context for top repositories.
    """
    def __init__(self, repo_manager, username):
        self.repo_manager = repo_manager
        self.username = username

    def build_tiered_context(self, top_repos: List[Dict], max_repos: int = 3) -> Dict[str, Any]:
        context = {}
        if top_repos:
            context['primary_repo'] = self._build_detailed_context(top_repos[0])
        if len(top_repos) > 1:
            context['secondary_repo'] = self._build_summary_context(top_repos[1])
        if len(top_repos) > 2:
            context['tertiary_repo'] = self._build_mention_context(top_repos[2])
        return context

    def _build_detailed_context(self, repo: Dict) -> Dict:
        # Retrieve README, SKILLS-INDEX, ARCHITECTURE
        return {
            "name": repo.get("name"),
            "readme": repo.get("readme", ""),
            "skills_index": repo.get("skills_index", ""),
            "architecture": repo.get("architecture", ""),
            "context": repo.get("repoContext", {})
        }

    def _build_summary_context(self, repo: Dict) -> Dict:
        return {
            "name": repo.get("name"),
            "summary": repo.get("readme", "")[:200]
        }

    def _build_mention_context(self, repo: Dict) -> Dict:
        return {"name": repo.get("name")}
    
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