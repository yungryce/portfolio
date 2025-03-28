import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface AppConfig {
  githubToken: string;
}

@Injectable({
  providedIn: 'root'
})
export class ConfigService {
  private config: AppConfig = {
    githubToken: ''
  };

  constructor(private http: HttpClient) {}

  async load(): Promise<void> {
    try {
      // First try loading from config.json
      this.config = await firstValueFrom(
        this.http.get<AppConfig>('/assets/config.json')
      );
      console.log('Configuration loaded from config.json');
    } catch (err) {
      console.warn('Could not load config.json, using default values');
      this.config = {
        githubToken: ''
      };
    }
  }

  get githubToken(): string {
    return this.config.githubToken;
  }
}
