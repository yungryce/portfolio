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
    // If environment already has a token (for non-production environments), use it
    if (environment.githubToken) {
      this.config.githubToken = environment.githubToken;
      console.log('Using token from environment:', this.config.githubToken ? 'Token exists (masked)' : 'No token');
      return of(true);
    }
    
    // Otherwise load from assets/config.json (created by build-config.js)
    return this.http.get<any>('./assets/config.json').pipe(
      tap(config => {
        this.config = config;
        console.log('Loaded token from config.json:', config.githubToken ? 'Token exists (masked)' : 'No token');
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
}
