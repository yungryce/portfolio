import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  // Get the token directly from environment
  get githubToken(): string {
    return environment.githubToken || '';
  }
  
  // Simple loading method that just returns true
  loadConfig(): Observable<boolean> {
    return of(true);
  }
}
