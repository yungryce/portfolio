import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';
import { Subject, takeUntil } from 'rxjs';
import { GithubService, Repository } from '../services/github.service';
import { CacheService } from '../services/cache.service';
import { DifficultyService, DifficultyAnalysis, DifficultyState } from '../services/difficulty.service';
import { FEATURED_REPOSITORIES, ProjectConfigHelper, TechStack } from './projects-config';

@Component({
  selector: 'app-projects',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './projects.component.html',
  styleUrls: ['./projects.component.css']
})
export class ProjectsComponent implements OnInit, OnDestroy {
  repositories: Repository[] = [];
  loading = true;
  error = false;
  errorType: 'network' | 'parsing' | 'general' | null = null;
  
  // Difficulty state
  difficultyState: DifficultyState = {};
  difficultyLoading: { [repoName: string]: boolean } = {};
  
  // Use simplified repository list
  private readonly featuredRepoNames = FEATURED_REPOSITORIES;
  private destroy$ = new Subject<void>();
  
  constructor(
    private githubService: GithubService,
    private cacheService: CacheService,
    private difficultyService: DifficultyService
  ) {}
  
  ngOnInit(): void {
    this.setupDifficultyStateSubscription();
    this.loadFeaturedRepositories();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private setupDifficultyStateSubscription(): void {
    // Subscribe to difficulty state changes
    this.difficultyService.difficultyState$
      .pipe(takeUntil(this.destroy$))
      .subscribe(state => {
        this.difficultyState = state;
        
        // Update loading states
        this.difficultyLoading = {};
        Object.keys(state).forEach(repoName => {
          this.difficultyLoading[repoName] = state[repoName]?.loading || false;
        });
      });
  }

  private loadFeaturedRepositories(): void {
    this.loading = true;
    
    // First, try to get cached repository data and files
    const cachedRepos = this.getCachedFeaturedRepositories();
    
    if (cachedRepos.length > 0) {
      // We have some cached data, show it immediately
      this.repositories = this.sortRepositories(cachedRepos);
      this.loading = false;
      
      // Start fetching difficulties in background
      this.startBackgroundDifficultyFetch(cachedRepos.map(r => r.name));
      
      // Optionally, still fetch fresh data in background for updates
      this.refreshRepositoriesInBackground();
    } else {
      // No cached data, fetch everything fresh
      this.fetchFreshRepositories();
    }
  }

  private startBackgroundDifficultyFetch(repoNames: string[]): void {
    console.log('Starting background difficulty fetch for', repoNames.length, 'repositories');
    
    // Use the batch fetch method for better performance
    this.difficultyService.batchFetchDifficulties(repoNames)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (results) => {
          console.log('Received difficulty batch results:', Object.keys(results).length);
          // Results are automatically updated via the state subscription
        },
        error: (error) => {
          console.error('Batch difficulty fetch failed:', error);
        }
      });
  }

  private sortRepositories(repos: Repository[]): Repository[] {
    return repos.sort((a, b) => {
      // Sort by array order (index in FEATURED_REPOSITORIES)
      const aIndex = this.featuredRepoNames.indexOf(a.name);
      const bIndex = this.featuredRepoNames.indexOf(b.name);
      
      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex;
      }
      
      // Fallback to difficulty rating if not in featured list
      const aDifficulty = this.getDifficultyNumericScore(a.name);
      const bDifficulty = this.getDifficultyNumericScore(b.name);
      return bDifficulty - aDifficulty;
    });
  }

  private fetchFreshRepositories(): void {
    this.githubService.getFeaturedRepositoriesWithContext(this.featuredRepoNames)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (reposWithContext) => {
          this.repositories = this.sortRepositories(reposWithContext);
          this.loading = false;
          this.errorType = null;
          
          // Start fetching difficulties in background
          this.startBackgroundDifficultyFetch(reposWithContext.map(r => r.name));
        },
        error: (err) => {
          console.error('Error fetching repository contexts:', err);
          this.error = true;
          this.errorType = err.status === 0 ? 'network' : 'general';
          this.loading = false;
        }
      });
  }

  private refreshRepositoriesInBackground(): void {
    // Silently refresh data in background without showing loading state
    this.githubService.getFeaturedRepositoriesWithContext(this.featuredRepoNames)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (reposWithContext) => {
          // Update repositories if we got fresh data
          const freshRepos = this.sortRepositories(reposWithContext);
          
          // Only update if the data has actually changed
          if (this.hasRepositoryDataChanged(this.repositories, freshRepos)) {
            this.repositories = freshRepos;
            console.log('Repository data updated with fresh information');
            
            // Fetch difficulties for any new repositories
            const newRepoNames = freshRepos.map(r => r.name);
            this.startBackgroundDifficultyFetch(newRepoNames);
          }
        },
        error: (err) => {
          console.warn('Background refresh failed, using cached data:', err);
          // Don't show error since we already have cached data displayed
        }
      });
  }

  private hasRepositoryDataChanged(current: Repository[], fresh: Repository[]): boolean {
    if (current.length !== fresh.length) return true;
    
    // Simple check - compare repository names and last updated dates
    for (let i = 0; i < current.length; i++) {
      if (current[i].name !== fresh[i].name || 
          current[i].updated_at !== fresh[i].updated_at) {
        return true;
      }
    }
    
    return false;
  }

  private getCachedFeaturedRepositories(): Repository[] {
    const cachedRepos: Repository[] = [];
    
    // Check if we have cached repository metadata and files
    for (const repoName of this.featuredRepoNames) {
      const repoMetadata = this.getCachedRepoMetadata(repoName);
      const cachedFiles = this.getCachedRepoFiles(repoName);
      
      if (repoMetadata && cachedFiles.context) {
        // We have both metadata and essential files cached
        const repoWithContext: Repository = {
          ...repoMetadata,
          repoContext: cachedFiles.context
        };
        cachedRepos.push(repoWithContext);
      }
    }
    
    return cachedRepos;
  }

  private getCachedRepoMetadata(repoName: string): any {
    // Check if repository metadata is cached (from GithubService)
    const cacheKey = `repo-metadata-${repoName}`;
    return this.getSafeCache(cacheKey);
  }

  private getSafeCache<T>(key: string): T | undefined {
    const cached = this.cacheService.get<T>(key);
    return cached ?? undefined; // Convert null to undefined for TypeScript compatibility
  }

  private getCachedRepoFiles(repoName: string): { readme?: string, context?: any } {
    // Use the SAME cache keys as GithubFilesService now uses
    const contextCacheKey = `${repoName}-context-content`;
    
    return {
      context: this.getCachedContextAsObject(contextCacheKey)
    };
  }

  private getCachedContextAsObject(cacheKey: string): any {
    const cachedContext = this.cacheService.get<string>(cacheKey);
    if (!cachedContext) return null;
    
    try {
      return JSON.parse(cachedContext);
    } catch (error) {
      console.warn('Failed to parse cached context:', error);
      return null;
    }
  }

  // ===== DIFFICULTY RELATED METHODS =====

  getDifficultyRating(repo: Repository): string {
    // First try to get from the difficulty service (synchronously)
    const cachedDifficulty = this.getDifficultyRatingSync(repo.name);
    if (cachedDifficulty !== 'intermediate' || this.isDifficultyLoaded(repo.name)) {
      return cachedDifficulty;
    }
    
    // Fallback to local calculation while API data loads
    return this.calculateLocalDifficultyRating(repo);
  }

  getDifficultyRatingSync(repoName: string): string {
    const analysis = this.getDifficultyAnalysis(repoName);
    return analysis?.difficulty || 'intermediate';
  }

  isDifficultyLoaded(repoName: string): boolean {
    const state = this.difficultyState[repoName];
    return !!(state?.analysis && !state.loading && !state.error);
  }

  getDifficultyColor(repoName: string): string {
    const difficulty = this.getDifficultyRatingFromState(repoName);
    return this.difficultyService.getDifficultyColor(difficulty);
  }

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

  getDifficultyNumericScore(repoName: string): number {
    const analysis = this.getDifficultyAnalysis(repoName);
    if (analysis?.difficulty) {
      return this.difficultyService.getDifficultyNumericScore(analysis.difficulty);
    }
    return 2; // Default intermediate
  }

  getDifficultyTooltip(repoName: string): string {
    const analysis = this.getDifficultyAnalysis(repoName);
    if (!analysis) {
      return this.isDifficultyLoading(repoName) 
        ? 'Difficulty analysis loading...' 
        : 'Difficulty analysis not available';
    }
    
    return `${analysis.difficulty} (${analysis.score}/100) - ${(analysis.confidence * 100).toFixed(0)}% confidence`;
  }

  // Helper method to get difficulty from state
  private getDifficultyRatingFromState(repoName: string): string {
    const analysis = this.difficultyState[repoName]?.analysis;
    return analysis?.difficulty || this.calculateLocalDifficultyRating(
      this.repositories.find(r => r.name === repoName) || {} as Repository
    );
  }

  // Local difficulty calculation fallback
  private calculateLocalDifficultyRating(repo: Repository): string {
    // Use the enhanced context to determine difficulty (fallback method)
    if (!repo?.repoContext) {
      return 'beginner'; // Default for repos without context
    }
    
    let score = 0;
    
    // Technology stack complexity
    const techStack = repo.repoContext.tech_stack;
    if (techStack?.primary?.length > 0) {
      score += techStack.primary.length * 2;
    }
    if (techStack?.secondary?.length > 0) {
      score += techStack.secondary.length;
    }
    
    // Architecture complexity
    const components = repo.repoContext.components;
    if (components) {
      score += Object.keys(components).length * 3;
    }
    
    // Skill requirements
    const skills = repo.repoContext.skill_manifest;
    if (skills?.technical?.length > 0) {
      score += skills.technical.length;
    }
    if (skills?.domain?.length > 0) {
      score += skills.domain.length;
    }
    
    // Project scope
    const projectType = repo.repoContext.project_identity?.type?.toLowerCase();
    if (projectType?.includes('full-stack') || projectType?.includes('enterprise')) {
      score += 10;
    }
    
    // Determine difficulty based on score
    if (score >= 30) return 'expert';
    if (score >= 20) return 'advanced';
    if (score >= 10) return 'intermediate';
    return 'beginner';
  }

  // ===== TEMPLATE HELPER METHODS =====

  getPrimaryTechStack(repo: Repository): string[] {
    return repo.repoContext?.tech_stack?.primary || [repo.language].filter(Boolean);
  }

  getSecondaryTechStack(repo: Repository): string[] {
    return repo.repoContext?.tech_stack?.secondary || [];
  }

  hasSecondaryTechStack(repo: Repository): boolean {
    return this.getSecondaryTechStack(repo).length > 0;
  }

  getProjectTitle(repo: Repository): string {
    return ProjectConfigHelper.getProjectTitle(repo.repoContext, repo.name);
  }

  getProjectDescription(repo: Repository): string {
    return ProjectConfigHelper.getProjectDescription(repo.repoContext, repo.name);
  }

  getScreenshotUrl(repo: Repository): string | undefined {
    return ProjectConfigHelper.getScreenshotUrl(repo.repoContext, repo.name);
  }

  getProjectTags(repo: Repository): string[] {
    return ProjectConfigHelper.getProjectTags(repo.repoContext, repo.name);
  }

  getTechStack(repo: Repository): TechStack[] {
    return ProjectConfigHelper.getTechStack(repo.repoContext);
  }

  getEstimatedHours(repo: Repository): number {
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext).estimatedHours;
  }

  getCompetencyLevel(repo: Repository): string {
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext).competencyLevel;
  }

  getProjectType(repo: Repository): string {
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext).projectType;
  }

  getProjectScope(repo: Repository): string {
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext).projectScope;
  }

  getProjectVersion(repo: Repository): string {
    return ProjectConfigHelper.getProjectMetrics(repo.repoContext).version;
  }

  // ===== SUMMARY STATISTICS =====

  getTotalDevelopmentHours(): number {
    return this.repositories.reduce((sum, repo) => sum + this.getEstimatedHours(repo), 0);
  }

  getTotalStars(): number {
    return this.repositories.reduce((sum, repo) => sum + repo.stargazers_count, 0);
  }

  getCompletedProjects(): number {
    return this.repositories.filter(repo => 
      repo.repoContext?.project_status === 'completed'
    ).length;
  }

  getActiveProjects(): number {
    return this.repositories.filter(repo => 
      repo.repoContext?.project_status === 'active'
    ).length;
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
}
