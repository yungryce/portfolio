import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from helpers import (
    normalize_string,
    extract_keywords_from_text,
    extract_component_info,
    safe_get_nested_value
)

logger = logging.getLogger('portfolio.api')

class ProjectType(Enum):
    """Project type classifications for better scoring"""
    FULL_STACK_APPLICATION = "full_stack_application"
    BACKEND_SERVICE = "backend_service"
    FRONTEND_APPLICATION = "frontend_application"
    CLOUD_INFRASTRUCTURE = "cloud_infrastructure"
    DATA_SCIENCE = "data_science"
    ALGORITHM_CHALLENGE = "algorithm_challenge"
    LIBRARY_FRAMEWORK = "library_framework"
    PORTFOLIO_SHOWCASE = "portfolio_showcase"
    LEARNING_PROJECT = "learning_project"
    PRODUCTION_READY = "production_ready"
    CAPSTONE_PROJECT = "capstone_project"
    ENTERPRISE_PROJECT = "enterprise_project"

class ProjectComplexity(Enum):
    """Project complexity levels"""
    BASIC = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4

@dataclass
class RepositoryMetrics:
    """Repository quality metrics"""
    architectural_sophistication: float = 0.0
    technology_maturity: float = 0.0
    project_completeness: float = 0.0
    documentation_excellence: float = 0.0
    production_readiness: float = 0.0
    skill_demonstration: float = 0.0
    innovation_factor: float = 0.0
    enterprise_value: float = 0.0

@dataclass
class RepositoryAnalysis:
    """Complete repository analysis result"""
    name: str
    project_type: ProjectType
    complexity: ProjectComplexity
    quality_score: float
    relevance_score: float
    difficulty_score: float
    enterprise_score: float
    metrics: RepositoryMetrics
    reasoning: List[str] = field(default_factory=list)
    confidence: float = 0.0
    curriculum_stage: str = "unknown"

