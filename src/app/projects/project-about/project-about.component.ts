import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, switchMap, catchError, of, tap } from 'rxjs';
import { GithubService, Repository } from '../../services/github.service';
import { ProjectConfigHelper, TechStack } from '../projects-config';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';

@Component({
  selector: 'app-project-about',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './project-about.component.html',
  styleUrls: ['./project-about.component.css']
})
export class ProjectAboutComponent implements OnInit {
  repository$!: Observable<Repository>;
  loading = true;
  error = false;
  errorMessage = '';
  
  // Tab state management
  activeTab = 'readme';
  
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private githubService: GithubService
  ) { }

  ngOnInit(): void {
    console.log('ProjectAboutComponent: ngOnInit called');
    this.loadRepositoryData();
  }

  private loadRepositoryData(): void {
    console.log('ProjectAboutComponent: loadRepositoryData started');
    this.loading = true;
    this.error = false;
    this.errorMessage = '';

    this.repository$ = this.route.params.pipe(
      tap(params => {
        console.log('ProjectAboutComponent: Route params received:', params);
        this.loading = true;
        this.error = false;
      }),
      switchMap(params => {
        const repoName = params['repoName'];
        console.log('ProjectAboutComponent: Extracted repoName:', repoName);
        
        if (!repoName) {
          console.error('ProjectAboutComponent: No repository name provided');
          this.handleError('No repository name provided');
          return of({} as Repository);
        }

        console.log(`ProjectAboutComponent: Calling githubService.getRepositoryWithAllDocs(${repoName})`);

        // Use the optimized method to get complete repository data
        return this.githubService.getRepositoryWithAllDocs(repoName).pipe(
          tap(repo => {
            console.log('ProjectAboutComponent: Repository loaded successfully:', repo);
            console.log('ProjectAboutComponent: Setting loading to false');
            this.loading = false;
          }),
          catchError(error => {
            console.error(`ProjectAboutComponent: Error loading repository ${repoName}:`, error);
            console.error('ProjectAboutComponent: Error details:', {
              status: error.status,
              message: error.message,
              error: error
            });
            
            // Handle specific error cases
            if (error.status === 404) {
              this.handleError(`Repository "${repoName}" not found`);
            } else if (error.status === 403) {
              this.handleError('API rate limit exceeded. Please try again later.');
            } else if (error.status === 0) {
              this.handleError('Network error. Please check your connection.');
            } else {
              this.handleError('Failed to load repository data. Please try again.');
            }
            
            return of({} as Repository);
          })
        );
      })
    );
    
    console.log('ProjectAboutComponent: Observable created, subscribing for debug...');
    
    // Add a subscription for debugging (remove this after debugging)
    this.repository$.subscribe({
      next: (repo) => {
        console.log('ProjectAboutComponent: Observable emitted:', repo);
        console.log('ProjectAboutComponent: Loading state:', this.loading);
        console.log('ProjectAboutComponent: Error state:', this.error);
      },
      error: (err) => {
        console.error('ProjectAboutComponent: Observable error:', err);
      },
      complete: () => {
        console.log('ProjectAboutComponent: Observable completed');
      }
    });
  }

  private handleError(message: string): void {
    this.error = true;
    this.errorMessage = message;
    this.loading = false;
    console.error('ProjectAboutComponent Error:', message);
  }

  // Tab management
  setActiveTab(tab: string): void {
    this.activeTab = tab;
  }

  // Retry functionality
  retryLoad(): void {
    this.loadRepositoryData();
  }

  // Navigation helpers
  goBack(): void {
    this.router.navigate(['/projects']);
  }

  // Repository data helper methods using ProjectConfigHelper
  getProjectTitle(repo: Repository): string {
    if (!repo || !repo.name) return 'Unknown Project';
    return ProjectConfigHelper.getProjectTitle(repo.repoContext, repo.name);
  }

  getProjectDescription(repo: Repository): string {
    if (!repo || !repo.name) return 'No description available';
    return ProjectConfigHelper.getProjectDescription(repo.repoContext, repo.name);
  }

  getScreenshotUrl(repo: Repository): string | undefined {
    if (!repo || !repo.name) return undefined;
    return ProjectConfigHelper.getScreenshotUrl(repo.repoContext, repo.name);
  }

  getProjectTags(repo: Repository): string[] {
    if (!repo || !repo.name) return [];
    return ProjectConfigHelper.getProjectTags(repo.repoContext, repo.name);
  }

  getTechStack(repo: Repository): TechStack[] {
    if (!repo || !repo.repoContext) return [];
    return ProjectConfigHelper.getTechStack(repo.repoContext);
  }

  getProjectMetrics(repo: Repository) {
    if (!repo || !repo.repoContext) return {};
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext);
  }

  // Specific data extraction methods with null checks
  getProjectType(repo: Repository): string {
    return repo?.repoContext?.project_identity?.type || 'project';
  }

  getProjectScope(repo: Repository): string {
    return repo?.repoContext?.project_identity?.scope || 'general';
  }

  getProjectVersion(repo: Repository): string {
    return repo?.repoContext?.project_identity?.version || '1.0.0';
  }

  getCurriculumStage(repo: Repository): string {
    return repo?.repoContext?.project_identity?.curriculum_stage || 'main';
  }

  getPrimaryTechStack(repo: Repository): string[] {
    return repo?.repoContext?.tech_stack?.primary || [repo?.language].filter(Boolean);
  }

  getSecondaryTechStack(repo: Repository): string[] {
    return repo?.repoContext?.tech_stack?.secondary || [];
  }

  getKeyLibraries(repo: Repository): string[] {
    return repo?.repoContext?.tech_stack?.key_libraries || [];
  }

  getDevelopmentTools(repo: Repository): string[] {
    return repo?.repoContext?.tech_stack?.development_tools || [];
  }

  getTestingFrameworks(repo: Repository): string[] {
    return repo?.repoContext?.tech_stack?.testing_frameworks || [];
  }

  getTechnicalSkills(repo: Repository): string[] {
    return repo?.repoContext?.skill_manifest?.technical || [];
  }

  getDomainSkills(repo: Repository): string[] {
    return repo?.repoContext?.skill_manifest?.domain || [];
  }

  getCompetencyLevel(repo: Repository): string {
    return repo?.repoContext?.skill_manifest?.competency_level || 'intermediate';
  }

  getPrerequisites(repo: Repository): string[] {
    return repo?.repoContext?.skill_manifest?.prerequisites || [];
  }

  getDifficultyRating(repo: Repository): string {
    return repo?.repoContext?.assessment?.difficulty || 'intermediate';
  }

  getEstimatedHours(repo: Repository): number {
    return repo?.repoContext?.assessment?.estimated_hours || 0;
  }

  getComplexityFactors(repo: Repository): string[] {
    return repo?.repoContext?.assessment?.complexity_factors || [];
  }

  getEvaluationCriteria(repo: Repository): string[] {
    return repo?.repoContext?.assessment?.evaluation_criteria || [];
  }

  // Component and structure data
  getMainDirectories(repo: Repository): any[] {
    return repo?.repoContext?.components?.main_directories || [];
  }

  getIntegrationPoints(repo: Repository): any[] {
    return repo?.repoContext?.components?.integration_points || [];
  }

  getKeyFiles(repo: Repository): string[] {
    return repo?.repoContext?.files?.key_files || [];
  }

  getFilesByType(repo: Repository): any {
    return repo?.repoContext?.files?.by_type || {};
  }

  getDeploymentWorkflow(repo: Repository): any[] {
    return repo?.repoContext?.deployment_workflow || 
           repo?.repoContext?.projectStructure?.deploymentWorkflow || [];
  }

  getAssociatedProjects(repo: Repository): any[] {
    return repo?.repoContext?.associatedProjects || [];
  }

  // UI helper methods
  getDifficultyColor(difficulty: string): string {
    const colors: { [key: string]: string } = {
      'beginner': '#4ade80',
      'intermediate': '#fbbf24', 
      'advanced': '#fb923c',
      'expert': '#ef4444'
    };
    return colors[difficulty] || '#6b7280';
  }

  getCompetencyColor(level: string): string {
    const colors: { [key: string]: string } = {
      'beginner': '#10b981',
      'intermediate': '#3b82f6', 
      'advanced': '#8b5cf6',
      'expert': '#ef4444'
    };
    return colors[level] || '#6b7280';
  }

  // Content validation helpers
  hasReadme(repo: Repository): boolean {
    return !!repo?.readme && repo.readme.trim().length > 0;
  }

  hasArchitecture(repo: Repository): boolean {
    return !!repo?.architecture && repo.architecture.trim().length > 0;
  }

  hasSkillsIndex(repo: Repository): boolean {
    return !!repo?.skillsIndex && repo.skillsIndex.trim().length > 0;
  }

  hasRepoContext(repo: Repository): boolean {
    return !!repo?.repoContext && Object.keys(repo.repoContext).length > 0;
  }

  hasComponents(repo: Repository): boolean {
    return this.getMainDirectories(repo).length > 0;
  }

  hasDeploymentWorkflow(repo: Repository): boolean {
    return this.getDeploymentWorkflow(repo).length > 0;
  }

  hasAssociatedProjects(repo: Repository): boolean {
    return this.getAssociatedProjects(repo).length > 0;
  }

  // Utility methods
  formatDuration(minutes: number): string {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }

  formatFileCount(count: number): string {
    return count.toLocaleString();
  }

  // External link helpers
  openGithubRepo(repo: Repository): void {
    if (repo?.html_url) {
      window.open(repo.html_url, '_blank');
    }
  }

  openHomepage(repo: Repository): void {
    if (repo?.homepage) {
      window.open(repo.homepage, '_blank');
    }
  }
}
