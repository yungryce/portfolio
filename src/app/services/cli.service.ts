import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';
import { Observable, of } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';

export interface CommandSuggestionResponse {
  commands: string[];
  explanation?: string;
  fromCache?: boolean;
}

interface CachedCommandResponse extends CommandSuggestionResponse {
  timestamp: number;
}

@Injectable({
  providedIn: 'root'
})
export class CliService {
  private configService = inject(ConfigService);
  private cacheService = inject(CacheService);
  private cacheValidityPeriod = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

  constructor(private http: HttpClient) { }

  getSuggestedCommands(description: string, forceRefresh = false): Observable<CommandSuggestionResponse & { fromCache?: boolean }> {
    const cacheKey = `cli_commands:${description.trim().toLowerCase()}`;
    
    // Check if we have a cached response and if forceRefresh is not requested
    if (!forceRefresh) {
      const cachedResponse = this.cacheService.get<CachedCommandResponse>(cacheKey);
      
      if (cachedResponse) {
        // Check if cache is still valid (less than 24 hours old)
        const cacheAge = Date.now() - cachedResponse.timestamp;
        
        if (cacheAge < this.cacheValidityPeriod) {
          // Use cached results with an additional flag to indicate cache hit
          return of({
            commands: cachedResponse.commands,
            explanation: cachedResponse.explanation,
            fromCache: true
          });
        }
      }
    }
    
    // If not in cache, cache expired, or force refresh is requested, make API call
    return this.http.post<CommandSuggestionResponse>(
      `${this.configService.apiUrl}/cli/suggest-commands`, 
      { description }
    ).pipe(
      tap(response => {
        // Store result in cache with timestamp
        this.cacheService.set(cacheKey, {
          ...response,
          timestamp: Date.now()
        });
      }),
      // Add fromCache=false flag to the response
      tap(response => response.fromCache = false),
      catchError(error => {
        console.error('Error fetching command suggestions:', error);
        throw error;
      })
    );
  }
  
  clearCommandCache(description?: string): void {
    if (description) {
      const cacheKey = `cli_commands:${description.trim().toLowerCase()}`;
      this.cacheService.clear(cacheKey);
    } else {
      // Clear all cli commands from cache by finding keys that start with "cli_commands:"
      // This would require an enhancement to CacheService to do properly
      // For now, we'll just clear the specific key if provided
    }
  }
}
