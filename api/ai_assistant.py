import logging
import os
import time
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from github_client import GitHubClient

# Configure logging
logger = logging.getLogger('portfolio.ai_assistant')
logger.setLevel(logging.INFO)


class AIAssistant:
    """
    Modular AI Assistant class for portfolio query processing with repository context management.
    Handles search term extraction, repository filtering, and enhanced AI query processing.
    """
    
    def __init__(self, github_token: str = None, username: str = 'yungryce'):
        """
        Initialize the AI Assistant with GitHub client and configuration.
        
        Args:
            github_token: GitHub API token for repository access
            username: GitHub username for repository queries
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.username = username
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        # Initialize GitHub client
        if self.github_token:
            self.gh_client = GitHubClient(token=self.github_token, username=self.username)
        else:
            self.gh_client = None
            logger.warning("GitHub token not configured - file fetching disabled")
        
        # Validate Groq API key
        if not self.groq_api_key:
            logger.error("GROQ_API_KEY not configured in environment")
            raise ValueError("GROQ_API_KEY environment variable is not set")
        
        # Initialize OpenAI client for Groq
        self.openai_client = OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )
        
        logger.info(f"AI Assistant initialized for user: {self.username}")
    
    def calculate_difficulty_score(self, repo: Dict) -> Dict[str, any]:
        """
        Calculate difficulty score for a repository using enhanced context analysis.
        
        Args:
            repo: Repository dictionary with context
            
        Returns:
            Dictionary containing difficulty rating, score, and reasoning
        """
        
        if not repo:
            return {
                'difficulty': 'unknown',
                'score': 0,
                'confidence': 0.0,
                'reasoning': ['No repository data available']
            }
        
        repo_context = repo.get('repoContext', {})
        difficulty_score = 0
        reasoning = []
        confidence_factors = []
        
        # 1. TECHNOLOGY STACK COMPLEXITY (0-30 points)
        tech_stack = repo_context.get('tech_stack', {})
        
        # Primary technologies complexity
        primary_tech = tech_stack.get('primary', [])
        if primary_tech:
            tech_complexity = 0
            advanced_techs = ['kubernetes', 'docker', 'microservices', 'distributed', 'blockchain', 'machine learning', 'ai', 'tensorflow', 'pytorch', 'react native', 'flutter']
            intermediate_techs = ['react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel', 'mongodb', 'postgresql', 'redis']
            
            for tech in primary_tech:
                tech_lower = tech.lower()
                if any(adv in tech_lower for adv in advanced_techs):
                    tech_complexity += 3
                elif any(inter in tech_lower for inter in intermediate_techs):
                    tech_complexity += 2
                else:
                    tech_complexity += 1
            
            difficulty_score += min(tech_complexity, 15)
            reasoning.append(f"Primary technologies: {', '.join(primary_tech)}")
            confidence_factors.append(0.8)
        
        # Secondary technologies and libraries
        secondary_tech = tech_stack.get('secondary', [])
        key_libraries = tech_stack.get('key_libraries', [])
        
        if secondary_tech or key_libraries:
            additional_complexity = len(secondary_tech) + len(key_libraries)
            difficulty_score += min(additional_complexity, 10)
            reasoning.append(f"Additional technologies: {additional_complexity} tools/libraries")
            confidence_factors.append(0.6)
        
        # Development tools complexity
        dev_tools = tech_stack.get('development_tools', [])
        if dev_tools:
            tools_complexity = len(dev_tools)
            difficulty_score += min(tools_complexity, 5)
            reasoning.append(f"Development tools: {tools_complexity} specialized tools")
            confidence_factors.append(0.4)
        
        # 2. ARCHITECTURE COMPLEXITY (0-25 points)
        components = repo_context.get('components', {})
        
        if components:
            # Number of components
            component_count = len(components)
            difficulty_score += min(component_count * 2, 10)
            
            # Component type complexity
            complex_components = 0
            for comp_name, comp_data in components.items():
                comp_type = comp_data.get('type', '').lower()
                if any(term in comp_type for term in ['service', 'api', 'microservice', 'database', 'cache', 'queue']):
                    complex_components += 1
            
            difficulty_score += min(complex_components * 3, 15)
            reasoning.append(f"Architecture: {component_count} components, {complex_components} complex components")
            confidence_factors.append(0.9)
        
        # 3. SKILL REQUIREMENTS (0-20 points)
        skill_manifest = repo_context.get('skill_manifest', {})
        
        technical_skills = skill_manifest.get('technical', [])
        domain_skills = skill_manifest.get('domain', [])
        
        if technical_skills or domain_skills:
            skill_complexity = len(technical_skills) + len(domain_skills)
            difficulty_score += min(skill_complexity, 15)
            
            # Advanced skill detection
            advanced_skills = ['devops', 'cloud', 'aws', 'azure', 'gcp', 'security', 'performance', 'scalability', 'testing', 'ci/cd']
            advanced_count = 0
            
            for skill in technical_skills + domain_skills:
                if any(adv in skill.lower() for adv in advanced_skills):
                    advanced_count += 1
            
            difficulty_score += min(advanced_count, 5)
            reasoning.append(f"Skills: {skill_complexity} total skills, {advanced_count} advanced skills")
            confidence_factors.append(0.7)
        
        # 4. PROJECT SCOPE AND FEATURES (0-15 points)
        project_identity = repo_context.get('project_identity', {})
        
        if project_identity:
            project_type = project_identity.get('type', '').lower()
            project_scope = project_identity.get('scope', '').lower()
            
            # Project type complexity
            if any(term in project_type for term in ['full-stack', 'enterprise', 'distributed', 'real-time']):
                difficulty_score += 5
                reasoning.append(f"Complex project type: {project_type}")
            elif any(term in project_type for term in ['web application', 'api', 'service']):
                difficulty_score += 3
            
            # Project scope complexity
            if any(term in project_scope for term in ['large', 'complex', 'enterprise', 'production']):
                difficulty_score += 5
                reasoning.append(f"Complex project scope: {project_scope}")
            elif any(term in project_scope for term in ['medium', 'moderate']):
                difficulty_score += 2
            
            confidence_factors.append(0.6)
        
        # 5. REPOSITORY METRICS (0-10 points)
        repo_language = repo.get('language', '')
        repo_size = repo.get('size', 0)
        
        if repo_size > 50000:  # Large repository
            difficulty_score += 5
            reasoning.append(f"Large repository size: {repo_size} KB")
        elif repo_size > 10000:  # Medium repository
            difficulty_score += 2
        
        # Language complexity
        complex_languages = ['c++', 'rust', 'go', 'scala', 'haskell', 'assembly']
        if repo_language and repo_language.lower() in complex_languages:
            difficulty_score += 3
            reasoning.append(f"Complex primary language: {repo_language}")
        
        confidence_factors.append(0.5)
        
        # 6. INTEGRATION AND DEPLOYMENT (0-10 points)
        # Check for deployment complexity
        if any(key in repo_context for key in ['deployment_workflow', 'ci_cd', 'infrastructure']):
            difficulty_score += 5
            reasoning.append("Has deployment/CI-CD configuration")
            confidence_factors.append(0.7)
        
        # Calculate final difficulty rating
        max_possible_score = 100
        normalized_score = min(difficulty_score, max_possible_score)
        
        # Determine difficulty level
        if normalized_score >= 75:
            difficulty_level = 'expert'
        elif normalized_score >= 50:
            difficulty_level = 'advanced'
        elif normalized_score >= 25:
            difficulty_level = 'intermediate'
        else:
            difficulty_level = 'beginner'
        
        # Calculate confidence based on available data
        avg_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.3
        
        return {
            'difficulty': difficulty_level,
            'score': normalized_score,
            'confidence': round(avg_confidence, 2),
            'reasoning': reasoning,
            'breakdown': {
                'technology_complexity': min(difficulty_score, 30),
                'architecture_complexity': min(len(components) * 2 + sum(1 for comp in components.values() if 'service' in comp.get('type', '').lower()) * 3, 25) if components else 0,
                'skill_requirements': min(len(technical_skills) + len(domain_skills), 20),
                'project_scope': min(10, 10),
                'repository_metrics': min(5 if repo_size > 50000 else 2 if repo_size > 10000 else 0, 10)
            }
        }

    def get_difficulty_rating(self, repo: Dict) -> str:
        """
        Get simple difficulty rating for a repository.
        
        Args:
            repo: Repository dictionary with context
            
        Returns:
            String difficulty rating ('beginner', 'intermediate', 'advanced', 'expert')
        """
        difficulty_data = self.calculate_difficulty_score(repo)
        return difficulty_data['difficulty']
    
    def extract_search_terms(self, query: str, repositories: List[Dict] = None) -> Dict[str, List[str]]:
        """
        Dynamic search term extraction from repository contexts without hardcoded keywords.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries with context
            
        Returns:
            Dictionary of categorized search terms
        """
        
        # Initialize dynamic keyword collections
        dynamic_keywords = {
            'tech': set(),
            'skills': set(), 
            'components': set(),
            'project': set()
        }
        
        # Extract keywords from repository contexts if provided
        if repositories:
            for repo in repositories:
                repo_context = repo.get('repoContext', {})
                
                # Extract tech stack terms
                tech_stack = repo_context.get('tech_stack', {})
                if tech_stack:
                    # Primary technologies
                    if 'primary' in tech_stack:
                        dynamic_keywords['tech'].update(
                            tech.lower() for tech in tech_stack['primary'] if tech
                        )
                    
                    # Secondary technologies
                    if 'secondary' in tech_stack:
                        dynamic_keywords['tech'].update(
                            tech.lower() for tech in tech_stack['secondary'] if tech
                        )
                    
                    # Key libraries
                    if 'key_libraries' in tech_stack:
                        dynamic_keywords['tech'].update(
                            lib.lower() for lib in tech_stack['key_libraries'] if lib
                        )
                
                # Extract skill manifest terms
                skill_manifest = repo_context.get('skill_manifest', {})
                if skill_manifest:
                    # Technical skills
                    if 'technical' in skill_manifest:
                        dynamic_keywords['skills'].update(
                            skill.lower() for skill in skill_manifest['technical'] if skill
                        )
                    
                    # Domain skills
                    if 'domain' in skill_manifest:
                        dynamic_keywords['skills'].update(
                            skill.lower() for skill in skill_manifest['domain'] if skill
                        )
                
                # Extract component terms
                components = repo_context.get('components', {})
                if components:
                    for component_name, component_data in components.items():
                        # Add component name
                        dynamic_keywords['components'].add(component_name.lower())
                        
                        # Add component type
                        if 'type' in component_data and component_data['type']:
                            dynamic_keywords['components'].add(component_data['type'].lower())
                        
                        # Add component description words
                        if 'description' in component_data and component_data['description']:
                            desc_words = component_data['description'].lower().split()
                            dynamic_keywords['components'].update(
                                word for word in desc_words if len(word) > 3
                            )
                
                # Extract project identity terms
                project_identity = repo_context.get('project_identity', {})
                if project_identity:
                    # Project type
                    if 'type' in project_identity and project_identity['type']:
                        dynamic_keywords['project'].add(project_identity['type'].lower())
                    
                    # Project scope
                    if 'scope' in project_identity and project_identity['scope']:
                        dynamic_keywords['project'].add(project_identity['scope'].lower())
                    
                    # Project name words
                    if 'name' in project_identity and project_identity['name']:
                        name_words = project_identity['name'].lower().split()
                        dynamic_keywords['project'].update(
                            word for word in name_words if len(word) > 3
                        )
        
        # Extract matching terms from query
        found_terms = {
            'tech': [],
            'skills': [],
            'components': [],
            'project': [],
            'general': []
        }
        
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # Check for technology matches
        for term in dynamic_keywords['tech']:
            if term in query_lower:
                found_terms['tech'].append(term)
        
        # Check for skill matches
        for term in dynamic_keywords['skills']:
            if term in query_lower:
                found_terms['skills'].append(term)
        
        # Check for component matches
        for term in dynamic_keywords['components']:
            if term in query_lower:
                found_terms['components'].append(term)
        
        # Check for project type matches
        for term in dynamic_keywords['project']:
            if term in query_lower:
                found_terms['project'].append(term)
        
        # Extract general terms (words not in predefined categories)
        all_known_terms = (dynamic_keywords['tech'] | 
                          dynamic_keywords['skills'] | 
                          dynamic_keywords['components'] | 
                          dynamic_keywords['project'])
        
        for word in query_words:
            if len(word) > 3 and word not in all_known_terms:
                found_terms['general'].append(word)
        
        return found_terms
    
    def calculate_repo_relevance_score(self, repo: Dict, query: str, search_terms: Dict) -> float:
        """
        Calculate relevance score for a repository based on query using repo context structure.
        
        Args:
            repo: Repository dictionary with context
            query: User query string
            search_terms: Pre-extracted search terms
            
        Returns:
            Relevance score as float
        """
        
        score = 0.0
        query_lower = query.lower()
        
        # Get repository context
        repo_context = repo.get('repoContext', {})
        repo_name = repo.get('name', '').lower()
        repo_description = repo.get('description', '').lower()
        repo_language = repo.get('language', '').lower()
        repo_topics = [topic.lower() for topic in repo.get('topics', [])]
        
        # 1. TECH STACK SCORING
        tech_stack = repo_context.get('tech_stack', {})
        
        # Primary tech stack
        if 'primary' in tech_stack:
            primary_tech = [tech.lower() for tech in tech_stack['primary']]
            for term in search_terms['tech']:
                if any(term in tech for tech in primary_tech):
                    score += 3.0  # High score for primary tech match
        
        # Secondary tech stack
        if 'secondary' in tech_stack:
            secondary_tech = [tech.lower() for tech in tech_stack['secondary']]
            for term in search_terms['tech']:
                if any(term in tech for tech in secondary_tech):
                    score += 2.0  # Medium score for secondary tech match
        
        # Key libraries
        if 'key_libraries' in tech_stack:
            key_libraries = [lib.lower() for lib in tech_stack['key_libraries']]
            for term in search_terms['tech']:
                if any(term in lib for lib in key_libraries):
                    score += 2.5  # High score for exact library match
        
        # 2. SKILL MANIFEST SCORING
        skill_manifest = repo_context.get('skill_manifest', {})
        
        # Technical skills
        if 'technical' in skill_manifest:
            technical_skills = [skill.lower() for skill in skill_manifest['technical']]
            for term in search_terms['skills']:
                if any(term in skill for skill in technical_skills):
                    score += 1.8  # Good score for technical skill match
        
        # Domain skills
        if 'domain' in skill_manifest:
            domain_skills = [skill.lower() for skill in skill_manifest['domain']]
            for term in search_terms['skills']:
                if any(term in skill for skill in domain_skills):
                    score += 1.5  # Good score for domain skill match
        
        # 3. COMPONENTS SCORING
        components = repo_context.get('components', {})
        if components:
            for component_name, component_data in components.items():
                component_type = component_data.get('type', '').lower()
                component_desc = component_data.get('description', '').lower()
                
                # Check if query matches component type or description
                for term in search_terms['components']:
                    if (term in component_type or 
                        term in component_desc or 
                        term in component_name.lower()):
                        score += 1.2  # Medium score for component match
        
        # 4. PROJECT IDENTITY SCORING
        project_identity = repo_context.get('project_identity', {})
        if project_identity:
            project_name = project_identity.get('name', '').lower()
            project_type = project_identity.get('type', '').lower()
            project_desc = project_identity.get('description', '').lower()
            
            # Check project identity matches
            for term in search_terms['project']:
                if (term in project_name or 
                    term in project_type or 
                    term in project_desc):
                    score += 1.0  # Base score for project identity match
        
        # 5. GENERAL TERMS SCORING
        for term in search_terms['general']:
            if (term in repo_name or 
                term in repo_description or 
                term in repo_language or 
                any(term in topic for topic in repo_topics)):
                score += 0.8  # Score for general term match
        
        # 6. BONUS SCORING
        # Boost score for repos with comprehensive context
        if repo_context:
            if tech_stack.get('primary'):
                score += 0.5  # Bonus for having primary tech stack
            if skill_manifest.get('technical'):
                score += 0.3  # Bonus for having technical skills
            if components:
                score += 0.2  # Bonus for having components
            if project_identity.get('description'):
                score += 0.2  # Bonus for having project description
        
        # Boost score for recently updated repos
        if repo.get('updated_at'):
            try:
                from datetime import datetime
                updated_date = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                days_since_update = (datetime.now().replace(tzinfo=updated_date.tzinfo) - updated_date).days
                if days_since_update < 365:  # Updated within last year
                    score += 0.5
            except:
                pass
        
        return score
    
    def get_matched_categories(self, repo: Dict, search_terms: Dict) -> List[str]:
        """
        Get categories that matched for this repository (for debugging/explanation).
        
        Args:
            repo: Repository dictionary
            search_terms: Pre-extracted search terms
            
        Returns:
            List of matched category names
        """
        matched = []
        
        # Check what categories had matches
        if any(search_terms['tech']):
            matched.append('technology')
        if any(search_terms['skills']):
            matched.append('skills')
        if any(search_terms['components']):
            matched.append('components')
        if any(search_terms['project']):
            matched.append('project_type')
        
        return matched
    
    def filter_repositories_with_terms(self, query: str, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
        """
        Filter repositories using pre-extracted search terms (optimized version).
        
        Args:
            query: User query string
            repositories: List of repository dictionaries
            search_terms: Pre-extracted search terms
            
        Returns:
            List of filtered repositories sorted by relevance
        """
        logger.info(f"Filtering {len(repositories)} repositories using pre-extracted search terms")
        
        scored_repos = []
        
        for repo in repositories:
            # Calculate relevance score using pre-extracted search terms
            score = self.calculate_repo_relevance_score(repo, query.lower(), search_terms)
            
            if score > 0:
                scored_repos.append({
                    'repo': repo,
                    'relevance_score': score,
                    'matched_categories': self.get_matched_categories(repo, search_terms)
                })
        
        # Sort by relevance score and return top repositories
        scored_repos.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Log scoring details for debugging
        logger.info(f"Top scoring repositories:")
        for i, item in enumerate(scored_repos[:5]):
            logger.info(f"  {i+1}. {item['repo']['name']}: {item['relevance_score']:.2f}")
        
        return [item['repo'] for item in scored_repos[:10]]
    
    def fetch_repository_context_files(self, repo_name: str) -> Dict[str, str]:
        """
        Fetch additional context files for a repository.
        
        Args:
            repo_name: Repository name
            
        Returns:
            Dictionary of context files content
        """
        if not self.gh_client:
            logger.warning("GitHub client not available for file fetching")
            return {}
        
        context_files = {}
        
        # Define the files we want to fetch
        file_mappings = {
            'readme': ['README.md', 'readme.md', 'Readme.md'],
            'skills_index': ['SKILLS-INDEX.md', 'skills-index.md', 'Skills-Index.md'],
            'architecture': ['ARCHITECTURE.md', 'architecture.md', 'Architecture.md', 'ARCHITECHURE.md'],
            'project_manifest': ['PROJECT-MANIFEST.md', 'project-manifest.md', 'Project-Manifest.md']
        }
        
        # Try to fetch each type of file
        for file_type, possible_names in file_mappings.items():
            for file_name in possible_names:
                try:
                    file_content = self.gh_client.get_file_content(self.username, repo_name, file_name)
                    if file_content and isinstance(file_content, str):
                        context_files[file_type] = file_content
                        logger.debug(f"Fetched {file_name} for {repo_name}")
                        break  # Found the file, no need to try other names
                except Exception as e:
                    logger.debug(f"Failed to fetch {file_name} from {repo_name}: {str(e)}")
                    continue
        
        return context_files
    
    def build_enhanced_context(self, repositories: List[Dict]) -> str:
        """
        Build comprehensive context for AI from filtered repositories.
        
        Args:
            repositories: List of filtered repository dictionaries
            
        Returns:
            Enhanced context string for AI processing
        """
        context_parts = []
        
        # Add summary of found repositories
        if repositories:
            context_parts.append(f"Found {len(repositories)} relevant repositories for your query.")
            
            # Process each repository to fetch complete context
            for i, repo in enumerate(repositories, 1):
                repo_name = repo.get('name', 'Unknown')
                repo_context = repo.get('repoContext', {})
                
                logger.info(f"Building context for repository: {repo_name}")
                
                # Start building repository information
                repo_info = []
                repo_info.append(f"\n{'='*60}")
                repo_info.append(f"REPOSITORY {i}: {repo_name}")
                repo_info.append(f"{'='*60}")
                
                # Add basic repository metadata
                if repo.get('description'):
                    repo_info.append(f"Description: {repo['description']}")
                
                if repo.get('language'):
                    repo_info.append(f"Primary Language: {repo['language']}")
                
                if repo.get('topics'):
                    repo_info.append(f"Topics: {', '.join(repo['topics'])}")
                
                # Add technology stack from repo context
                tech_stack = repo_context.get('tech_stack', {})
                if tech_stack:
                    repo_info.append(f"\nTECHNOLOGY STACK:")
                    if tech_stack.get('primary'):
                        repo_info.append(f"  Primary: {', '.join(tech_stack['primary'])}")
                    if tech_stack.get('secondary'):
                        repo_info.append(f"  Secondary: {', '.join(tech_stack['secondary'])}")
                    if tech_stack.get('key_libraries'):
                        repo_info.append(f"  Key Libraries: {', '.join(tech_stack['key_libraries'])}")
                
                # Add skill manifest from repo context
                skill_manifest = repo_context.get('skill_manifest', {})
                if skill_manifest:
                    repo_info.append(f"\nSKILLS DEMONSTRATED:")
                    if skill_manifest.get('technical'):
                        repo_info.append(f"  Technical: {', '.join(skill_manifest['technical'][:5])}{'...' if len(skill_manifest['technical']) > 5 else ''}")
                    if skill_manifest.get('domain'):
                        repo_info.append(f"  Domain: {', '.join(skill_manifest['domain'][:3])}{'...' if len(skill_manifest['domain']) > 3 else ''}")
                
                # Add project identity from repo context
                project_identity = repo_context.get('project_identity', {})
                if project_identity:
                    repo_info.append(f"\nPROJECT DETAILS:")
                    if project_identity.get('type'):
                        repo_info.append(f"  Type: {project_identity['type']}")
                    if project_identity.get('scope'):
                        repo_info.append(f"  Scope: {project_identity['scope']}")
                    if project_identity.get('description'):
                        repo_info.append(f"  Project Description: {project_identity['description']}")
                
                # Add components from repo context
                components = repo_context.get('components', {})
                if components:
                    repo_info.append(f"\nARCHITECTURE COMPONENTS:")
                    for comp_name, comp_data in list(components.items())[:5]:  # Limit to 5 components
                        comp_type = comp_data.get('type', 'Unknown')
                        comp_desc = comp_data.get('description', 'No description')
                        repo_info.append(f"  {comp_name} ({comp_type}): {comp_desc}")
                    if len(components) > 5:
                        repo_info.append(f"  ... and {len(components) - 5} more components")
                
                # Fetch additional context files
                additional_files = self.fetch_repository_context_files(repo_name)
                
                # Add README content if available
                if additional_files.get('readme'):
                    repo_info.append(f"\nREADME CONTENT:")
                    repo_info.append(f"{additional_files['readme'][:1500]}{'...' if len(additional_files['readme']) > 1500 else ''}")
                
                # Add SKILLS-INDEX content if available
                if additional_files.get('skills_index'):
                    repo_info.append(f"\nSKILLS INDEX:")
                    repo_info.append(f"{additional_files['skills_index'][:1000]}{'...' if len(additional_files['skills_index']) > 1000 else ''}")
                
                # Add ARCHITECTURE content if available
                if additional_files.get('architecture'):
                    repo_info.append(f"\nARCHITECTURE DOCUMENTATION:")
                    repo_info.append(f"{additional_files['architecture'][:1000]}{'...' if len(additional_files['architecture']) > 1000 else ''}")
                
                # Add PROJECT-MANIFEST content if available
                if additional_files.get('project_manifest'):
                    repo_info.append(f"\nPROJECT MANIFEST:")
                    repo_info.append(f"{additional_files['project_manifest'][:1000]}{'...' if len(additional_files['project_manifest']) > 1000 else ''}")
                
                context_parts.append('\n'.join(repo_info))
        
        # Build the complete enhanced context
        enhanced_context = '\n\n'.join(context_parts)
        
        # Log context size for monitoring
        logger.info(f"Built enhanced context with {len(enhanced_context)} characters for {len(repositories)} repositories")
        
        return enhanced_context
    
    def query_ai_with_context(self, query: str, enhanced_context: str) -> str:
        """
        Query the AI assistant with enhanced context.
        
        Args:
            query: User query string
            enhanced_context: Built context from repositories
            
        Returns:
            AI response string
        """
        logger.info("Starting enhanced AI assistant query")
        
        # Add tracing for request sequence
        request_id = f"req-{int(time.time())}"
        logger.info(f"Request ID: {request_id} - Processing enhanced query: {query[:100]}...")
        
        # Create system message with comprehensive repository context
        system_message = f"""You are an AI assistant that helps users understand Chigbu Joshua's portfolio projects.
