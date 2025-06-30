import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, tap, catchError, forkJoin, map } from 'rxjs';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';

export interface FileMetadata {
  repoName: string;
  fileName: string;
  content: string;
  lastFetched: Date;
  size: number;
}

@Injectable({
  providedIn: 'root'
})
export class GithubFilesService {
  private username = 'yungryce';
  private configService = inject(ConfigService);
  private cacheService = inject(CacheService);
  
  constructor(private http: HttpClient) {}


  /**
   * Generic method to get any file content with safe error handling
   */
  private getFileContent(repoName: string, filePath: string, cacheKey: string): Observable<string> {
    const cached = this.cacheService.get<string>(cacheKey);
    console.debug(`++++Checking cache for cachekey ${cacheKey}...`);
    
    if (cached) {
      console.debug(`Cache hit for ${cacheKey}`);
      return of(cached);
    }
    console.debug(`****Cache miss for ${cacheKey} - fetching from API`);
    return this.http.get(
      `${this.configService.apiUrl}/github/repos/${this.username}/${repoName}/contents/${filePath}`,
      { responseType: 'text' }
    ).pipe(
      tap(content => this.cacheService.set(cacheKey, content, 1000 * 60 * 60)),
      catchError(error => {
        console.warn(`File ${filePath} not found for ${repoName}:`, error);
        // Return a safe default instead of throwing
        const fileType = filePath.split('.').pop()?.toLowerCase();
        const defaultMessage = fileType === 'json' ? '{}' : `# ${filePath} not available\n\nThis file was not found in the repository.`;
        return of(defaultMessage);
      })
    );
  }


  /**
   * Get README.md content
   */
  getReadme(repoName: string): Observable<string> {
    return this.getFileContent(repoName, 'README.md', `readme-${repoName}`);
    // return this.getFileContent(repoName, 'README.md', `${repoName}-readme-content`);
  }

  /**
   * Get ARCHITECTURE.md content
   */
  getArchitecture(repoName: string): Observable<string> {
    return this.getFileContent(repoName, 'ARCHITECTURE.md', `architecture-${repoName}`);
  }

  /**
   * Get SKILLS-INDEX.md content
   */
  getSkillsIndex(repoName: string): Observable<string> {
    return this.getFileContent(repoName, 'SKILLS-INDEX.md', `skills-index-${repoName}`);
  }

  /**
   * Get project manifest file content (only exists at sub-repo/container level)
   */
  getProjectManifest(repoName: string, containerPath: string): Observable<string> {
    if (!containerPath) {
      // PROJECT-MANIFEST.md doesn't exist at root level
      return of('No project manifest available - only exists at container level');
    }
    
    const path = `${containerPath}/PROJECT-MANIFEST.md`;
    const cacheKey = `project-manifest-${repoName}-${containerPath}`;
    
    return this.getFileContent(repoName, path, cacheKey);
  }


  /**
   * Get .repo-context.json content
   */
  getRepoContext(repoName: string, containerPath?: string): Observable<any> {
    const path = containerPath ? `${containerPath}/.repo-context.json` : '.repo-context.json';
    const cacheKey = `repo-context-${repoName}-${containerPath || 'root'}`;
    
    return this.getFileContent(repoName, path, cacheKey).pipe(
      map(content => {
        try {
          // Parse JSON content
          return JSON.parse(content);
        } catch (error) {
          console.warn(`Invalid JSON in .repo-context.json for ${repoName} at ${path}:`, error);
          return null;
        }
      }),
      catchError(error => {
        console.warn(`Repo context not found for ${repoName} at ${path}:`, error);
        return of(null);
      })
    );
  }


