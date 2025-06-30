import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, map, switchMap, catchError, of, tap } from 'rxjs';
import { FEATURED_PROJECTS, TechStack } from '../projects/projects-config';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';
import { GithubFilesService } from './github-files.service';

export interface Repository {
  name: string;
  description: string;
  html_url: string;
  homepage: string;
  topics: string[];
  stargazers_count: number;
  language: string;
  fork: boolean;
  updated_at: string;
  size: number;

  // Dynamic file content (fetched when needed) - Fix null/undefined compatibility
  readme?: string;
  architecture?: string; // Changed from string | null to string | undefined
  skillsIndex?: string; // Changed from string | null to string | undefined
  repoContext?: any;
  projectManifests?: {[containerPath: string]: string};
  
  // Additional properties for enhanced functionality
  featured?: boolean;
  customTitle?: string; // Add this property
}

export interface RepositoryStatistics {
  totalRepositories: number;
  featuredRepositories: number;
  completedProjects: number;
  activeProjects: number;
  totalEstimatedHours: number;
  languageDistribution: { [key: string]: number };
  techStackDistribution: { [key: string]: number };
  complexityDistribution: { [key: string]: number };
}

@Injectable({
  providedIn: 'root'
})
export class GithubService {
  private readonly username = 'yungryce'; 
  
  constructor(
    private http: HttpClient,
    private cacheService: CacheService, // Add this injection
    private configService: ConfigService, // Add this injection
    private filesService: GithubFilesService // Make this public or add public methods
  ) {}

  /**
   * Get repository metadata only (no file content) - Fast operation
   */
  getRepositories(): Observable<Repository[]> {
    const cacheKey = 'repositories-metadata';
    const cached = this.cacheService.get<Repository[]>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.http.get<Repository[]>(
      `${this.configService.apiUrl}/github/repos`
    ).pipe(
      map(repos => repos.filter(repo => !repo.fork)),
      tap(repos => {
        this.cacheService.set(cacheKey, repos, 1000 * 60 * 15); // 15 minutes
        // Prefetch context files for top repos
        const topRepos = repos.slice(0, 5).map(r => r.name);
        this.filesService.prefetchCommonFiles(topRepos);
      }),
      catchError(error => {
        console.error('Error fetching repositories metadata:', error);
        return of([]); // Return empty array on error
      })
    );
  }

  /**
   * Get repositories with README content included
   */
  getRepositoriesWithReadme(): Observable<Repository[]> {
    const cacheKey = 'repositories-with-readme';
    const cached = this.cacheService.get<Repository[]>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.getRepositories().pipe(
      switchMap(repos => {
        const repoObservables = repos.map(repo => 
          this.filesService.getReadme(repo.name).pipe(
            map(readme => ({
              ...repo,
              readme
            })),
            catchError(error => {
              console.warn(`Failed to fetch README for ${repo.name}:`, error);
              return of(repo); // Return repo without README on error
            })
          )
        );
        return forkJoin(repoObservables);
      }),
      tap(repos => this.cacheService.set(cacheKey, repos, 1000 * 60 * 10)) // 10 minutes
    );
  }


  /**
   * Get single repository with metadata only
   */
  getRepository(repoName: string): Observable<Repository> {
    const cacheKey = `repository-${repoName}`;
    const cached = this.cacheService.get<Repository>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.http.get<Repository>(
      `${this.configService.apiUrl}/github/repos/${this.username}/${repoName}`
    ).pipe(
      tap(repo => this.cacheService.set(cacheKey, repo, 1000 * 60 * 30)),
      catchError(error => {
        console.error(`Error fetching repository ${repoName}:`, error);
        throw error;
      })
    );
  }

  /**
   * Get repository with README content
   */
  getRepositoryWithReadme(repoName: string): Observable<Repository> {
    const cacheKey = `repository-with-readme-${repoName}`;
    const cached = this.cacheService.get<Repository>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.getRepository(repoName).pipe(
      switchMap(repo => 
        this.filesService.getReadme(repo.name).pipe(
          map(readme => ({
            ...repo,
            readme
          }))
        )
      ),
      tap(repo => this.cacheService.set(cacheKey, repo, 1000 * 60 * 20))
    );
  }

