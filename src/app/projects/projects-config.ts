export interface ProjectConfig {
  repoName: string;
  featured: boolean;
  customTitle?: string;
  customDescription?: string;
  screenshotUrl?: string;
  demoUrl?: string;
  tags?: string[];
  stack: TechStack[];
  order?: number;
}

// Tech stack interface
export interface TechStack {
    name: string;
    icon?: string; // FontAwesome class or image URL
    color?: string; // Optional color for the tech badge
}

export const FEATURED_PROJECTS: ProjectConfig[] = [
  {
    repoName: 'azure_vmss_cluster',
    customTitle: 'Kubernetes CI/CD Pipeline', // Optional override
    customDescription: 'A robust CI/CD pipeline for Kubernetes deployments with automated testing and monitoring.', // Optional override
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'https://i.imgur.com/Pu28iPG.png',
    featured: true,
    order: 1,
    tags: ['DevOps', 'Kubernetes', 'CI/CD'],
    stack: [
      { name: 'Kubernetes', icon: 'fab fa-kubernetes', color: '#326CE5' },
      { name: 'Terraform', icon: 'fab fa-terraform', color: '#58347E' },
      { name: 'Ansible', icon: 'fab fa-ansible', color: '#44A044' },
      { name: 'Containerd', icon: 'fab fa-docker', color: '#2496ED' },
      { name: 'Flux CD', icon: 'fab fa-flux', color: '#D33833' }
    ]
  },
  {
    repoName: 'AirBnB_clone_v4',
    customTitle: 'AirBnB Clone',
    customDescription: 'A full-stack AirBnB clone with booking, user authentication, and property management features.',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'https://i.imgur.com/eMZ6T3y.gif',
    featured: true,
    order: 3,
    tags: ['Full-Stack', 'Web App'],
    stack: [
      { name: 'Python', icon: 'fab fa-python', color: '#3776AB' },
      { name: 'Flask', icon: 'fas fa-flask', color: '#000000' },
      { name: 'MySQL', icon: 'fas fa-database', color: '#4479A1' },
      { name: 'SQLAlchemy', icon: 'fas fa-database', color: '#4479A1' },
      { name: 'JavaScript', icon: 'fab fa-js', color: '#F7DF1E' }
    ]
  },
  {
    repoName: 'collabHub',
    customTitle: 'CollabHub Project Management',
    customDescription: 'A collaborative project management platform with real-time updates and integrated team tools.',
    screenshotUrl: 'https://i.imgur.com/3zOi6WU.jpg',
    featured: true,
    order: 4,
    tags: ['Python', 'Flask', 'Angular', 'SQLAlchemy'],
    stack: [
      { name: 'Python', icon: 'fab fa-python', color: '#3776AB' },
      { name: 'Flask', icon: 'fas fa-flask', color: '#000000' },
      { name: 'Angular', icon: 'fab fa-angular', color: '#DD0031' },
      { name: 'SQLAlchemy', icon: 'fas fa-database', color: '#4479A1' },
      { name: 'MySQL', icon: 'fas fa-database', color: '#4479A1' }
    ]
  },
  {
    repoName: 'simple_shell',
    customTitle: 'SH Shell Clone',
    customDescription: 'A UNIX command interpreter that replicates core functionality of the sh shell with custom extensions.',
    screenshotUrl: 'https://i.imgur.com/qSbIw3l.gif',
    featured: true,
    order: 5,
    tags: ['C', 'Shell', 'Linux'],
    stack: [
      { name: 'C', icon: 'fas fa-code', color: '#A8B9CC' },
      { name: 'Unix', icon: 'fab fa-linux', color: '#FCC624' },
      { name: 'Bash', icon: 'fas fa-terminal', color: '#4EAA25' },
      { name: 'Make', icon: 'fas fa-cogs', color: '#9B4F96' }
    ]
  },
  {
    repoName: 'printf',
    customTitle: 'Printf',
    customDescription: 'Custom implementation of the C printf function with support for various format specifiers and flags.',
    screenshotUrl: 'https://i.imgur.com/ED9kJ0d.png',
    featured: true,
    order: 6,
    tags: ['C', 'Shell', 'Linux'],
    stack: [
      { name: 'C', icon: 'fas fa-code', color: '#A8B9CC' },
      { name: 'GCC', icon: 'fas fa-file-code', color: '#CD5834' },
      { name: 'Unix', icon: 'fab fa-linux', color: '#FCC624' },
      { name: 'Make', icon: 'fas fa-cogs', color: '#9B4F96' }
    ]
  }
];