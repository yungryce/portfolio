import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of } from 'rxjs';
import { ConfigService } from './config.service';

export interface AIAssistantRequest {
  query: string;
  username?: string;
  instance_id?: string;
  status_query_url?: string;
}

export interface AIAssistantResponse {
  response: string; // Markdown text
  repositories_used: { name: string; relevance_score: number }[];
  total_repositories: number;
  query: string;
}

@Injectable({ providedIn: 'root' })
export class AIAssistantService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);

  askPortfolio(req: AIAssistantRequest): Observable<AIAssistantResponse> {
    const url = `${this.config.apiUrl}/ai`;
    return this.http.post<any>(url, req).pipe(
      map(res => {
        // API returns { status: 'success', data: {...} }
        if (res?.status === 'success' && res?.data) return res.data as AIAssistantResponse;
        return res as AIAssistantResponse;
      }),
      catchError(err => {
        console.error('AI request failed:', err);
        return of({
          response: 'AI service failed or is unavailable. Please try again.',
          repositories_used: [],
          total_repositories: 0,
          query: req.query
        } as AIAssistantResponse);
      })
    );
  }
}