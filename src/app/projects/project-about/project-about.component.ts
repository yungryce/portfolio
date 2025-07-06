import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, switchMap, catchError, of, tap, Subject, takeUntil, map } from 'rxjs';
import { GithubService, Repository } from '../../services/github.service';
import { ProjectConfigHelper, TechStack } from '../projects-config';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';
import { DifficultyService, DifficultyAnalysis, DifficultyState } from '../../services/difficulty.service';

@Component({
  selector: 'app-project-about',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './project-about.component.html',
  styleUrls: ['./project-about.component.css']
})
export class ProjectAboutComponent implements OnInit, OnDestroy {
  // Fix: Type the Observable to handle null values properly
  repository$!: Observable<Repository | null>;
  loading = true;
  error = false;
  errorMessage = '';
  
  // Tab state management
  activeTab = 'readme';
  
  // Difficulty state
  difficultyState: DifficultyState = {};
  private destroy$ = new Subject<void>();
  
  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private githubService: GithubService,
    private difficultyService: DifficultyService
  ) { }

  ngOnInit(): void {
    console.log('ProjectAboutComponent: ngOnInit called');
    this.setupDifficultyStateSubscription();
    this.loadRepositoryData();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private setupDifficultyStateSubscription(): void {
    this.difficultyService.difficultyState$
      .pipe(takeUntil(this.destroy$))
      .subscribe(state => {
        this.difficultyState = state;
      });
  }

  private loadRepositoryData(): void {
    console.log('ProjectAboutComponent: Starting to load repository data');
    
    this.repository$ = this.route.paramMap.pipe(
      switchMap(params => {
        const repoName = params.get('name');
        if (!repoName) {
          throw new Error('Repository name not found in route');
        }
        
        console.log(`ProjectAboutComponent: Loading repository: ${repoName}`);
        
        return this.githubService.getRepositoryWithAllDocs(repoName).pipe(
          tap(repo => {
            if (repo) {
              console.log('ProjectAboutComponent: Repository loaded successfully:', repo);
              this.loading = false;
              
              // Check if we already have difficulty data cached
              if (!this.difficultyService.isDifficultyLoaded(repo.name) && 
                  !this.difficultyService.isDifficultyLoading(repo.name)) {
                // Trigger background fetch if not already cached
                console.log(`ProjectAboutComponent: Triggering background difficulty fetch for ${repo.name}`);
                this.difficultyService.getDifficultyAnalysis(repo.name).subscribe({
                  next: (analysis) => {
                    console.log(`ProjectAboutComponent: Difficulty analysis loaded for ${repo.name}:`, analysis);
                  },
                  error: (err) => {
                    console.warn(`ProjectAboutComponent: Failed to load difficulty for ${repo.name}:`, err);
                  }
                });
              }
            }
          }),
          catchError(error => {
            console.error('ProjectAboutComponent: Error loading repository:', error);
            
            if (error.status === 404) {
              this.handleError('Repository not found');
            } else if (error.status === 403) {
              this.handleError('API rate limit exceeded. Please try again later.');
            } else if (error.status === 0) {
              this.handleError('Network error. Please check your connection.');
            } else {
              this.handleError('Failed to load repository data. Please try again.');
            }
            
            return of(null);
          })
        );
      })
    );
  }

  private handleError(message: string): void {
    this.error = true;
    this.errorMessage = message;
    this.loading = false;
    console.error('ProjectAboutComponent Error:', message);
  }

  // ===== NAVIGATION AND UI METHODS =====
  
  setActiveTab(tab: string): void {
    this.activeTab = tab;
  }

  retryLoad(): void {
    this.error = false;
    this.errorMessage = '';
    this.loading = true;
    this.loadRepositoryData();
  }

  goBack(): void {
    this.router.navigate(['/projects']);
  }

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

  // ===== PROJECT DATA EXTRACTION METHODS =====
  
  getProjectTitle(repo: Repository): string {
    if (!repo?.name) return 'Unknown Project';
    return ProjectConfigHelper.getProjectTitle(repo.repoContext, repo.name);
  }

  getProjectDescription(repo: Repository): string {
    if (!repo?.name) return 'No description available';
    return ProjectConfigHelper.getProjectDescription(repo.repoContext, repo.name);
  }

  getScreenshotUrl(repo: Repository): string | undefined {
    if (!repo?.name) return undefined;
    return ProjectConfigHelper.getScreenshotUrl(repo.repoContext, repo.name);
  }

  getProjectTags(repo: Repository): string[] {
    if (!repo?.name) return [];
    return ProjectConfigHelper.getProjectTags(repo.repoContext, repo.name);
  }

  getTechStack(repo: Repository): TechStack[] {
    if (!repo?.repoContext) return [];
    return ProjectConfigHelper.getTechStack(repo.repoContext);
  }

  getProjectMetrics(repo: Repository) {
    if (!repo?.repoContext) return {};
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext);
  }

  // ===== PROJECT IDENTITY METHODS =====
  
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

  // ===== TECHNOLOGY STACK METHODS =====
  
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

  // ===== SKILLS AND COMPETENCY METHODS =====
  
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

  // ===== ASSESSMENT METHODS =====
  
  getEstimatedHours(repo: Repository): number {
    return repo?.repoContext?.assessment?.estimated_hours || 0;
  }

  getComplexityFactors(repo: Repository): string[] {
    return repo?.repoContext?.assessment?.complexity_factors || [];
  }

  getEvaluationCriteria(repo: Repository): string[] {
    return repo?.repoContext?.assessment?.evaluation_criteria || [];
  }

  // ===== STRUCTURE AND COMPONENTS METHODS =====
  
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

  // ===== DIFFICULTY METHODS - USING SERVICE =====
  
  isDifficultyLoading(repoName: string): boolean {
    return this.difficultyService.isDifficultyLoading(repoName);
  }

  getDifficultyAnalysis(repoName: string): DifficultyAnalysis | null {
    return this.difficultyService.getCachedDifficulty(repoName);
  }

  getDifficultyScore(repoName: string): number {
    const analysis = this.getDifficultyAnalysis(repoName);
    return analysis?.score || 0;
  }

  getDifficultyRating(repo: Repository): string {
    const analysis = this.getDifficultyAnalysis(repo.name);
    return analysis?.difficulty || this.calculateFallbackDifficulty(repo);
  }

  getDifficultyTooltip(repoName: string): string {
    const analysis = this.getDifficultyAnalysis(repoName);
    if (!analysis) return 'Difficulty analysis not available';
    
    return `${analysis.difficulty} (${analysis.score}/100) - ${(analysis.confidence * 100).toFixed(0)}% confidence`;
  }

  // Fix: Single getDifficultyColor method that works with both signatures
  getDifficultyColor(input: string | Repository): string {
    let difficulty: string;
    
    if (typeof input === 'string') {
      // Called with repository name
      const analysis = this.getDifficultyAnalysis(input);
      difficulty = analysis?.difficulty || 'intermediate';
    } else {
      // Called with Repository object (legacy support)
      difficulty = this.getDifficultyRating(input);
    }
    
    return this.difficultyService.getDifficultyColor(difficulty);
  }

  private calculateFallbackDifficulty(repo: Repository): string {
    if (!repo?.repoContext) return 'intermediate';
    
    let score = 0;
    const techStack = repo.repoContext.tech_stack;
    
    if (techStack?.primary?.length > 0) score += techStack.primary.length * 2;
    if (techStack?.secondary?.length > 0) score += techStack.secondary.length;
    
    const components = repo.repoContext.components;
    if (components) score += Object.keys(components).length * 2;
    
    if (score >= 20) return 'advanced';
    if (score >= 10) return 'intermediate';
    return 'beginner';
  }

  // ===== UI HELPER METHODS =====
  
  getCompetencyColor(level: string): string {
    const colors: { [key: string]: string } = {
      'beginner': '#10b981',
      'intermediate': '#3b82f6', 
      'advanced': '#8b5cf6',
      'expert': '#ef4444'
    };
    return colors[level] || '#6b7280';
  }

  // ===== CONTENT VALIDATION METHODS =====
  
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

  // ===== UTILITY METHODS =====
  
  formatDuration(minutes: number): string {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  }

  formatFileCount(count: number): string {
    return count.toLocaleString();
  }
}
