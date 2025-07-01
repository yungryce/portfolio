import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';
import { GithubService, Repository } from '../services/github.service';
import { CacheService } from '../services/cache.service';
import { FEATURED_REPOSITORIES, ProjectConfigHelper, TechStack } from './projects-config';

@Component({
  selector: 'app-projects',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './projects.component.html',
  styleUrls: ['./projects.component.css']
})
export class ProjectsComponent implements OnInit {
  repositories: Repository[] = [];
  loading = true;
  error = false;
  errorType: 'network' | 'parsing' | 'general' | null = null;
  
  // Use simplified repository list
  private readonly featuredRepoNames = FEATURED_REPOSITORIES;
  
  constructor(
    private githubService: GithubService,
    private cacheService: CacheService
  ) {}
  
  ngOnInit(): void {
    console.debug('Initializing ProjectsComponent, loading featured repositories...');
    this.loadFeaturedRepositories();
    console.debug('Featured repositories loaded:', this.featuredRepoNames);
  }

  private loadFeaturedRepositories(): void {
    this.loading = true;
    
    // First, try to get cached repository data and files
    const cachedRepos = this.getCachedFeaturedRepositories();
    console.debug('Cached repositories:', cachedRepos);
    
    if (cachedRepos.length > 0) {
      // We have some cached data, show it immediately
      this.repositories = this.sortRepositories(cachedRepos);
      this.loading = false;
      
      // Optionally, still fetch fresh data in background for updates
      this.refreshRepositoriesInBackground();
    } else {
      // No cached data, fetch everything fresh
      this.fetchFreshRepositories();
    }
  }

  private getCachedFeaturedRepositories(): Repository[] {
    const cachedRepos: Repository[] = [];
    
    // Check if we have cached repository metadata and files
    for (const repoName of this.featuredRepoNames) {
      const repoMetadata = this.getCachedRepoMetadata(repoName);
      const cachedFiles = this.getCachedRepoFiles(repoName);
      
      if (repoMetadata && cachedFiles.readme && cachedFiles.context) {
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
    const readmeCacheKey = `${repoName}-readme-content`;
    const contextCacheKey = `${repoName}-context-content`;
    
    return {
      readme: this.getSafeCache<string>(readmeCacheKey),
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

  private sortRepositories(repos: Repository[]): Repository[] {
    return repos.sort((a, b) => {
      // Sort by array order (index in FEATURED_REPOSITORIES)
      const aIndex = this.featuredRepoNames.indexOf(a.name);
      const bIndex = this.featuredRepoNames.indexOf(b.name);
      
      if (aIndex !== -1 && bIndex !== -1) {
        return aIndex - bIndex;
      }
      
      // Fallback to difficulty rating if not in featured list
      const aDifficulty = this.getDifficultyRating(a);
      const bDifficulty = this.getDifficultyRating(b);
      return bDifficulty - aDifficulty;
    });
  }

  private refreshRepositoriesInBackground(): void {
    // Silently refresh data in background without showing loading state
    this.githubService.getFeaturedRepositoriesWithContext(this.featuredRepoNames)
      .subscribe({
        next: (reposWithContext) => {
          // Update repositories if we got fresh data
          const freshRepos = this.sortRepositories(reposWithContext);
          
          // Only update if the data has actually changed
          if (this.hasRepositoryDataChanged(this.repositories, freshRepos)) {
            this.repositories = freshRepos;
            console.log('Repository data updated with fresh information');
          }
        },
        error: (err) => {
          console.warn('Background refresh failed, using cached data:', err);
          // Don't show error since we already have cached data displayed
        }
      });
  }

  private fetchFreshRepositories(): void {
    // Original fetch logic when no cache is available
    this.githubService.getFeaturedRepositoriesWithContext(this.featuredRepoNames)
      .subscribe({
        next: (reposWithContext) => {
          this.repositories = this.sortRepositories(reposWithContext);
          this.loading = false;
          this.errorType = null;
        },
        error: (err) => {
          console.error('Error fetching repository contexts:', err);
          this.error = true;
          this.errorType = err.status === 0 ? 'network' : 'general';
          this.loading = false;
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

  // Helper methods for template
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

  getDifficultyRating(repo: Repository): number {
    const metrics = ProjectConfigHelper.getProjectMetrics(repo.repoContext);
    // Convert difficulty string to number for sorting
    const difficultyMap: { [key: string]: number } = {
      'beginner': 2,
      'intermediate': 5,
      'advanced': 8,
      'expert': 10
    };
    return difficultyMap[metrics.difficulty] || 5;
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
}
