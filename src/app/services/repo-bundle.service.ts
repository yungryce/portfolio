import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';

export interface RepoBundleResponse {
  username: string;
  fingerprint?: string;
  last_modified?: string;
  size_bytes?: number;
  data: { has_documentation: boolean }[];
}

export interface SingleRepoBundleResponse {
  username: string;
  repo: string;
  fingerprint?: string;
  last_modified?: string;
  size_bytes?: number;
  data: any; // single repository bundle
}

@Injectable({ providedIn: 'root' })
export class RepoBundleService {
  private http = inject(HttpClient);
  private config = inject(ConfigService);
  private cache = inject(CacheService);

  /**
   * GET /bundles/{username}
   * Unwraps { status, data } shapes and guarantees data is an array.
   */
  getUserBundle(username: string, useCache = true): Observable<RepoBundleResponse> {
    const url = `${this.config.apiUrl}/bundles/${encodeURIComponent(username)}`;
    const cacheKey = `bundle-${username}`;

    if (useCache) {
      const cached = this.cache.get<RepoBundleResponse>(cacheKey);
      if (cached) return of(cached);
    }

    return this.http.get<any>(url).pipe(
      map((res: any) => {
        // Expected: { status: 'success', data: { username, data: [] } }
        let payload: RepoBundleResponse | null = null;

        if (res?.status === 'success' && res?.data) {
          payload = res.data as RepoBundleResponse;
        } else if (res?.username && Array.isArray(res?.data)) {
          payload = res as RepoBundleResponse;
        } else if (Array.isArray(res)) {
          payload = { username, data: res };
        } else if (Array.isArray(res?.data)) {
          payload = { username, data: res.data };
        } else {
          payload = { username, data: [] };
        }

        if (!Array.isArray(payload.data)) payload.data = [];
        this.cache.set(cacheKey, payload, 1000 * 60 * 10);
        return payload;
      }),
      catchError(err => {
        console.error('getUserBundle error:', err);
        return of({ username, data: [] } as RepoBundleResponse);
      })
    );
  }

  /**
   * GET /bundles/{username}/{repo}
   * Unwraps { status, data } shapes and returns normalized payload.
   */
  getUserSingleRepoBundle(username: string, repo: string, useCache = true): Observable<SingleRepoBundleResponse> {
    const url = `${this.config.apiUrl}/bundles/${encodeURIComponent(username)}/${encodeURIComponent(repo)}`;
    const cacheKey = `repo-bundle-${username}-${repo}`;

    if (useCache) {
      const cached = this.cache.get<SingleRepoBundleResponse>(cacheKey);
      if (cached) return of(cached);
    }

    return this.http.get<any>(url).pipe(
      map((res: any) => {
        let payload: SingleRepoBundleResponse;

        if (res?.status === 'success' && res?.data) {
          payload = res.data as SingleRepoBundleResponse;
        } else if (res?.username && res?.repo && 'data' in res) {
          payload = res as SingleRepoBundleResponse;
        } else {
          payload = { username, repo, data: res?.data ?? null };
        }

        this.cache.set(cacheKey, payload, 1000 * 60 * 10);
        return payload;
      }),
      catchError(err => {
        console.error('getUserSingleRepoBundle error:', err);
        return of({ username, repo, data: null } as SingleRepoBundleResponse);
      })
    );
  }

  /**
   * Alias for convenience.
   */
  getUserSingleRepo(username: string, repo: string, useCache = true): Observable<SingleRepoBundleResponse> {
    return this.getUserSingleRepoBundle(username, repo, useCache);
  }
}