Use the following comprehensive information about the GitHub repositories to answer questions.

PORTFOLIO REPOSITORY ANALYSIS:
{enhanced_context}

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
        
        logger.info(f"Request ID: {request_id} - Created enhanced system prompt ({len(system_message)} chars)")
        
        # Call Groq API with Llama model
        try:
            api_start = time.time()
            response = self.openai_client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query}
                ],
                max_tokens=2048,  # Increased for more comprehensive responses
                temperature=0.3
            )
            api_time = time.time() - api_start
            
            # Extract the response text
            if response.choices and len(response.choices) > 0:
                answer = response.choices[0].message.content
                logger.info(f"Request ID: {request_id} - Received enhanced AI response in {api_time:.2f}s ({len(answer)} chars)")
                return answer
            else:
                logger.error(f"Request ID: {request_id} - Empty response from AI API")
                return "I'm sorry, I couldn't generate a response based on the portfolio information."
                
        except Exception as e:
            logger.error(f"Request ID: {request_id} - Error calling AI API: {str(e)}")
            raise
    
    def process_query(self, query: str, repositories: List[Dict]) -> Tuple[str, Dict]:
        """
        Main method to process a query with complete pipeline.
        
        Args:
            query: User query string
            repositories: List of repository dictionaries with context
            
        Returns:
            Tuple of (AI response, metadata dictionary)
        """
        logger.info(f"Processing query: {query[:100]}...")
        
        # Stage 1: Extract search terms
        search_terms = self.extract_search_terms(query.lower(), repositories)
        logger.info(f"Extracted search terms: {dict(search_terms)}")
        
        # Stage 2: Filter repositories
        relevant_repos = self.filter_repositories_with_terms(query, repositories, search_terms)
        logger.info(f"Found {len(relevant_repos)} relevant repositories")
        
        # Stage 3: Build enhanced context
        enhanced_context = self.build_enhanced_context(relevant_repos)
        
        # Stage 4: Query AI
        ai_response = self.query_ai_with_context(query, enhanced_context)
        
        # Build metadata
        metadata = {
            "total_repos_searched": len(repositories),
            "relevant_repos_found": len(relevant_repos),
            "query_processed": query[:100] + "..." if len(query) > 100 else query,
            "search_terms_found": {
                "tech": len(search_terms.get('tech', [])),
                "skills": len(search_terms.get('skills', [])),
                "components": len(search_terms.get('components', [])),
                "project": len(search_terms.get('project', [])),
                "general": len(search_terms.get('general', []))
            },
            "repositories_analyzed": [repo.get('name', 'Unknown') for repo in relevant_repos[:5]]
        }
        
        return ai_response, metadata


