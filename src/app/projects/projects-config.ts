export interface ProjectConfig {
  repoName: string;
  // Display overrides - only use these if you want to override repo-context data
  customTitle?: string;
  customDescription?: string;
  customScreenshotUrl?: string;
  customDemoUrl?: string;
  customTags?: string[];
}

// Tech stack interface for display configuration
export interface TechStack {
  name: string;
  icon?: string; // FontAwesome class or image URL
  color?: string; // Optional color for the tech badge
}

// Simple list of featured repositories - order matters for display
export const FEATURED_REPOSITORIES: string[] = [
  'azure_vmss_cluster',
  'authentication-FA',
  'AirBnB_clone_v4',
  'collabHub',
  'simple_shell',
  'alx-low_level_programming',
  'alx-higher_level_programming',
  'alx-system_engineering-devops',
];

// Optional: Project-specific overrides (only if needed)
export const PROJECT_OVERRIDES: { [repoName: string]: Partial<ProjectConfig> } = {
  // Example: only add entries here if you need to override repo-context data
  // 'AirBnB_clone_v4': {
  //   customTitle: 'AirBnB Clone Platform'
  // }
};

// Tech stack display configuration - maps tech names to display properties
export const TECH_STACK_DISPLAY: { [key: string]: TechStack } = {
  // Cloud & Infrastructure
  'Terraform': { name: 'Terraform', icon: 'fas fa-cube', color: '#5C4EE5' },
  'Terraform 1.0+': { name: 'Terraform', icon: 'fas fa-cube', color: '#5C4EE5' },
  'Ansible': { name: 'Ansible', icon: 'fas fa-cogs', color: '#EE0000' },
  'Ansible 2.9+': { name: 'Ansible', icon: 'fas fa-cogs', color: '#EE0000' },
  'Kubernetes': { name: 'Kubernetes', icon: 'fas fa-dharmachakra', color: '#326CE5' },
  'Kubernetes 1.24+': { name: 'Kubernetes', icon: 'fas fa-dharmachakra', color: '#326CE5' },
  'Azure VMSS': { name: 'Azure VMSS', icon: 'fab fa-microsoft', color: '#0078D4' },
  'Azure CLI': { name: 'Azure CLI', icon: 'fab fa-microsoft', color: '#0078D4' },
  'Flux CD': { name: 'Flux CD', icon: 'fas fa-sync-alt', color: '#5468FF' },
  'Flux CD 2.0': { name: 'Flux CD', icon: 'fas fa-sync-alt', color: '#5468FF' },
  'Containerd': { name: 'Containerd', icon: 'fab fa-docker', color: '#2496ED' },
  'Containerd 1.6+': { name: 'Containerd', icon: 'fab fa-docker', color: '#2496ED' },
  'Flannel CNI': { name: 'Flannel CNI', icon: 'fas fa-network-wired', color: '#0066CC' },
  
  // Programming Languages
  'Python': { name: 'Python', icon: 'fab fa-python', color: '#3776AB' },
  'Python 3.8+': { name: 'Python', icon: 'fab fa-python', color: '#3776AB' },
  'JavaScript': { name: 'JavaScript', icon: 'fab fa-js-square', color: '#F7DF1E' },
  'TypeScript': { name: 'TypeScript', icon: 'fab fa-js-square', color: '#3178C6' },
  'C': { name: 'C', icon: 'fas fa-code', color: '#A8B9CC' },
  
  // Frameworks & Libraries
  'Flask': { name: 'Flask', icon: 'fas fa-flask', color: '#000000' },
  'Angular': { name: 'Angular', icon: 'fab fa-angular', color: '#DD0031' },
  'SQLAlchemy': { name: 'SQLAlchemy', icon: 'fas fa-database', color: '#4479A1' },
  
  // Databases
  'MySQL': { name: 'MySQL', icon: 'fas fa-database', color: '#4479A1' },
  
  // Development Tools
  'GCC': { name: 'GCC', icon: 'fas fa-file-code', color: '#CD5834' },
  'Make': { name: 'Make', icon: 'fas fa-cogs', color: '#9B4F96' },
  'Git': { name: 'Git', icon: 'fab fa-git-alt', color: '#F05032' },
  'Visual Studio Code': { name: 'VS Code', icon: 'fas fa-code', color: '#007ACC' },
  'kubectl': { name: 'kubectl', icon: 'fas fa-dharmachakra', color: '#326CE5' },
  'terraform': { name: 'Terraform CLI', icon: 'fas fa-cube', color: '#5C4EE5' },
  'ansible': { name: 'Ansible CLI', icon: 'fas fa-cogs', color: '#EE0000' },
  'flux': { name: 'Flux CLI', icon: 'fas fa-sync-alt', color: '#5468FF' },
  
  // Operating Systems
  'Unix': { name: 'Unix', icon: 'fab fa-linux', color: '#FCC624' },
  'Linux': { name: 'Linux', icon: 'fab fa-linux', color: '#FCC624' },
  
  // Terminal & Shell
  'Bash': { name: 'Bash', icon: 'fas fa-terminal', color: '#4EAA25' },
  
  // Testing & Validation
  'terraform validate': { name: 'Terraform Validate', icon: 'fas fa-check-circle', color: '#5C4EE5' },
  'ansible-lint': { name: 'Ansible Lint', icon: 'fas fa-check-circle', color: '#EE0000' },
  'yamllint': { name: 'YAML Lint', icon: 'fas fa-check-circle', color: '#CB171E' },
  'kubernetes validation': { name: 'K8s Validation', icon: 'fas fa-check-circle', color: '#326CE5' },
  
  // Azure Services
  'Azure Provider': { name: 'Azure Provider', icon: 'fab fa-microsoft', color: '#0078D4' },
  'Azure Provider ~>3.0': { name: 'Azure Provider', icon: 'fab fa-microsoft', color: '#0078D4' },
  'Azure Resource Manager': { name: 'Azure ARM', icon: 'fab fa-microsoft', color: '#0078D4' },
  'Azure Key Vault': { name: 'Key Vault', icon: 'fas fa-key', color: '#0078D4' },
  'Azure Load Balancer': { name: 'Load Balancer', icon: 'fas fa-balance-scale', color: '#0078D4' },
  'Azure Virtual Network': { name: 'Virtual Network', icon: 'fas fa-network-wired', color: '#0078D4' }
};

