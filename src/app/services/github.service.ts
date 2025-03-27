import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, forkJoin, map, switchMap, catchError, of } from 'rxjs';
import { FEATURED_PROJECTS } from '../projects/projects-config';

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
}

@Injectable({
  providedIn: 'root'
})
export class GithubService {
  private username = 'yungryce'; // Replace with your GitHub username
  private apiUrl = 'https://api.github.com';

  // List of featured repositories
  private featuredRepos: string[] = [
    'k8s pipeline',
    'Azure Function Apps',
    'AirBnB Clone'
  ];

  constructor(private http: HttpClient) { }

  /**
   * Get repositories for the specified user
   */
  getRepositories(): Observable<Repository[]> {
    return this.http.get<Repository[]>(`${this.apiUrl}/users/${this.username}/repos?sort=updated&per_page=10`)
      .pipe(
        // Filter out forked repositories if needed
        map(repos => repos.filter(repo => !repo.fork)),
        // Get README content for each repository
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
    // Get repository details for each featured repo
    const repoObservables = FEATURED_PROJECTS
      .filter(project => project.featured)
      .sort((a, b) => (a.order || 99) - (b.order || 99))
      .map(project => 
        this.getRepository(project.repoName).pipe(
          // Add custom showcase information
          map(repo => ({
            ...repo,
            featured: true,
            customTitle: project.customTitle,
            customDescription: project.customDescription || repo.description,
            screenshotUrl: project.screenshotUrl,
            customTags: project.tags
          })),
          catchError(error => {
            console.error(`Error fetching repo ${project.repoName}:`, error);
            return of(null);
          })
        )
      );
    
    return forkJoin(repoObservables).pipe(
      map(repos => repos.filter(Boolean) as Repository[])
    );
  }

  /**
   * Get a specific repository by name
   */
  getRepository(repoName: string): Observable<Repository> {
    return this.http.get<Repository>(`${this.apiUrl}/repos/${this.username}/${repoName}`)
      .pipe(
        switchMap(repo => 
          this.getReadme(repo.name).pipe(
            map(readme => ({
              ...repo,
              readme
            }))
          )
        )
      );
  }

  /**
   * Get README content for a specific repository
   */
  getReadme(repoName: string): Observable<string> {
    return this.http.get(
      `${this.apiUrl}/repos/${this.username}/${repoName}/readme`, 
      { headers: { Accept: 'application/vnd.github.v3.raw' } }
    ).pipe(
      map(response => response as string),
      catchError(error => {
        console.log(`No README found for ${repoName}`);
        return of('No README available');
      })
    );
  }
}