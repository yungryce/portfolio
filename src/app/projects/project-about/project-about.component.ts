import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, switchMap, catchError, of, finalize } from 'rxjs';
import { GithubService, Repository } from '../../services/github.service';
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
  
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private githubService: GithubService
  ) { }

  ngOnInit(): void {
    this.loadRepositoryData();
  }

  private loadRepositoryData(): void {
    this.loading = true;
    this.error = false;

    this.repository$ = this.route.params.pipe(
      switchMap(params => {
        const repoName = params['repoName'];
        
        if (!repoName) {
          this.handleError('No repository name provided');
          return of({} as Repository);
        }

        // Use the optimized single method instead of multiple API calls
        return this.githubService.getRepositoryWithAllDocs(repoName).pipe(
          catchError(error => {
            console.error(`Error loading repository ${repoName}:`, error);
            
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
          }),
          finalize(() => {
            this.loading = false;
          })
        );
      })
    );
  }

  private handleError(message: string): void {
    this.error = true;
    this.errorMessage = message;
    this.loading = false;
  }

  // Retry functionality
  retryLoad(): void {
    this.loadRepositoryData();
  }

  // Navigation helpers
  goBack(): void {
    this.router.navigate(['/projects']);
  }

  // Repository data helper methods
  getProjectName(repo: Repository): string {
    return repo.repoContext?.project_identity?.name || repo.name;
  }

  getProjectDescription(repo: Repository): string {
    return repo.repoContext?.project_identity?.description || repo.description;
  }

  getProjectType(repo: Repository): string {
    return repo.repoContext?.project_identity?.type || 'project';
  }

  getProjectScope(repo: Repository): string {
    return repo.repoContext?.project_identity?.scope || 'general';
  }

  getPrimaryTechStack(repo: Repository): string[] {
    return repo.repoContext?.tech_stack?.primary || [repo.language].filter(Boolean);
  }

  getSecondaryTechStack(repo: Repository): string[] {
    return repo.repoContext?.tech_stack?.secondary || [];
  }

  getKeyLibraries(repo: Repository): string[] {
    return repo.repoContext?.tech_stack?.key_libraries || [];
  }

  getTechnicalSkills(repo: Repository): string[] {
    return repo.repoContext?.skill_manifest?.technical || [];
  }

  getDomainSkills(repo: Repository): string[] {
    return repo.repoContext?.skill_manifest?.domain || [];
  }

  getCompetencyLevel(repo: Repository): string {
    return repo.repoContext?.skill_manifest?.competency_level || 'intermediate';
  }

  getDifficultyRating(repo: Repository): number {
    return repo.repoContext?.metadata?.difficulty_rating || 5;
  }

  getEstimatedHours(repo: Repository): number {
    return repo.repoContext?.metadata?.estimated_hours || 0;
  }

  getPrerequisites(repo: Repository): string[] {
    return repo.repoContext?.prerequisites || [];
  }

  getTopics(repo: Repository): string[] {
    return repo.repoContext?.topics || [];
  }

  hasComponents(repo: Repository): boolean {
    return repo.repoContext?.components && Object.keys(repo.repoContext.components).length > 0;
  }

  getComponents(repo: Repository): any[] {
    if (!repo.repoContext?.components) return [];
    
    return Object.entries(repo.repoContext.components).map(([name, component]) => {
      const baseComponent = { name };
      
      // Safe object merging
      if (component && typeof component === 'object' && component !== null && !Array.isArray(component)) {
        return Object.assign(baseComponent, component);
      }
      
      // Handle non-object values
      return {
        ...baseComponent,
        value: component
      };
    });
  }

  // UI helper methods
  getDifficultyColor(rating: number): string {
    if (rating <= 3) return '#4ade80'; // green
    if (rating <= 6) return '#fbbf24'; // yellow
    if (rating <= 8) return '#fb923c'; // orange
    return '#ef4444'; // red
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
    return !!repo.readme && repo.readme.trim().length > 0;
  }

  hasArchitecture(repo: Repository): boolean {
    return !!repo.architecture && repo.architecture.trim().length > 0;
  }

  hasSkillsIndex(repo: Repository): boolean {
    return !!repo.skillsIndex && repo.skillsIndex.trim().length > 0;
  }

  hasRepoContext(repo: Repository): boolean {
    return !!repo.repoContext && Object.keys(repo.repoContext).length > 0;
  }
}