// Helper functions to extract data from repo context
export class ProjectConfigHelper {
  static getProjectTitle(repoContext: any, repoName: string): string {
    const override = PROJECT_OVERRIDES[repoName]?.customTitle;
    return override || 
           repoContext?.project_identity?.name || 
           repoName.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
  }

  static getProjectDescription(repoContext: any, repoName: string): string {
    const override = PROJECT_OVERRIDES[repoName]?.customDescription;
    return override || 
           repoContext?.project_identity?.description || 
           'No description available';
  }

  static getScreenshotUrl(repoContext: any, repoName: string): string | undefined {
    const override = PROJECT_OVERRIDES[repoName]?.customScreenshotUrl;
    return override || 
           repoContext?.project_identity?.screenshotUrl;
  }

  static getDemoUrl(repoContext: any, repoName: string): string | undefined {
    const override = PROJECT_OVERRIDES[repoName]?.customDemoUrl;
    return override || 
           repoContext?.demo_url;
  }

  static getProjectTags(repoContext: any, repoName: string): string[] {
    const override = PROJECT_OVERRIDES[repoName]?.customTags;
    if (override) return override;
    
    // Extract from repo context topics
    const topics = repoContext?.topics || [];
    const skillDomains = repoContext?.skill_manifest?.domain || [];
    const projectType = repoContext?.project_identity?.type || '';
    const projectScope = repoContext?.project_identity?.scope || '';
    
    // Combine and deduplicate, filter out empty values
    const allTags = [...topics, ...skillDomains, projectType, projectScope]
      .filter(tag => tag && typeof tag === 'string' && tag.trim().length > 0);
    
    return [...new Set(allTags)];
  }

  static getTechStack(repoContext: any): TechStack[] {
    const techStack: TechStack[] = [];
    
    // Get primary and secondary tech stack from repo context
    const primary = repoContext?.tech_stack?.primary || [];
    const secondary = repoContext?.tech_stack?.secondary || [];
    const keyLibraries = repoContext?.tech_stack?.key_libraries || [];
    
    // Combine primary, secondary (limited), and key libraries (limited)
    const allTech = [
      ...primary,
      ...secondary.slice(0, 3),
      ...keyLibraries.slice(0, 2)
    ];
    
    allTech.forEach(tech => {
      const displayConfig = TECH_STACK_DISPLAY[tech];
      
      if (displayConfig) {
        techStack.push(displayConfig);
      } else {
        // Fallback for unmapped technologies
        const techName = tech.split(' ')[0]; // Get base name (e.g., "Terraform 1.0+" -> "Terraform")
        techStack.push({
          name: techName,
          icon: 'fas fa-code',
          color: '#6B7280'
        });
      }
    });
    
    // Remove duplicates based on name
    const uniqueTechStack = techStack.filter((tech, index, self) => 
      index === self.findIndex(t => t.name === tech.name)
    );
    
    return uniqueTechStack;
  }

  static getProjectMetrics(repoContext: any): {
    difficulty: string;
    estimatedHours: number;
    competencyLevel: string;
    projectType: string;
    projectScope: string;
    version: string;
    curriculumStage: string;
  } {
    return {
      difficulty: repoContext?.assessment?.difficulty || 'intermediate',
      estimatedHours: repoContext?.assessment?.estimated_hours || 0,
      competencyLevel: repoContext?.skill_manifest?.competency_level || 'intermediate',
      projectType: repoContext?.project_identity?.type || 'project',
      projectScope: repoContext?.project_identity?.scope || 'general',
      version: repoContext?.project_identity?.version || '1.0.0',
      curriculumStage: repoContext?.project_identity?.curriculum_stage || 'main'
    };
  }

  static getProjectOutcomes(repoContext: any): {
    primaryOutcomes: string[];
    skillsAcquired: string[];
    deliverables: string[];
  } {
    const outcomes = repoContext?.outcomes || {};
    return {
      primaryOutcomes: outcomes.primary || [],
      skillsAcquired: outcomes.skills_acquired || [],
      deliverables: outcomes.deliverables || []
    };
  }

  static getProjectSkills(repoContext: any): {
    technical: string[];
    domain: string[];
    prerequisites: string[];
  } {
    const skillManifest = repoContext?.skill_manifest || {};
    return {
      technical: skillManifest.technical || [],
      domain: skillManifest.domain || [],
      prerequisites: skillManifest.prerequisites || []
    };
  }
}