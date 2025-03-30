import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { catchError, map, tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  private config: any = {};
  
  constructor(private http: HttpClient) {}

  // Call this in your app initialization
  loadConfig(): Observable<boolean> {
    // First try to load from environment variables
    if (environment.githubToken) {
      this.config.githubToken = environment.githubToken;
      const maskedToken = this.getMaskedToken();
      console.log(`Using token from environment: ${maskedToken}`);
      
      // Still load from config.json as a fallback or for other configuration
      return this.loadFromConfigJson().pipe(
        map(() => true)
      );
    } else {
      console.log('No token in environment, loading from config.json');
      return this.loadFromConfigJson();
    }
  }

  private loadFromConfigJson(): Observable<boolean> {
    return this.http.get<any>('./assets/config.json').pipe(
      tap(config => {
        // If we already have a token from environment, don't override it
        if (!this.config.githubToken && config.githubToken) {
          this.config.githubToken = config.githubToken;
        }
        
        const maskedToken = this.getMaskedToken();
        console.log(`Config from config.json, token: ${maskedToken}`);
      }),
      map(() => true),
      catchError(err => {
        console.error('Could not load configuration', err);
        return of(false);
      })
    );
  }

  get githubToken(): string {
    return this.config.githubToken || '';
  }
  
  private getMaskedToken(): string {
    const token = this.config.githubToken || '';
    if (!token) return 'No token';
    if (token.length <= 8) return '********';
    return `${token.substring(0, 4)}...${token.substring(token.length - 4)}`;
  }
}
