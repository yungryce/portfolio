import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';
import { tap } from 'rxjs/operators';

export interface PortfolioQueryResponse {
  response: string;
  repositories?: any[];
}

@Injectable({
  providedIn: 'root'
})
export class PortfolioService {
  private configService = inject(ConfigService);
  private cacheService = inject(CacheService);
  
  constructor(private http: HttpClient) { }

  queryPortfolio(query: string): Observable<PortfolioQueryResponse> {
    console.log('Querying portfolio with:', query);
    return this.http.post<PortfolioQueryResponse>(
      `${this.configService.apiUrl}/ai`,
      { query }
    ).pipe(
      tap(response => console.log('AI Response:', response))
    );
  }
}
