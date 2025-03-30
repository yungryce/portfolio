import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  private config: any = {};
  
  constructor(private http: HttpClient) {}

  // Call this in your app initialization
  loadConfig(): Observable<boolean> {
    // Set token from environment variables
    this.config.githubToken = environment.githubToken || '';
    
    const maskedToken = this.getMaskedToken();
    if (this.config.githubToken) {
      console.log(`Using token from environment: ${maskedToken}`);
      return of(true);
    } else {
      console.warn('No GitHub token found in environment');
      // Return success anyway as we might not need the token for some operations
      return of(true);
    }
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
