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
  
  constructor(private http: HttpClient) {
    console.log('ConfigService initialized');
  }
  
  // Get the token with enhanced logging
  get githubToken(): string {
    // If we've already loaded the token
    if (this._token !== null) {
      console.log(`Using cached GitHub token from ${this.tokenSource}`);
      return this._token;
    }

    // First try from environment (set during build time)
    if (environment.githubToken) {
      this._token = environment.githubToken;
      this.tokenSource = 'environment.ts';
      console.log(`Using GitHub token from environment`);
      return this._token;
    }

    // If no token yet, use empty string
    console.warn('No GitHub token found in environment');
    this._token = '';
    this.tokenSource = 'none';
    return this._token;
  }
  
  // Load configuration for runtime fallbacks
  loadConfig(): Observable<boolean> {
    console.log('Loading runtime configuration...');
    this.logEnvironmentInfo();
    
    // For runtime, try to load from config.json
    return this.http.get<{githubToken: string}>('assets/config.json').pipe(
      tap(config => {
        if (config && config.githubToken) {
          this._token = config.githubToken;
          this.tokenSource = 'assets/config.json';
          console.log(`Loaded GitHub token from config.json`);
        } else {
          console.warn('config.json found but no token in it');
        }
      }),
      map(() => true),
      catchError(error => {
        console.warn(`Failed to load config.json: ${error.status} ${error.statusText}`);
        
        // Final fallback to Azure SWA runtime variables
        if (typeof window !== 'undefined') {
          // Try direct window environment variable
          if ((window as any).GITHUB_TOKEN) {
            this._token = (window as any).GITHUB_TOKEN;
            this.tokenSource = 'window.GITHUB_TOKEN';
            console.log(`Found GitHub token in window.GITHUB_TOKEN`);
            return of(true);
          }
          
          // Try Azure SWA env object
          if ((window as any).__env && (window as any).__env.GITHUB_TOKEN) {
            this._token = (window as any).__env.GITHUB_TOKEN;
            this.tokenSource = 'Azure SWA runtime';
            console.log(`Found GitHub token in Azure SWA runtime env`);
            return of(true);
          }
        }
        
        // Fall back to environment
        if (!this._token && environment.githubToken) {
          this._token = environment.githubToken;
          this.tokenSource = 'environment.ts (fallback)';
          console.log(`Using environment fallback for GitHub token`);
        } else if (!this._token) {
          console.error('No GitHub token available from any source');
        }
        
        return of(true);
      })
    );
  }

  // Helper to log environment information
  private logEnvironmentInfo(): void {
    if (typeof window === 'undefined') return;
    
    try {
      const currentHost = window.location.hostname;
      const isSwaHost = currentHost.includes('staticwebapp.app') || 
                        currentHost.includes('azurestaticapps.net') ||
                        currentHost === 'chxgbx.com';
      
      console.log(`Current hostname: ${currentHost}`);
      console.log(`Running in Azure SWA environment: ${isSwaHost}`);
      console.log(`Environment token available: ${environment.githubToken ? 'Yes' : 'No'}`);
      console.log(`window.__env available: ${(window as any).__env !== undefined}`);
      
      if ((window as any).__env) {
        console.log(`Azure SWA environment variables: ${Object.keys((window as any).__env).join(', ')}`);
      }
    } catch (error) {
      console.error('Error checking environment:', error);
    }
  }
}