  /**
   * Type-safe batch file fetcher that returns properly typed Repository content
   */
  private batchFetchRepositoryFiles(repoName: string): Observable<{
    readme?: string;
    architecture?: string;
    skillsIndex?: string;
    repoContext?: any;
  }> {
    const fileRequests = [
      { repoName, fileType: 'readme' as const },
      { repoName, fileType: 'context' as const },
      { repoName, fileType: 'architecture' as const },
      { repoName, fileType: 'skills' as const }
    ];

    return this.filesService.batchFetchFiles(fileRequests).pipe(
      map((files: Record<string, string | { error: string }>) => {
        const result: {
          readme?: string;
          architecture?: string;
          skillsIndex?: string;
          repoContext?: any;
        } = {};

        // Handle README
        const readmeContent = files[`${repoName}-readme-root`];
        if (typeof readmeContent === 'string') {
          result.readme = readmeContent;
        }

        // Handle ARCHITECTURE
        const archContent = files[`${repoName}-architecture-root`];
        if (typeof archContent === 'string') {
          result.architecture = archContent;
        }

        // Handle SKILLS-INDEX
        const skillsContent = files[`${repoName}-skills-root`];
        if (typeof skillsContent === 'string') {
          result.skillsIndex = skillsContent;
        }

        // Handle repo context (JSON)
        const contextContent = files[`${repoName}-context-root`];
        if (typeof contextContent === 'string') {
          try {
            result.repoContext = JSON.parse(contextContent);
          } catch (error) {
            console.warn(`Failed to parse repo context JSON for ${repoName}:`, error);
          }
        }

        return result;
      })
    );
  }

  /**
   * Get repository with complete documentation (README, ARCHITECTURE, SKILLS-INDEX, .repo-context.json)
   */
  getRepositoryWithAllDocs(repoName: string): Observable<Repository> {
    const cacheKey = `repository-full-docs-${repoName}`;
    const cached = this.cacheService.get<Repository>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.getRepository(repoName).pipe(
      switchMap(repo => 
        this.batchFetchRepositoryFiles(repoName).pipe(
          map(files => ({
            ...repo,
            ...files
          }))
        )
      ),
      tap(repo => this.cacheService.set(cacheKey, repo, 1000 * 60 * 30))
    );
  }

  /**
   * Search repositories by criteria with context-based filtering
   */
  searchRepositories(criteria: {
    status?: string;
    complexity?: string;
    techStack?: string;
    featured?: boolean;
    language?: string;
  }): Observable<Repository[]> {
    const cacheKey = `search-repositories-${JSON.stringify(criteria)}`;
    const cached = this.cacheService.get<Repository[]>(cacheKey);

    if (cached) {
      return of(cached);
    }

    return this.getRepositories().pipe(
      switchMap(repos => {
        // Filter by basic criteria first
        let filteredRepos = repos;
        
        if (criteria.language) {
          filteredRepos = filteredRepos.filter(repo => 
            repo.language?.toLowerCase() === criteria.language!.toLowerCase()
          );
        }

        // Get contexts for advanced filtering
        const contextRequests = filteredRepos.map(repo => 
          this.filesService.getRepoContext(repo.name).pipe(
            map(context => ({ repo, context }))
          )
        );

        return forkJoin(contextRequests);
      }),
      map(repoContextPairs => {
        return repoContextPairs
          .filter(pair => {
            const context = pair.context;
            if (!context) return true; // Include repos without context if no advanced criteria

            if (criteria.status && context.project_status !== criteria.status) return false;
            if (criteria.complexity && context.complexity_level !== criteria.complexity) return false;
            if (criteria.featured !== undefined && context.featured !== criteria.featured) return false;
            if (criteria.techStack && !context.tech_stack?.some((tech: string) => 
              tech.toLowerCase().includes(criteria.techStack!.toLowerCase())
            )) return false;

            return true;
          })
          .map(pair => ({
            ...pair.repo,
            repoContext: pair.context
          }));
      }),
      tap(repos => this.cacheService.set(cacheKey, repos, 1000 * 60 * 5)) // 5 minutes for search results
    );
  }


  /**
   * Public method to get repository context
   */
  getRepoContext(repoName: string): Observable<any> {
    return this.filesService.getRepoContext(repoName);
  }