# Add this method to the AIAssistant class

def calculate_difficulty_score(self, repo: Dict) -> Dict[str, any]:
    """
    Calculate difficulty score for a repository using enhanced context analysis.
    
    Args:
        repo: Repository dictionary with context
        
    Returns:
        Dictionary containing difficulty rating, score, and reasoning
    """
    
    if not repo:
        return {
            'difficulty': 'unknown',
            'score': 0,
            'confidence': 0.0,
            'reasoning': ['No repository data available']
        }
    
    repo_context = repo.get('repoContext', {})
    difficulty_score = 0
    reasoning = []
    confidence_factors = []
    
    # 1. TECHNOLOGY STACK COMPLEXITY (0-30 points)
    tech_stack = repo_context.get('tech_stack', {})
    
    # Primary technologies complexity
    primary_tech = tech_stack.get('primary', [])
    if primary_tech:
        tech_complexity = 0
        advanced_techs = ['kubernetes', 'docker', 'microservices', 'distributed', 'blockchain', 'machine learning', 'ai', 'tensorflow', 'pytorch', 'react native', 'flutter']
        intermediate_techs = ['react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel', 'mongodb', 'postgresql', 'redis']
        
        for tech in primary_tech:
            tech_lower = tech.lower()
            if any(adv in tech_lower for adv in advanced_techs):
                tech_complexity += 3
            elif any(inter in tech_lower for inter in intermediate_techs):
                tech_complexity += 2
            else:
                tech_complexity += 1
        
        difficulty_score += min(tech_complexity, 15)
        reasoning.append(f"Primary technologies: {', '.join(primary_tech)}")
        confidence_factors.append(0.8)
    
    # Secondary technologies and libraries
    secondary_tech = tech_stack.get('secondary', [])
    key_libraries = tech_stack.get('key_libraries', [])
    
    if secondary_tech or key_libraries:
        additional_complexity = len(secondary_tech) + len(key_libraries)
        difficulty_score += min(additional_complexity, 10)
        reasoning.append(f"Additional technologies: {additional_complexity} tools/libraries")
        confidence_factors.append(0.6)
    
    # Development tools complexity
    dev_tools = tech_stack.get('development_tools', [])
    if dev_tools:
        tools_complexity = len(dev_tools)
        difficulty_score += min(tools_complexity, 5)
        reasoning.append(f"Development tools: {tools_complexity} specialized tools")
        confidence_factors.append(0.4)
    
    # 2. ARCHITECTURE COMPLEXITY (0-25 points)
    components = repo_context.get('components', {})
    
    if components:
        # Number of components
        component_count = len(components)
        difficulty_score += min(component_count * 2, 10)
        
        # Component type complexity
        complex_components = 0
        for comp_name, comp_data in components.items():
            comp_type = comp_data.get('type', '').lower()
            if any(term in comp_type for term in ['service', 'api', 'microservice', 'database', 'cache', 'queue']):
                complex_components += 1
        
        difficulty_score += min(complex_components * 3, 15)
        reasoning.append(f"Architecture: {component_count} components, {complex_components} complex components")
        confidence_factors.append(0.9)
    
    # 3. SKILL REQUIREMENTS (0-20 points)
    skill_manifest = repo_context.get('skill_manifest', {})
    
    technical_skills = skill_manifest.get('technical', [])
    domain_skills = skill_manifest.get('domain', [])
    
    if technical_skills or domain_skills:
        skill_complexity = len(technical_skills) + len(domain_skills)
        difficulty_score += min(skill_complexity, 15)
        
        # Advanced skill detection
        advanced_skills = ['devops', 'cloud', 'aws', 'azure', 'gcp', 'security', 'performance', 'scalability', 'testing', 'ci/cd']
        advanced_count = 0
        
        for skill in technical_skills + domain_skills:
            if any(adv in skill.lower() for adv in advanced_skills):
                advanced_count += 1
        
        difficulty_score += min(advanced_count, 5)
        reasoning.append(f"Skills: {skill_complexity} total skills, {advanced_count} advanced skills")
        confidence_factors.append(0.7)
    
    # 4. PROJECT SCOPE AND FEATURES (0-15 points)
    project_identity = repo_context.get('project_identity', {})
    
    if project_identity:
        project_type = project_identity.get('type', '').lower()
        project_scope = project_identity.get('scope', '').lower()
        
        # Project type complexity
        if any(term in project_type for term in ['full-stack', 'enterprise', 'distributed', 'real-time']):
            difficulty_score += 5
            reasoning.append(f"Complex project type: {project_type}")
        elif any(term in project_type for term in ['web application', 'api', 'service']):
            difficulty_score += 3
        
        # Project scope complexity
        if any(term in project_scope for term in ['large', 'complex', 'enterprise', 'production']):
            difficulty_score += 5
            reasoning.append(f"Complex project scope: {project_scope}")
        elif any(term in project_scope for term in ['medium', 'moderate']):
            difficulty_score += 2
        
        confidence_factors.append(0.6)
    
    # 5. REPOSITORY METRICS (0-10 points)
    # File count, size, and activity indicators
    repo_language = repo.get('language', '')
    repo_size = repo.get('size', 0)
    
    if repo_size > 50000:  # Large repository
        difficulty_score += 5
        reasoning.append(f"Large repository size: {repo_size} KB")
    elif repo_size > 10000:  # Medium repository
        difficulty_score += 2
    
    # Language complexity
    complex_languages = ['c++', 'rust', 'go', 'scala', 'haskell', 'assembly']
    if repo_language and repo_language.lower() in complex_languages:
        difficulty_score += 3
        reasoning.append(f"Complex primary language: {repo_language}")
    
    confidence_factors.append(0.5)
    
    # 6. INTEGRATION AND DEPLOYMENT (0-10 points)
    # Check for deployment complexity
    if any(key in repo_context for key in ['deployment_workflow', 'ci_cd', 'infrastructure']):
        difficulty_score += 5
        reasoning.append("Has deployment/CI-CD configuration")
        confidence_factors.append(0.7)
    
    # Calculate final difficulty rating
    max_possible_score = 100
    normalized_score = min(difficulty_score, max_possible_score)
    
    # Determine difficulty level
    if normalized_score >= 75:
        difficulty_level = 'expert'
    elif normalized_score >= 50:
        difficulty_level = 'advanced'
    elif normalized_score >= 25:
        difficulty_level = 'intermediate'
    else:
        difficulty_level = 'beginner'
    
    # Calculate confidence based on available data
    avg_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.3
    
    return {
        'difficulty': difficulty_level,
        'score': normalized_score,
        'confidence': round(avg_confidence, 2),
        'reasoning': reasoning,
        'breakdown': {
            'technology_complexity': min(difficulty_score, 30),
            'architecture_complexity': min(len(components) * 2 + sum(1 for comp in components.values() if 'service' in comp.get('type', '').lower()) * 3, 25),
            'skill_requirements': min(len(technical_skills) + len(domain_skills), 20),
            'project_scope': min(10, 10),  # Simplified for this example
            'repository_metrics': min(5 if repo_size > 50000 else 2 if repo_size > 10000 else 0, 10)
        }
    }