  /**
   * Safe batch fetch with validation and proper error handling
   */
  batchFetchFiles(requests: Array<{
    repoName: string, 
    fileType: 'readme' | 'architecture' | 'skills' | 'manifest' | 'context', 
    containerPath?: string
  }>): Observable<{[key: string]: string | { error: string }}> {
    const validatedRequests = requests.map(req => ({
      ...req,
      validation: this.validateFileRequest(req.fileType, req.containerPath)
    }));

    const observables = validatedRequests.map(req => {
      const key = `${req.repoName}-${req.fileType}-${req.containerPath || 'root'}`;
      
      if (!req.validation.valid) {
        return of({[key]: { error: req.validation.message || 'Invalid request' }});
      }
      
      switch (req.fileType) {
        case 'readme': 
          return this.getReadme(req.repoName).pipe(
            map(content => ({[key]: content})),
            catchError(error => {
              console.warn(`Failed to fetch README for ${req.repoName}:`, error);
              return of({[key]: { error: `Failed to fetch README: ${error.message}` }});
            })
          );
        
        case 'architecture': 
          return this.getArchitecture(req.repoName).pipe(
            map(content => ({[key]: content})),
            catchError(error => {
              console.warn(`Failed to fetch ARCHITECTURE for ${req.repoName}:`, error);
              return of({[key]: { error: `Failed to fetch ARCHITECTURE: ${error.message}` }});
            })
          );
        
        case 'skills': 
          return this.getSkillsIndex(req.repoName).pipe(
            map(content => ({[key]: content})),
            catchError(error => {
              console.warn(`Failed to fetch SKILLS-INDEX for ${req.repoName}:`, error);
              return of({[key]: { error: `Failed to fetch SKILLS-INDEX: ${error.message}` }});
            })
          );
        
        case 'manifest': 
          if (!req.containerPath) {
            return of({[key]: { error: 'Container path required for PROJECT-MANIFEST' }});
          }
          return this.getProjectManifest(req.repoName, req.containerPath).pipe(
            map(content => ({[key]: content})),
            catchError(error => {
              console.warn(`Failed to fetch PROJECT-MANIFEST for ${req.repoName}/${req.containerPath}:`, error);
              return of({[key]: { error: `Failed to fetch PROJECT-MANIFEST: ${error.message}` }});
            })
          );
        
        case 'context': 
          return this.getRepoContext(req.repoName, req.containerPath).pipe(
            map(content => {
              // Handle context specially - return the object as-is if it's valid JSON
              if (content && typeof content === 'object') {
                return {[key]: JSON.stringify(content)};
              }
              // Return empty JSON if null/undefined
              return {[key]: '{}'};
            }),
            catchError(error => {
              console.warn(`Failed to fetch repo context for ${req.repoName}:`, error);
              return of({[key]: { error: `Failed to fetch repo context: ${error.message}` }});
            })
          );
        
        default: 
          return of({[key]: { error: 'Unknown file type' }});
      }
    });

    return forkJoin(observables).pipe(
      map(results => {
        // Use explicit type casting and Object.assign to avoid reduce type issues
        const finalResult: {[key: string]: string | { error: string }} = {};
        
        results.forEach(result => {
          Object.assign(finalResult, result);
        });
        
        return finalResult;
      }),
      catchError(error => {
        console.error('Batch fetch failed:', error);
        // Return error object for all requested files
        const errorResults: {[key: string]: { error: string }} = {};
        requests.forEach(req => {
          const key = `${req.repoName}-${req.fileType}-${req.containerPath || 'root'}`;
          errorResults[key] = { error: 'Batch fetch operation failed' };
        });
        return of(errorResults);
      })
    );
  }

    /**
   * Prefetch commonly accessed files
   */
  prefetchCommonFiles(repoNames: string[]): void {
    const prefetchRequests = repoNames.flatMap(repo => [
      { repoName: repo, fileType: 'readme' as const },
      { repoName: repo, fileType: 'context' as const }
    ]);

    this.batchFetchFiles(prefetchRequests).subscribe({
      next: () => console.log(`Prefetched files for ${repoNames.length} repositories`),
      error: (error) => console.warn('Prefetch failed:', error)
    });
  }

  /**
   * Enhanced cache clearing with proper type safety
   */
  clearRepoCache(repoName: string, containerPath?: string): void {
    const baseCacheKeys = [
      `readme-${repoName}`,
      `architecture-${repoName}`,
      `skills-index-${repoName}`,
      `repo-context-${repoName}-root`
    ];

    if (containerPath) {
      // Clear specific container cache
      const containerCacheKeys = [
        `project-manifest-${repoName}-${containerPath}`,
        `repo-context-${repoName}-${containerPath}`
      ];
      [...baseCacheKeys, ...containerCacheKeys].forEach(key => this.cacheService.remove(key));
    } else {
      // Clear all cache for this repo
      baseCacheKeys.forEach(key => this.cacheService.remove(key));
      
      // Also clear any container-specific caches (if we know about them)
      // Note: This is a simplified version - in production you might want to 
      // track container paths or use a more sophisticated cache clearing strategy
    }
  }


  /**
   * Validate file request based on location rules
   */
  private validateFileRequest(fileType: string, containerPath?: string): { valid: boolean; message?: string } {
    switch (fileType) {
      case 'skills':
        if (containerPath) {
          return { valid: false, message: 'SKILLS-INDEX.md only exists at repository root level' };
        }
        break;
      
      case 'manifest':
        if (!containerPath) {
          return { valid: false, message: 'PROJECT-MANIFEST.md only exists at container/sub-repository level' };
        }
        break;
      
      case 'readme':
      case 'architecture':
      case 'context':
        // These can exist at both levels
        break;
      
      default:
        return { valid: false, message: `Unknown file type: ${fileType}` };
    }
    
    return { valid: true };
  }
}
