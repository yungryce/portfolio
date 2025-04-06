import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, map, switchMap, catchError, of, tap } from 'rxjs';
import { FEATURED_PROJECTS, TechStack } from '../projects/projects-config';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';

export interface Repository {
  name: string;
  description: string;
  html_url: string;
  homepage: string;
  topics: string[];
  stargazers_count: number;
  language: string;
  readme?: string;
  fork: boolean; // Add this missing property
  featured?: boolean;
  customTitle?: string;
  customDescription?: string;
  screenshotUrl?: string;
  customTags?: string[];
  stack?: TechStack[];
}

@Injectable({
  providedIn: 'root'
})
export class GithubService {
  private username = 'yungryce'; // Replace with your GitHub username
  private configService = inject(ConfigService);
  private cacheService = inject(CacheService);
  
  constructor(private http: HttpClient) {}


  /**
   * Get repositories through Azure Function proxy
   */
  getRepositories(): Observable<Repository[]> {
    const cacheKey = 'all-repositories';
    const cachedRepos = this.cacheService.get<Repository[]>(cacheKey);

    if (cachedRepos) {
      return of(cachedRepos);
    }

    return this.http.get<Repository[]>(
      `${this.configService.apiUrl}/github/repos`
    ).pipe(
      map(repos => repos.filter(repo => !repo.fork)),
      switchMap(repos => {
        const repoObservables = repos.map(repo => 
          this.getReadme(repo.name).pipe(
            map(readme => ({
              ...repo,
              readme
            }))
          )
        );
        return forkJoin(repoObservables);
      }),
      tap(repos => this.cacheService.set(cacheKey, repos))
    );
  }

  /**
   * Get featured repositories from config
   */
  getFeaturedRepositories(): Observable<Repository[]> {
    // Get repository details for each featured repo
    const repoObservables = FEATURED_PROJECTS
      .filter(project => project.featured)
      .sort((a, b) => (a.order || 99) - (b.order || 99))
      .map(project => {
        return this.getRepository(project.repoName).pipe(
          map(repo => ({
            ...repo,
            featured: true,
            customTitle: project.customTitle,
            customDescription: project.customDescription || repo.description,
            screenshotUrl: project.screenshotUrl,
            customTags: project.tags,
            stack: project.stack
          })),
          catchError(error => {
            console.error(`Error fetching repo ${project.repoName}:`, error);
            return of(null);
          })
        );
      });
    
    return forkJoin(repoObservables).pipe(
      map(repos => repos.filter(Boolean) as Repository[])
    );
  }

  /**
   * Get a specific repository by name
   */
  getRepository(repoName: string): Observable<Repository> {
    return this.http.get<Repository>(
      `${this.configService.apiUrl}/github/repos/${this.username}/${repoName}`
    ).pipe(
      switchMap(repo => 
        this.getReadme(repo.name).pipe(
          map(readme => ({
            ...repo,
            readme
          }))
        )
      ),
      catchError(error => {
        console.error(`Error in getRepository for ${repoName}:`, error);
        throw error;
      })
    );
  }

  /**
   * Get README content for a specific repository
   */
  getReadme(repoName: string): Observable<string> {
    return this.http.get(
      `${this.configService.apiUrl}/github/repos/${this.username}/${repoName}/readme`, 
      { responseType: 'text' }
    ).pipe(
      catchError(error => {
        console.error(`Error fetching README for ${repoName}:`, error);
        return of('No README available');
      })
    );
  }
}