  /**
   * Get multiple repositories with contexts in a single optimized call
   */
  getFeaturedRepositoriesWithContext(repoNames: string[]): Observable<Repository[]> {
    const cacheKey = `featured-repos-with-context-${repoNames.join(',')}`;
    const cached = this.cacheService.get<Repository[]>(cacheKey);

    if (cached) {
      return of(cached);
    }

    // Create requests for both repository metadata and context files
    const requests = repoNames.map(repoName => 
      this.getRepository(repoName).pipe(
        switchMap(repo => 
          this.getRepoContext(repo.name).pipe(
            map(context => ({
              ...repo,
              repoContext: context,
              featured: true
            })),
            catchError(error => {
              console.warn(`Failed to get context for ${repoName}:`, error);
              return of({ ...repo, featured: true });
            })
          )
        ),
        catchError(error => {
          console.warn(`Failed to get repository ${repoName}:`, error);
          return of(null);
        })
      )
    );

    return forkJoin(requests).pipe(
      map(repos => repos.filter(repo => repo !== null) as Repository[]),
      tap(repos => this.cacheService.set(cacheKey, repos, 1000 * 60 * 30)),
      catchError(error => {
        console.error('Error fetching featured repositories with context:', error);
        return of([]);
      })
    );
  }

  // /**
  //  * Fallback method for individual repository fetching
  //  */
  // private getFeaturedRepositoriesFallback(repoNames: string[]): Observable<Repository[]> {
  //   const repoRequests = repoNames.map(repoName =>
  //     this.getRepository(repoName).pipe(
  //       switchMap(repo => 
  //         this.filesService.getRepoContext(repo.name).pipe(
  //           map(context => ({
  //             ...repo,
  //             repoContext: context,
  //             featured: true
  //           })),
  //           catchError(() => of({ ...repo, featured: true }))
  //         )
  //       )
  //     )
  //   );

  //   return forkJoin(repoRequests);
  // }

  // /**
  //  * Get repository statistics from contexts
  //  */
  // getRepositoryStatistics(): Observable<RepositoryStatistics> {
  //   const cacheKey = 'repository-statistics';
  //   const cached = this.cacheService.get<RepositoryStatistics>(cacheKey);

  //   if (cached) {
  //     return of(cached);
  //   }

  //   return this.getRepositories().pipe(
  //     switchMap(repos => {
  //       const contextRequests = repos.map(repo => 
  //         this.filesService.getRepoContext(repo.name).pipe(
  //           map(context => ({ repo, context })),
  //           catchError(error => {
  //             console.warn(`Failed to get context for ${repo.name}:`, error);
  //             return of({ repo, context: null });
  //           })
  //         )
  //       );

  //       return forkJoin(contextRequests);
  //     }),
  //     map(repoContextPairs => {
  //       const languageDistribution: { [key: string]: number } = {};
  //       const techStackDistribution: { [key: string]: number } = {};
  //       const complexityDistribution: { [key: string]: number } = {};
        
  //       let featuredCount = 0;
  //       let completedCount = 0;
  //       let activeCount = 0;
  //       let totalHours = 0;

  //       repoContextPairs.forEach(({ repo, context }) => {
  //         // Language distribution
  //         if (repo.language) {
  //           languageDistribution[repo.language] = (languageDistribution[repo.language] || 0) + 1;
  //         }

  //         if (context) {
  //           // Featured count
  //           if (context.featured) featuredCount++;

  //           // Status counts
  //           if (context.project_status === 'completed') completedCount++;
  //           if (context.project_status === 'active') activeCount++;

  //           // Hours
  //           totalHours += context.estimated_hours || 0;

  //           // Tech stack distribution
  //           if (context.tech_stack) {
  //             context.tech_stack.forEach((tech: string) => {
  //               techStackDistribution[tech] = (techStackDistribution[tech] || 0) + 1;
  //             });
  //           }

  //           // Complexity distribution
  //           if (context.complexity_level) {
  //             complexityDistribution[context.complexity_level] = 
  //               (complexityDistribution[context.complexity_level] || 0) + 1;
  //           }
  //         }
  //       });

  //       const stats: RepositoryStatistics = {
  //         totalRepositories: repoContextPairs.length,
  //         featuredRepositories: featuredCount,
  //         completedProjects: completedCount,
  //         activeProjects: activeCount,
  //         totalEstimatedHours: totalHours,
  //         languageDistribution,
  //         techStackDistribution,
  //         complexityDistribution
  //       };

  //       return stats;
  //     }),
  //     tap(stats => this.cacheService.set(cacheKey, stats, 1000 * 60 * 60)), // Cache for 1 hour
  //     catchError(error => {
  //       console.error('Error fetching repository statistics:', error);
  //       // Return default statistics object on error
  //       return of({
  //         totalRepositories: 0,
  //         featuredRepositories: 0,
  //         completedProjects: 0,
  //         activeProjects: 0,
  //         totalEstimatedHours: 0,
  //         languageDistribution: {},
  //         techStackDistribution: {},
  //         complexityDistribution: {}
  //       } as RepositoryStatistics);
  //     })
  //   );
  // }


}