class RepositoryAnalyzer:
    """
    Advanced repository analyzer optimized for repo-context.json structure.
    Focuses on enterprise value, architectural sophistication, and skill demonstration.
    """
    
    def __init__(self):
        # Adjusted weights for enterprise-focused scoring
        self.quality_weights = {
            'architectural_sophistication': 0.25,
            'technology_maturity': 0.20,
            'project_completeness': 0.15,
            'documentation_excellence': 0.15,
            'production_readiness': 0.10,
            'skill_demonstration': 0.10,
            'innovation_factor': 0.05
        }
        
        self.relevance_weights = {
            'direct_match': 0.35,
            'context_match': 0.30,
            'technology_match': 0.20,
            'skill_match': 0.15
        }
        
        # Technology maturity levels (aligned with enterprise needs)
        self.tech_maturity_levels = {
            'enterprise': {
                'technologies': ['kubernetes', 'docker', 'terraform', 'ansible', 'azure', 'aws', 
                               'microservices', 'postgresql', 'redis', 'nginx', 'jenkins', 'grafana'],
                'score_multiplier': 1.5,
                'base_score': 15
            },
            'professional': {
                'technologies': ['react', 'angular', 'vue', 'node.js', 'django', 'flask', 'spring',
                               'laravel', 'mongodb', 'elasticsearch', 'rabbitmq', 'docker'],
                'score_multiplier': 1.2,
                'base_score': 10
            },
            'intermediate': {
                'technologies': ['express', 'fastapi', 'mysql', 'sqlite', 'bootstrap', 'jquery'],
                'score_multiplier': 1.0,
                'base_score': 6
            },
            'basic': {
                'technologies': ['html', 'css', 'javascript', 'python', 'java', 'c++', 'php'],
                'score_multiplier': 0.8,
                'base_score': 3
            }
        }
        
        # Curriculum stage importance (higher scores for advanced stages)
        self.curriculum_stage_multipliers = {
            'capstone': 1.5,
            'advanced': 1.3,
            'intermediate': 1.1,
            'beginner': 0.9,
            'foundation': 0.8,
            'unknown': 1.0
        }
        
        # Enterprise indicators
        self.enterprise_indicators = {
            'high_value': ['authentication', 'security', 'scalability', 'production', 'enterprise',
                          'microservices', 'api gateway', 'load balancer', 'monitoring', 'logging'],
            'architecture_patterns': ['mvc', 'microservices', 'event-driven', 'serverless', 
                                    'multi-tier', 'distributed', 'service-oriented'],
            'production_tools': ['docker', 'kubernetes', 'ci/cd', 'testing', 'monitoring',
                               'deployment', 'infrastructure', 'automation']
        }

    def analyze_repository(self, repo: Dict, query: str = None) -> RepositoryAnalysis:
        """
        Perform comprehensive repository analysis optimized for repo-context structure.
        
        Args:
            repo: Repository dictionary with context
            query: Optional query for relevance scoring
            
        Returns:
            RepositoryAnalysis object with complete assessment
        """
        repo_name = repo.get('name', 'Unknown')
        repo_context = repo.get('repoContext', {})
        
        logger.info(f"Analyzing repository: {repo_name}")
        
        # Extract project identity for enhanced analysis
        project_identity = repo_context.get('project_identity', {})
        curriculum_stage = project_identity.get('curriculum_stage', 'unknown')
        
        # Determine project type with enhanced classification
        project_type = self._classify_project_type_enhanced(repo, repo_context, project_identity)
        
        # Calculate enhanced quality metrics
        metrics = self._calculate_enhanced_quality_metrics(repo, repo_context, project_identity)
        
        # Calculate scores with curriculum stage consideration
        quality_score = self._calculate_enhanced_quality_score(metrics, curriculum_stage)
        difficulty_score = self._calculate_enhanced_difficulty_score(repo, repo_context, project_type)
        enterprise_score = self._calculate_enterprise_score(repo, repo_context, project_identity)
        relevance_score = self._calculate_enhanced_relevance_score(repo, repo_context, query) if query else 0.0
        
        # Determine complexity with project type consideration
        complexity = self._determine_enhanced_complexity(difficulty_score, project_type, curriculum_stage)
        
        # Generate enhanced reasoning
        reasoning = self._generate_enhanced_reasoning(repo, repo_context, metrics, project_type, quality_score)
        
        # Calculate confidence with repo-context completeness
        confidence = self._calculate_enhanced_confidence(repo_context, project_identity)
        
        analysis = RepositoryAnalysis(
            name=repo_name,
            project_type=project_type,
            complexity=complexity,
            quality_score=quality_score,
            relevance_score=relevance_score,
            difficulty_score=difficulty_score,
            enterprise_score=enterprise_score,
            metrics=metrics,
            reasoning=reasoning,
            confidence=confidence,
            curriculum_stage=curriculum_stage
        )
        
        logger.info(f"Enhanced analysis complete for {repo_name}: Quality={quality_score:.1f}, Enterprise={enterprise_score:.1f}, Complexity={complexity.name}")
        return analysis

    def _classify_project_type_enhanced(self, repo: Dict, repo_context: Dict, project_identity: Dict) -> ProjectType:
        """Enhanced project type classification using repo-context structure."""
        
        # Check curriculum stage first
        curriculum_stage = project_identity.get('curriculum_stage', '')
        if curriculum_stage == 'capstone':
            return ProjectType.CAPSTONE_PROJECT
        
        # Check project identity type and scope
        project_type = normalize_string(project_identity.get('type', ''))
        project_scope = normalize_string(project_identity.get('scope', ''))
        project_desc = normalize_string(project_identity.get('description', ''))
        
        # Enterprise indicators
        if any(indicator in project_desc for indicator in ['enterprise', 'production-ready', 'scalable']):
            return ProjectType.ENTERPRISE_PROJECT
        
        # Technology-based classification
        tech_stack = repo_context.get('tech_stack', {})
        primary_tech = [normalize_string(tech) for tech in tech_stack.get('primary', [])]
        
        # Cloud/Infrastructure projects
        if any(tech in ' '.join(primary_tech) for tech in ['terraform', 'ansible', 'kubernetes', 'azure', 'aws']):
            return ProjectType.CLOUD_INFRASTRUCTURE
        
        # Full-stack applications
        frontend_tech = ['react', 'angular', 'vue', 'html', 'css', 'javascript']
        backend_tech = ['django', 'flask', 'express', 'node.js', 'laravel', 'spring']
        
        has_frontend = any(tech in ' '.join(primary_tech) for tech in frontend_tech)
        has_backend = any(tech in ' '.join(primary_tech) for tech in backend_tech)
        
        if has_frontend and has_backend:
            return ProjectType.FULL_STACK_APPLICATION
        elif has_backend:
            return ProjectType.BACKEND_SERVICE
        elif has_frontend:
            return ProjectType.FRONTEND_APPLICATION
        
        # Check for portfolio/showcase projects
        if 'portfolio' in normalize_string(repo.get('name', '')):
            return ProjectType.PORTFOLIO_SHOWCASE
        
        # Algorithm challenges
        if any(term in project_desc for term in ['algorithm', 'challenge', 'problem', 'solution']):
            return ProjectType.ALGORITHM_CHALLENGE
        
        # Default based on complexity
        components = repo_context.get('components', {})
        if len(components) > 5:
            return ProjectType.ENTERPRISE_PROJECT
        elif len(components) > 2:
            return ProjectType.PRODUCTION_READY
        else:
            return ProjectType.LEARNING_PROJECT

    def _calculate_enhanced_quality_metrics(self, repo: Dict, repo_context: Dict, project_identity: Dict) -> RepositoryMetrics:
        """Calculate enhanced quality metrics using repo-context structure."""
        metrics = RepositoryMetrics()
        
        # Architectural Sophistication (based on components and outcomes)
        metrics.architectural_sophistication = self._assess_architectural_sophistication(repo_context)
        
        # Technology Maturity (enhanced with enterprise focus)
        metrics.technology_maturity = self._assess_technology_maturity(repo_context)
        
        # Project Completeness (using outcomes and deliverables)
        metrics.project_completeness = self._assess_project_completeness_enhanced(repo_context, project_identity)
        
        # Documentation Excellence (using metadata quality indicators)
        metrics.documentation_excellence = self._assess_documentation_excellence(repo_context)
        
        # Production Readiness (using assessment and quality indicators)
        metrics.production_readiness = self._assess_production_readiness_enhanced(repo, repo_context)
        
        # Skill Demonstration (using skill_manifest and competency_level)
        metrics.skill_demonstration = self._assess_skill_demonstration(repo_context)
        
        # Innovation Factor (using project uniqueness and technology combination)
        metrics.innovation_factor = self._assess_innovation_factor_enhanced(repo, repo_context, project_identity)
        
        # Enterprise Value (new metric for business value assessment)
        metrics.enterprise_value = self._assess_enterprise_value(repo_context, project_identity)
        
        return metrics

    def _assess_architectural_sophistication(self, repo_context: Dict) -> float:
        """Assess architectural sophistication using components and integration points."""
        score = 0.0
        
        components = repo_context.get('components', {})
        if not components:
            return 10.0
        
        # Component analysis
        if isinstance(components, dict):
            # Check for main_directories structure
            main_dirs = components.get('main_directories', [])
            if main_dirs:
                for directory in main_dirs:
                    complexity = directory.get('complexity', 'basic')
                    if complexity == 'advanced':
                        score += 20
                    elif complexity == 'intermediate':
                        score += 15
                    else:
                        score += 10
            
            # Check for integration points
            integration_points = components.get('integration_points', [])
            score += len(integration_points) * 10
            
            # Check for component diversity
            if len(main_dirs) >= 3:
                score += 20
            elif len(main_dirs) >= 2:
                score += 15
        else:
            # Fallback to standard component analysis
            component_count = len(components)
            score += min(component_count * 8, 40)
        
        # Architecture patterns
        project_structure = repo_context.get('projectStructure', {})
        if project_structure:
            workflow = project_structure.get('deploymentWorkflow', [])
            if len(workflow) > 2:
                score += 15
        
        return min(score, 100.0)

    def _assess_technology_maturity(self, repo_context: Dict) -> float:
        """Assess technology maturity with enterprise focus."""
        score = 0.0
        
        tech_stack = repo_context.get('tech_stack', {})
        if not tech_stack:
            return 10.0
        
        # Analyze all technology categories
        all_technologies = []
        all_technologies.extend(tech_stack.get('primary', []))
        all_technologies.extend(tech_stack.get('secondary', []))
        all_technologies.extend(tech_stack.get('key_libraries', []))
        all_technologies.extend(tech_stack.get('development_tools', []))
        all_technologies.extend(tech_stack.get('testing_frameworks', []))
        
        # Score based on technology maturity levels
        enterprise_count = 0
        professional_count = 0
        
        for tech in all_technologies:
            tech_lower = normalize_string(tech)
            
            # Check enterprise level
            for ent_tech in self.tech_maturity_levels['enterprise']['technologies']:
                if ent_tech in tech_lower:
                    score += self.tech_maturity_levels['enterprise']['base_score']
                    enterprise_count += 1
                    break
            else:
                # Check professional level
                for prof_tech in self.tech_maturity_levels['professional']['technologies']:
                    if prof_tech in tech_lower:
                        score += self.tech_maturity_levels['professional']['base_score']
                        professional_count += 1
                        break
                else:
                    # Check intermediate/basic
                    for level_name in ['intermediate', 'basic']:
                        level_data = self.tech_maturity_levels[level_name]
                        for level_tech in level_data['technologies']:
                            if level_tech in tech_lower:
                                score += level_data['base_score']
                                break
        
        # Enterprise technology bonus
        if enterprise_count >= 3:
            score *= 1.3
        elif professional_count >= 4:
            score *= 1.15
        
        return min(score, 100.0)

    def _assess_project_completeness_enhanced(self, repo_context: Dict, project_identity: Dict) -> float:
        """Enhanced project completeness using outcomes and deliverables."""
        score = 0.0
        
        # Project identity completeness
        if project_identity:
            required_fields = ['name', 'type', 'description', 'scope']
            completed_fields = sum(1 for field in required_fields if project_identity.get(field))
            score += (completed_fields / len(required_fields)) * 25
            
            # Version and independence indicators
            if project_identity.get('version'):
                score += 5
            if project_identity.get('is_independent'):
                score += 10
        
        # Outcomes assessment
        outcomes = repo_context.get('outcomes', {})
        if outcomes:
            if outcomes.get('primary'):
                score += 20
            if outcomes.get('skills_acquired'):
                score += 15
            if outcomes.get('deliverables'):
                score += 15
        
        # Tech stack completeness
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            tech_categories = ['primary', 'secondary', 'key_libraries', 'development_tools']
            completed_categories = sum(1 for cat in tech_categories if tech_stack.get(cat))
            score += (completed_categories / len(tech_categories)) * 15
        
        # Component and structure completeness
        components = repo_context.get('components', {})
        project_structure = repo_context.get('projectStructure', {})
        
        if components and project_structure:
            score += 10
        
        return min(score, 100.0)

    def _assess_documentation_excellence(self, repo_context: Dict) -> float:
        """Assess documentation quality using metadata and structure."""
        score = 0.0
        
        # Check for quality indicators
        metadata = repo_context.get('metadata', {})
        if metadata:
            quality_indicators = metadata.get('quality_indicators', {})
            if quality_indicators:
                doc_quality = quality_indicators.get('documentation_quality', '')
                if doc_quality == 'excellent':
                    score += 40
                elif doc_quality == 'good':
                    score += 30
                elif doc_quality == 'moderate':
                    score += 20
                else:
                    score += 10
        
        # Project structure documentation
        project_structure = repo_context.get('projectStructure', {})
        if project_structure:
            doc_files = project_structure.get('documentationFiles', [])
            score += min(len(doc_files) * 8, 32)
            
            # Bonus for comprehensive documentation
            comprehensive_docs = ['README.md', 'ARCHITECTURE.md', 'SKILLS-INDEX.md']
            found_docs = sum(1 for doc in comprehensive_docs if doc in doc_files)
            score += found_docs * 5
        
        # Assessment criteria (indicates thorough planning)
        assessment = repo_context.get('assessment', {})
        if assessment:
            if assessment.get('evaluation_criteria'):
                score += 15
            if assessment.get('complexity_factors'):
                score += 10
        
        return min(score, 100.0)

    def _assess_production_readiness_enhanced(self, repo: Dict, repo_context: Dict) -> float:
        """Enhanced production readiness assessment."""
        score = 0.0
        
        # Quality indicators from metadata
        metadata = repo_context.get('metadata', {})
        if metadata:
            quality_indicators = metadata.get('quality_indicators', {})
            if quality_indicators:
                prod_readiness = quality_indicators.get('production_readiness', '')
                if prod_readiness == 'high':
                    score += 35
                elif prod_readiness == 'medium':
                    score += 25
                elif prod_readiness == 'good':
                    score += 30
                else:
                    score += 15
        
        # Deployment workflow
        deployment_workflow = repo_context.get('deployment_workflow', [])
        if deployment_workflow:
            score += min(len(deployment_workflow) * 5, 25)
            
            # Check for automated deployment steps
            automation_indicators = ['terraform', 'ansible', 'ci/cd', 'automated']
            for step in deployment_workflow:
                step_desc = normalize_string(step.get('description', ''))
                if any(indicator in step_desc for indicator in automation_indicators):
                    score += 5
        
        # Prerequisites (indicates enterprise readiness)
        prerequisites = repo_context.get('prerequisites', {})
        if prerequisites:
            if prerequisites.get('technical'):
                score += 10
            if prerequisites.get('knowledge'):
                score += 10
        
        # Recent activity
        if repo.get('updated_at'):
            try:
                updated_date = datetime.fromisoformat(repo['updated_at'].replace('Z', '+00:00'))
                days_since_update = (datetime.now().replace(tzinfo=updated_date.tzinfo) - updated_date).days
                if days_since_update < 30:
                    score += 15
                elif days_since_update < 90:
                    score += 10
                elif days_since_update < 180:
                    score += 5
            except:
                pass
        
        return min(score, 100.0)

    def _assess_skill_demonstration(self, repo_context: Dict) -> float:
        """Assess skill demonstration using skill_manifest."""
        score = 0.0
        
        skill_manifest = repo_context.get('skill_manifest', {})
        if not skill_manifest:
            return 10.0
        
        # Technical skills
        technical_skills = skill_manifest.get('technical', [])
        score += min(len(technical_skills) * 3, 40)
        
        # Domain skills
        domain_skills = skill_manifest.get('domain', [])
        score += min(len(domain_skills) * 4, 32)
        
        # Competency level
        competency_level = skill_manifest.get('competency_level', '')
        if 'expert' in competency_level:
            score += 20
        elif 'advanced' in competency_level:
            score += 15
        elif 'intermediate' in competency_level:
            score += 10
        else:
            score += 5
        
        # Prerequisites (indicates depth)
        prerequisites = skill_manifest.get('prerequisites', [])
        if prerequisites:
            score += min(len(prerequisites) * 2, 8)
        
        return min(score, 100.0)

    def _assess_innovation_factor_enhanced(self, repo: Dict, repo_context: Dict, project_identity: Dict) -> float:
        """Enhanced innovation assessment."""
        score = 0.0
        
        # Project uniqueness
        project_desc = normalize_string(project_identity.get('description', ''))
        repo_name = normalize_string(repo.get('name', ''))
        
        # Penalty for common tutorial/clone patterns
        common_patterns = ['clone', 'tutorial', 'example', 'hello', 'test', 'sample']
        if any(pattern in repo_name for pattern in common_patterns):
            score += 10
        else:
            score += 30
        
        # Innovation indicators in description
        innovation_terms = ['innovative', 'novel', 'unique', 'cutting-edge', 'advanced', 'sophisticated']
        innovation_count = sum(1 for term in innovation_terms if term in project_desc)
        score += innovation_count * 5
        
        # Technology combination uniqueness
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            # Modern technology stack
            modern_tech = ['react', 'vue', 'kubernetes', 'terraform', 'microservices', 'serverless']
            all_tech = []
            all_tech.extend(tech_stack.get('primary', []))
            all_tech.extend(tech_stack.get('secondary', []))
            
            modern_count = sum(1 for tech in all_tech 
                             if any(modern in normalize_string(tech) for modern in modern_tech))
            score += min(modern_count * 8, 32)
        
        # Enterprise architecture patterns
        components = repo_context.get('components', {})
        if components:
            # Multi-layer architecture
            main_dirs = components.get('main_directories', [])
            if len(main_dirs) >= 3:
                score += 15
            
            # Integration complexity
            integration_points = components.get('integration_points', [])
            score += min(len(integration_points) * 5, 15)
        
        return min(score, 100.0)

    def _assess_enterprise_value(self, repo_context: Dict, project_identity: Dict) -> float:
        """Assess enterprise value and business impact."""
        score = 0.0
        
        # Enterprise indicators in description
        project_desc = normalize_string(project_identity.get('description', ''))
        enterprise_terms = ['enterprise', 'production', 'scalable', 'robust', 'secure', 'automated']
        
        for term in enterprise_terms:
            if term in project_desc:
                score += 8
        
        # Business value indicators
        business_terms = ['cost optimization', 'efficiency', 'automation', 'workflow', 'integration']
        for term in business_terms:
            if term in project_desc:
                score += 6
        
        # Architecture sophistication
        components = repo_context.get('components', {})
        if components:
            integration_points = components.get('integration_points', [])
            if len(integration_points) >= 2:
                score += 20
        
        # Industry relevance
        outcomes = repo_context.get('outcomes', {})
        if outcomes:
            skills_acquired = outcomes.get('skills_acquired', [])
            enterprise_skills = ['enterprise', 'production', 'scalability', 'security', 'automation']
            
            enterprise_skill_count = sum(1 for skill in skills_acquired 
                                       if any(ent_skill in normalize_string(skill) for ent_skill in enterprise_skills))
            score += enterprise_skill_count * 5
        
        return min(score, 100.0)

    def _calculate_enhanced_quality_score(self, metrics: RepositoryMetrics, curriculum_stage: str) -> float:
        """Calculate quality score with curriculum stage consideration."""
        base_score = (
            metrics.architectural_sophistication * self.quality_weights['architectural_sophistication'] +
            metrics.technology_maturity * self.quality_weights['technology_maturity'] +
            metrics.project_completeness * self.quality_weights['project_completeness'] +
            metrics.documentation_excellence * self.quality_weights['documentation_excellence'] +
            metrics.production_readiness * self.quality_weights['production_readiness'] +
            metrics.skill_demonstration * self.quality_weights['skill_demonstration'] +
            metrics.innovation_factor * self.quality_weights['innovation_factor']
        )
        
        # Apply curriculum stage multiplier
        stage_multiplier = self.curriculum_stage_multipliers.get(curriculum_stage, 1.0)
        final_score = base_score * stage_multiplier
        
        return min(final_score, 100.0)

    def _calculate_enhanced_difficulty_score(self, repo: Dict, repo_context: Dict, project_type: ProjectType) -> float:
        """Calculate difficulty with enhanced enterprise focus."""
        score = 0.0
        
        # Technology complexity
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            all_tech = []
            all_tech.extend(tech_stack.get('primary', []))
            all_tech.extend(tech_stack.get('secondary', []))
            all_tech.extend(tech_stack.get('key_libraries', []))
            
            for tech in all_tech:
                tech_lower = normalize_string(tech)
                if any(ent_tech in tech_lower for ent_tech in self.tech_maturity_levels['enterprise']['technologies']):
                    score += 15
                elif any(prof_tech in tech_lower for prof_tech in self.tech_maturity_levels['professional']['technologies']):
                    score += 10
                else:
                    score += 5
        
        # Architectural complexity
        components = repo_context.get('components', {})
        if components:
            main_dirs = components.get('main_directories', [])
            for directory in main_dirs:
                complexity = directory.get('complexity', 'basic')
                if complexity == 'advanced':
                    score += 12
                elif complexity == 'intermediate':
                    score += 8
                else:
                    score += 4
        
        # Skill requirements
        skill_manifest = repo_context.get('skill_manifest', {})
        if skill_manifest:
            competency_level = skill_manifest.get('competency_level', '')
            if 'expert' in competency_level:
                score += 25
            elif 'advanced' in competency_level:
                score += 20
            elif 'intermediate' in competency_level:
                score += 15
            else:
                score += 10
        
        # Assessment difficulty
        assessment = repo_context.get('assessment', {})
        if assessment:
            difficulty = assessment.get('difficulty', '')
            if difficulty == 'advanced':
                score += 20
            elif difficulty == 'intermediate':
                score += 15
            else:
                score += 10
        
        return min(score, 100.0)

    def _calculate_enterprise_score(self, repo: Dict, repo_context: Dict, project_identity: Dict) -> float:
        """Calculate enterprise readiness score."""
        score = 0.0
        
        # Enterprise value metric
        metrics = self._calculate_enhanced_quality_metrics(repo, repo_context, project_identity)
        score += metrics.enterprise_value * 0.4
        
        # Production readiness
        score += metrics.production_readiness * 0.3
        
        # Architectural sophistication
        score += metrics.architectural_sophistication * 0.3
        
        return min(score, 100.0)

    def _calculate_enhanced_relevance_score(self, repo: Dict, repo_context: Dict, query: str) -> float:
        """Enhanced relevance calculation with repo-context awareness."""
        if not query:
            return 0.0
        
        query_lower = normalize_string(query)
        query_words = query_lower.split()
        score = 0.0
        
        # Direct match (project identity)
        project_identity = repo_context.get('project_identity', {})
        if project_identity:
            name = normalize_string(project_identity.get('name', ''))
            desc = normalize_string(project_identity.get('description', ''))
            
            for word in query_words:
                if word in name:
                    score += 15
                if word in desc:
                    score += 10
        
        # Technology match
        tech_stack = repo_context.get('tech_stack', {})
        if tech_stack:
            all_tech = []
            all_tech.extend(tech_stack.get('primary', []))
            all_tech.extend(tech_stack.get('secondary', []))
            
            tech_text = normalize_string(' '.join(all_tech))
            for word in query_words:
                if word in tech_text:
                    score += 12
        
        # Skill match
        skill_manifest = repo_context.get('skill_manifest', {})
        if skill_manifest:
            all_skills = []
            all_skills.extend(skill_manifest.get('technical', []))
            all_skills.extend(skill_manifest.get('domain', []))
            
            skill_text = normalize_string(' '.join(all_skills))
            for word in query_words:
                if word in skill_text:
                    score += 8
        
        # Topic match
        topics = repo_context.get('topics', [])
        if topics:
            topic_text = normalize_string(' '.join(topics))
            for word in query_words:
                if word in topic_text:
                    score += 6
        
        return min(score, 100.0)

    def _determine_enhanced_complexity(self, difficulty_score: float, project_type: ProjectType, curriculum_stage: str) -> ProjectComplexity:
        """Enhanced complexity determination."""
        # Adjust thresholds based on project type and curriculum stage
        base_thresholds = [25, 50, 75]
        
        # Project type adjustments
        if project_type in [ProjectType.CAPSTONE_PROJECT, ProjectType.ENTERPRISE_PROJECT]:
            thresholds = [40, 60, 80]
        elif project_type in [ProjectType.CLOUD_INFRASTRUCTURE, ProjectType.PRODUCTION_READY]:
            thresholds = [35, 55, 75]
        elif project_type in [ProjectType.ALGORITHM_CHALLENGE, ProjectType.LEARNING_PROJECT]:
            thresholds = [20, 40, 60]
        else:
            thresholds = base_thresholds
        
        # Curriculum stage adjustments
        if curriculum_stage == 'capstone':
            thresholds = [max(t - 10, 10) for t in thresholds]
        elif curriculum_stage == 'advanced':
            thresholds = [max(t - 5, 10) for t in thresholds]
        
        if difficulty_score >= thresholds[2]:
            return ProjectComplexity.EXPERT
        elif difficulty_score >= thresholds[1]:
            return ProjectComplexity.ADVANCED
        elif difficulty_score >= thresholds[0]:
            return ProjectComplexity.INTERMEDIATE
        else:
            return ProjectComplexity.BASIC

    def _generate_enhanced_reasoning(self, repo: Dict, repo_context: Dict, metrics: RepositoryMetrics, 
                                   project_type: ProjectType, quality_score: float) -> List[str]:
        """Generate enhanced reasoning with repo-context insights."""
        reasoning = []
        
        # Project classification
        project_identity = repo_context.get('project_identity', {})
        curriculum_stage = project_identity.get('curriculum_stage', 'unknown')
        
        reasoning.append(f"Classified as {project_type.value.replace('_', ' ').title()}")
        
        if curriculum_stage != 'unknown':
            reasoning.append(f"Curriculum stage: {curriculum_stage.title()}")
        
        # Quality assessment
        if quality_score >= 85:
            reasoning.append("Exceptional quality with enterprise-grade implementation")
        elif quality_score >= 70:
            reasoning.append("High quality with professional standards")
        elif quality_score >= 55:
            reasoning.append("Good quality with solid implementation")
        else:
            reasoning.append("Basic implementation with improvement opportunities")
        
        # Specific strengths
        if metrics.architectural_sophistication >= 70:
            reasoning.append("Sophisticated multi-component architecture")
        
        if metrics.technology_maturity >= 70:
            reasoning.append("Enterprise-grade technology stack")
        
        if metrics.production_readiness >= 70:
            reasoning.append("Production-ready with comprehensive deployment workflow")
        
        if metrics.documentation_excellence >= 70:
            reasoning.append("Excellent documentation and project structure")
        
        if metrics.skill_demonstration >= 70:
            reasoning.append("Demonstrates advanced technical competencies")
        
        # Enterprise value
        if metrics.enterprise_value >= 60:
            reasoning.append("High enterprise value with business impact potential")
        
        return reasoning

    def _calculate_enhanced_confidence(self, repo_context: Dict, project_identity: Dict) -> float:
        """Calculate confidence based on repo-context completeness."""
        confidence = 0.0
        
        # Core sections presence
        core_sections = ['project_identity', 'tech_stack', 'skill_manifest', 'components']
        present_sections = sum(1 for section in core_sections if repo_context.get(section))
        confidence += (present_sections / len(core_sections)) * 0.4
        
        # Project identity completeness
        if project_identity:
            required_fields = ['name', 'type', 'description', 'scope']
            completed_fields = sum(1 for field in required_fields if project_identity.get(field))
            confidence += (completed_fields / len(required_fields)) * 0.3
        
        # Additional sections
        additional_sections = ['outcomes', 'prerequisites', 'assessment', 'metadata']
        present_additional = sum(1 for section in additional_sections if repo_context.get(section))
        confidence += (present_additional / len(additional_sections)) * 0.3
        
        return min(confidence, 1.0)

    def get_high_quality_repositories(self, repositories: List[Dict], 
                                    min_quality: float = 70.0,
                                    min_enterprise: float = 60.0,
                                    limit: int = 10) -> List[Tuple[Dict, RepositoryAnalysis]]:
        """Get high-quality repositories with enterprise focus."""
        analyzed_repos = []
        
        for repo in repositories:
            analysis = self.analyze_repository(repo)
            if (analysis.quality_score >= min_quality and 
                analysis.enterprise_score >= min_enterprise):
                analyzed_repos.append((repo, analysis))
        
        # Sort by combined quality and enterprise score
        analyzed_repos.sort(
            key=lambda x: (x[1].quality_score * 0.6 + x[1].enterprise_score * 0.4), 
            reverse=True
        )
        
        return analyzed_repos[:limit]

    def get_best_repositories_for_query(self, repositories: List[Dict], 
                                      query: str, 
                                      limit: int = 10) -> List[Tuple[Dict, RepositoryAnalysis]]:
        """Get best repositories for query with enhanced scoring."""
        analyzed_repos = []
        
        for repo in repositories:
            analysis = self.analyze_repository(repo, query)
            # Enhanced combined score: 40% quality + 30% relevance + 30% enterprise
            combined_score = (
                analysis.quality_score * 0.4 + 
                analysis.relevance_score * 0.3 + 
                analysis.enterprise_score * 0.3
            )
            analyzed_repos.append((repo, analysis, combined_score))
        
        # Sort by combined score
        analyzed_repos.sort(key=lambda x: x[2], reverse=True)
        
        return [(repo, analysis) for repo, analysis, _ in analyzed_repos[:limit]]