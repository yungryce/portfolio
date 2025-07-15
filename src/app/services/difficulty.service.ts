import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, of, EMPTY } from 'rxjs';
import { map, catchError, tap, finalize } from 'rxjs/operators';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';

export interface DifficultyAnalysis {
  difficulty: string;
  score: number;
  confidence: number;
  reasoning: string[];
  breakdown: {
    technology_complexity: number;
    architecture_complexity: number;
    skill_requirements: number;
    project_scope: number;
    repository_metrics: number;
  };
}

export interface DifficultyResponse {
  repository: string;
  difficulty_analysis: DifficultyAnalysis;
  metadata: {
    analyzed_at: string;
    analysis_version: string;
  };
}

export interface DifficultyState {
  [repoName: string]: {
    analysis: DifficultyAnalysis | null;
    loading: boolean;
    error: string | null;
    lastUpdated: number;
  };
}

@Injectable({
  providedIn: 'root'
})
export class DifficultyService {
  private configService = inject(ConfigService);
  private cacheService = inject(CacheService);
  
  // State management
  private difficultyState = new BehaviorSubject<DifficultyState>({});
  public difficultyState$ = this.difficultyState.asObservable();

  // Cache configuration
  private readonly CACHE_TTL = 1000 * 60 * 60 * 24; // 24 hours
  private readonly CACHE_PREFIX = 'repo-difficulty-';

  constructor(private http: HttpClient) {
    this.loadCachedDifficulties();
  }

  /**
   * Get difficulty analysis for a specific repository
   */
  getDifficultyAnalysis(repoName: string): Observable<DifficultyAnalysis | null> {
    const cacheKey = `${this.CACHE_PREFIX}${repoName}`;
    const cached = this.cacheService.get<DifficultyResponse>(cacheKey);
    
    // Return cached data if available and not expired
    if (cached) {
      this.updateRepositoryState(repoName, {
        analysis: cached.difficulty_analysis,
        loading: false,
        error: null,
        lastUpdated: Date.now()
      });
      return of(cached.difficulty_analysis);
    }

    // Set loading state
    this.updateRepositoryState(repoName, {
      analysis: null,
      loading: true,
      error: null,
      lastUpdated: Date.now()
    });

    // Fetch from API
    return this.http.get<DifficultyResponse>(
      `${this.configService.apiUrl}/repository/${encodeURIComponent(repoName)}/difficulty`
    ).pipe(
      map(response => response.difficulty_analysis),
      tap(analysis => {
        // Cache the full response
        const fullResponse: DifficultyResponse = {
          repository: repoName,
          difficulty_analysis: analysis,
          metadata: {
            analyzed_at: new Date().toISOString(),
            analysis_version: "1.0"
          }
        };
        this.cacheService.set(cacheKey, fullResponse, this.CACHE_TTL);
        
        // Update state
        this.updateRepositoryState(repoName, {
          analysis,
          loading: false,
          error: null,
          lastUpdated: Date.now()
        });
      }),
      catchError(error => {
        console.warn(`Failed to fetch difficulty for ${repoName}:`, error);
        
        // Update state with error
        this.updateRepositoryState(repoName, {
          analysis: null,
          loading: false,
          error: error.message || 'Failed to fetch difficulty',
          lastUpdated: Date.now()
        });
        
        return of(null);
      })
    );
  }

  /**
   * Batch fetch difficulties for multiple repositories
   */
  batchFetchDifficulties(repoNames: string[]): Observable<{[repoName: string]: DifficultyAnalysis | null}> {
    const requests = repoNames.map(repoName => 
      this.getDifficultyAnalysis(repoName).pipe(
        map(analysis => ({ [repoName]: analysis })),
        catchError(() => of({ [repoName]: null }))
      )
    );

    return new Observable(observer => {
      const results: {[repoName: string]: DifficultyAnalysis | null} = {};
      let completed = 0;

      requests.forEach(request => {
        request.subscribe({
          next: (result) => {
            Object.assign(results, result);
            completed++;
            
            // Emit intermediate results
            observer.next({ ...results });
            
            // Complete when all requests are done
            if (completed === requests.length) {
              observer.complete();
            }
          },
          error: (error) => {
            console.error('Batch difficulty fetch error:', error);
            completed++;
            if (completed === requests.length) {
              observer.complete();
            }
          }
        });
      });
    });
  }

  /**
   * Get difficulty rating as string (for compatibility with existing code)
   */
  getDifficultyRating(repoName: string): Observable<string> {
    return this.getDifficultyAnalysis(repoName).pipe(
      map(analysis => analysis?.difficulty || 'intermediate')
    );
  }

  /**
   * Check if difficulty is currently loading for a repository
   */
  isDifficultyLoading(repoName: string): boolean {
    const state = this.difficultyState.value[repoName];
    return state?.loading || false;
  }

  /**
   * Get cached difficulty if available
   */
  getCachedDifficulty(repoName: string): DifficultyAnalysis | null {
    const state = this.difficultyState.value[repoName];
    return state?.analysis || null;
  }

  /**
   * Check if difficulty data is loaded (not loading and not error)
   */
  isDifficultyLoaded(repoName: string): boolean {
    const state = this.difficultyState.value[repoName];
    return !!(state?.analysis && !state.loading && !state.error);
  }

  /**
   * Fetch difficulty for a single repository (used by project-about)
   */
  fetchDifficulty(repoName: string): Observable<DifficultyAnalysis | null> {
    return this.getDifficultyAnalysis(repoName);
  }

  /**
   * Get difficulty rating synchronously from cache
   */
  getDifficultyRatingSync(repoName: string): string {
    const analysis = this.getCachedDifficulty(repoName);
    return analysis?.difficulty || 'intermediate';
  }

  /**
   * Get numeric difficulty score for sorting
   */
  getDifficultyNumericScore(difficulty: string): number {
    const scores: { [key: string]: number } = {
      'beginner': 1,
      'intermediate': 2,
      'advanced': 3,
      'expert': 4
    };
    return scores[difficulty] || 2;
  }

  /**
   * Get difficulty color for UI display
   */
  getDifficultyColor(difficulty: string): string {
    const colors: { [key: string]: string } = {
      'beginner': '#10b981',
      'intermediate': '#3b82f6', 
      'advanced': '#8b5cf6',
      'expert': '#ef4444'
    };
    return colors[difficulty] || '#6b7280';
  }

  // Private helper methods
  private updateRepositoryState(repoName: string, update: Partial<DifficultyState[string]>): void {
    const currentState = this.difficultyState.value;
    const repoState = currentState[repoName] || {
      analysis: null,
      loading: false,
      error: null,
      lastUpdated: 0
    };

    const newState = {
      ...currentState,
      [repoName]: { ...repoState, ...update }
    };

    this.difficultyState.next(newState);
  }

  private loadCachedDifficulties(): void {
    // Load any cached difficulties into state on service initialization
    // This is a simplified implementation - you might want to scan cache keys
    console.log('Repository Difficulty Service initialized');
  }
}
