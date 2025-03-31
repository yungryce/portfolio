import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, catchError, map, tap } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  private tokenSource: string = 'Not initialized';
  private _token: string | null = null;
  
  constructor(private http: HttpClient) {}
  
  // Get the token with enhanced logging
  get githubToken(): string {
    // If we've already loaded the token
    if (this._token !== null) {
      console.log(`Using cached GitHub token from ${this.tokenSource}: ${this._token ? this._token.substring(0, 4) + '...' : 'empty'}`);
      return this._token;
    }

    // First try from environment
    if (environment.githubToken) {
      this._token = environment.githubToken;
      this.tokenSource = 'environment.ts';
      console.log(`Retrieved GitHub token from environment file: ${this._token.substring(0, 4)}...`);
      return this._token;
    }

    // If no token yet, use empty string
    console.warn('No GitHub token found in environment');
    this._token = '';
    this.tokenSource = 'none';
    return this._token;
  }
  
  // Load configuration, potentially from external sources
  loadConfig(): Observable<boolean> {
    console.log('Loading application configuration...');
    
    // Try to load from config.json which might be created during build/deployment
    return this.http.get<{githubToken: string}>('assets/config.json').pipe(
      tap(config => {
        if (config && config.githubToken) {
          this._token = config.githubToken;
          this.tokenSource = 'assets/config.json';
          console.log(`Loaded GitHub token from config.json: ${this._token.substring(0, 4)}...`);
        } else {
          console.warn('No GitHub token found in config.json');
        }
      }),
      map(() => true),
      catchError(error => {
        console.warn('Failed to load config.json:', error);
        console.log('Using environment token as fallback');
        
        // Fallback to environment token
        this._token = environment.githubToken || '';
        this.tokenSource = 'environment.ts (fallback)';
        
        if (this._token) {
          console.log(`Using fallback GitHub token: ${this._token.substring(0, 4)}...`);
        } else {
          console.error('No GitHub token available from any source');
        }
        
        return of(true);
      })
    );
  }
}
