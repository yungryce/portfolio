import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { ConfigService } from './config.service';
import { CacheService } from './cache.service';

export interface RepoBundleResponse {
  username: string;
  fingerprint?: string;
  last_modified?: string;
  size_bytes?: number;
  data: any[]; // bundle array
}

export interface BundleIndexEntry {
  username: string;
  blob_name: string;
  last_modified?: string;
  size_bytes?: number;
  data?: any[]; // present only when include_data=true
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
  private config = inject(ConfigService);
  private http = inject(HttpClient);
  private cache = inject(CacheService);

  
  /**
   * Fetches a single repository bundle
   * @param username GitHub username
   * @param repo Repository name
   * @param useCache Whether to use client-side cache
   * @returns Observable of the repository bundle
   */
  getUserBundle(username: string, useCache = true): Observable<RepoBundleResponse> {
    const url = `${this.config.apiUrl}/bundles/${encodeURIComponent(username)}`;
    const cacheKey = `bundle-${username}`;

    if (useCache) {
      const cached = this.cache.get<RepoBundleResponse>(cacheKey);
      if (cached) return new Observable(sub => { sub.next(cached); sub.complete(); });
    }

    return this.http.get<RepoBundleResponse>(url).pipe(
      map(res => {
        this.cache.set(cacheKey, res, 1000 * 60 * 10);
        return res;
      })
    );
  }

  /**
   * Fetches a single repository bundle
   * @param username GitHub username
   * @param repo Repository name
   * @param useCache Whether to use client-side cache
   * @returns Observable of the repository bundle
   */
  getUserSingleRepoBundle(username: string, repo: string, useCache = true): Observable<SingleRepoBundleResponse> {
    const url = `${this.config.apiUrl}/bundles/${encodeURIComponent(username)}/${encodeURIComponent(repo)}`;
    const cacheKey = `repo-bundle-${username}-${repo}`;

    if (useCache) {
      const cached = this.cache.get<SingleRepoBundleResponse>(cacheKey);
      if (cached) return new Observable(sub => { sub.next(cached); sub.complete(); });
    }

    return this.http.get<SingleRepoBundleResponse>(url).pipe(
      map(res => {
        this.cache.set(cacheKey, res, 1000 * 60 * 10); // Cache for 10 minutes
        return res;
      })
    );
  }
}