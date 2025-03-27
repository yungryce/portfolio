export interface ProjectConfig {
  repoName: string;
  customTitle?: string;
  customDescription?: string;
  screenshotUrl?: string;
  demoUrl?: string;
  featured: boolean;
  order?: number;
  tags?: string[];
}

export const FEATURED_PROJECTS: ProjectConfig[] = [
  {
    repoName: 'azure_vmss_cluster',
    customTitle: 'Cluster Devops Pipeline', // Optional override
    customDescription: 'This explores end to end pipeline for Azure VMSS cluster', // Optional override
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'assets/images/projects/project1-screenshot.png',
    featured: true,
    order: 1,
    tags: ['Terraform', 'Ansible', 'Kubernetes', 'Flux CD']
  },
  {
    repoName: 'collabHub',
    customDescription: 'Another awesome project that showcases my skills.',
    screenshotUrl: 'assets/images/projects/project2-screenshot.png',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    featured: true,
    order: 2,
    tags: ['Python', 'Flask', 'Angular', 'SQLAlchemy']
  },
  {
    repoName: 'AirBnB_clone_v4',
    customTitle: 'AirBnB Clone',
    customDescription: 'Another awesome project that showcases my skills.',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'assets/images/projects/project3-screenshot.png',
    featured: true,
    order: 3,
    tags: ['Python', 'Flask', 'SQLAlchemy']
  },
  {
    repoName: 'simple_shell',
    customTitle: 'SH Shell Clone',
    customDescription: 'This is a simple shell implementation in C.',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'assets/images/projects/project4-screenshot.png',
    featured: true,
    order: 4,
    tags: ['C', 'Shell', 'Linux']
  },
  {
    repoName: 'printf',
    customTitle: 'Printf Clone',
    customDescription: 'This is a printf implementation in C.',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'assets/images/projects/project5-screenshot.png',
    featured: true,
    order: 5,
    tags: ['C', 'Shell', 'Linux']
  },
  {
    repoName: 'python_function_apps ',
    customTitle: 'Implementation of tools built using Azure Function Apps on Python',
    customDescription: 'A simple Kubernetes pipeline using Jenkins.',
    // demoUrl: 'https://example.com/demo', // Optional demo URL,
    screenshotUrl: 'assets/images/projects/project6-screenshot.png',
    featured: true,
    order: 6,
    tags: ['Azure', 'Function App', 'Python']
  }
];