def get_difficulty_rating(self, repo: Dict) -> str:
    """
    Get simple difficulty rating for a repository.
    
    Args:
        repo: Repository dictionary with context
        
    Returns:
        String difficulty rating ('beginner', 'intermediate', 'advanced', 'expert')
    """
    difficulty_data = self.calculate_difficulty_score(repo)
    return difficulty_data['difficulty']

def get_difficulty_with_confidence(self, repo: Dict) -> Tuple[str, float]:
    """
    Get difficulty rating with confidence score.
    
    Args:
        repo: Repository dictionary with context
        
    Returns:
        Tuple of (difficulty_rating, confidence_score)
    """
    difficulty_data = self.calculate_difficulty_score(repo)
    return difficulty_data['difficulty'], difficulty_data['confidence']


# Convenience functions for backward compatibility
def extract_search_terms(query: str, repositories: List[Dict] = None) -> Dict[str, List[str]]:
    """Backward compatibility function for extract_search_terms."""
    assistant = AIAssistant()
    return assistant.extract_search_terms(query, repositories)


def filter_repositories_with_terms(query: str, repositories: List[Dict], search_terms: Dict) -> List[Dict]:
    """Backward compatibility function for filter_repositories_with_terms."""
    assistant = AIAssistant()
    return assistant.filter_repositories_with_terms(query, repositories, search_terms)


def query_ai_assistant_with_context(query: str, repositories: List[Dict]) -> str:
    """Backward compatibility function for query_ai_assistant_with_context."""
    assistant = AIAssistant()
    enhanced_context = assistant.build_enhanced_context(repositories)
    return assistant.query_ai_with_context(query, enhanced_context)


def get_repository_difficulty(repo: Dict) -> str:
    """Backward compatibility function for get_repository_difficulty."""
    assistant = AIAssistant()
    return assistant.get_difficulty_rating(repo)

def calculate_repository_difficulty_score(repo: Dict) -> Dict:
    """Backward compatibility function for calculate_repository_difficulty_score."""
    assistant = AIAssistant()
    return assistant.calculate_difficulty_score(repo)