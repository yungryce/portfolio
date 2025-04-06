import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, catchError, map, tap } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  constructor(private http: HttpClient) {}

  get apiUrl(): string {
    return environment.apiUrl;
  }

  // Simple method to load any config needed
  loadConfig(): Observable<boolean> {
    console.log('Loading configuration...');
    return of(true);
  }
}
