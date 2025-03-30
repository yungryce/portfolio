import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, forkJoin, map, switchMap, catchError, of, tap } from 'rxjs';
import { FEATURED_PROJECTS, TechStack } from '../projects/projects-config';
import { ConfigService } from './config.service';

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
  // Optional properties for customization
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
  private apiUrl = 'https://api.github.com';
  private configService = inject(ConfigService);

  // List of featured repositories
  private featuredRepos: string[] = [
    'azure_vmss_cluster',
    'python_function_apps',
    'AirBnB_clone_v4',
    'collabHub',
    'simple_shell',
    'printf',
  ];

  constructor(private http: HttpClient) { }

  /**
   * Get repositories for the specified user
   */
  getRepositories(): Observable<Repository[]> {
    // Get the token and log it
    const token = this.configService.githubToken;
    
    // Build the headers
    const headers = new HttpHeaders({
      'Accept': 'application/vnd.github.v3',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    });
    

    return this.http.get<Repository[]>(
      `${this.apiUrl}/users/${this.username}/repos?sort=updated&per_page=10`,
      { headers }
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
      })
    );
  }

  /**
   * Get featured repositories from config
   */
  getFeaturedRepositories(): Observable<Repository[]> {
    // Log the token availability at the beginning of the method
    const token = this.configService.githubToken;
    
    // Get repository details for each featured repo
    const repoObservables = FEATURED_PROJECTS
      .filter(project => project.featured)
      .sort((a, b) => (a.order || 99) - (b.order || 99))
      .map(project => {
        return this.getRepository(project.repoName).pipe(
          // Add custom showcase information
          map(repo => {
            return {
              ...repo,
              featured: true,
              customTitle: project.customTitle,
              customDescription: project.customDescription || repo.description,
              screenshotUrl: project.screenshotUrl,
              customTags: project.tags,
              stack: project.stack // Include the stack information
            };
          }),
          catchError(error => {
            console.error(`Error fetching repo ${project.repoName}:`, error);
            console.log(`Error status code: ${error.status}`);
            console.log(`Error message: ${error.message}`);
            if (error.error && error.error.message) {
              console.log(`GitHub API error message: ${error.error.message}`);
            }
            // Check rate limit via headers if available
            if (error.headers) {
              const rateLimit = error.headers.get('x-ratelimit-limit');
              const rateRemaining = error.headers.get('x-ratelimit-remaining');
              const rateReset = error.headers.get('x-ratelimit-reset');
              
              if (rateLimit) {
                console.log(`Rate limit info - Limit: ${rateLimit}, Remaining: ${rateRemaining}, Reset: ${new Date(rateReset * 1000)}`);
              }
            }
            return of(null);
          })
        );
      });
    
    return forkJoin(repoObservables).pipe(
      map(repos => {
        const filteredRepos = repos.filter(Boolean) as Repository[];
        return filteredRepos;
      })
    );
  }

  /**
   * Get a specific repository by name
   */
  getRepository(repoName: string): Observable<Repository> {
    // Get the token and log it
    const token = this.configService.githubToken;
    
    // Build the headers
    const headers = new HttpHeaders({
      'Accept': 'application/vnd.github.v3',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    });
    
    
    return this.http.get<Repository>(`${this.apiUrl}/repos/${this.username}/${repoName}`, { headers })
      .pipe(
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
          console.log(`Status code: ${error.status}, Message: ${error.message}`);
          if (error.error && error.error.message) {
            console.log(`GitHub API error message: ${error.error.message}`);
          }
          throw error; // Re-throw so the outer catchError can handle it
        })
      );
  }

  /**
   * Get README content for a specific repository
   */
  getReadme(repoName: string): Observable<string> {
    // Get the token from the config service
    const token = this.configService.githubToken;
    
    // Debug log to check if token exists
    
    // Build the headers
    const headers = new HttpHeaders({
      'Accept': 'application/vnd.github.v3.raw',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    });

    // Debug log to check headers

    return this.http.get(
      `${this.apiUrl}/repos/${this.username}/${repoName}/readme`, 
      { headers, responseType: 'text' }
    ).pipe(
      catchError(error => {
        console.error(`Error fetching README for ${repoName}:`, error);
        console.log(`Status code: ${error.status}, Message: ${error.message}`);
        if (error.error && error.error.message) {
          console.log(`GitHub API error message: ${error.error.message}`);
        }
        return of('No README available');
      })
    );
  }
}