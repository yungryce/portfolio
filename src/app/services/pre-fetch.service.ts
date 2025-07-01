import { Injectable } from '@angular/core';
import { GithubFilesService } from './github-files.service';
import { FEATURED_PROJECTS } from '../projects/projects-config';

@Injectable({
  providedIn: 'root'
})
export class PreFetchService {
  private initialized = false;

  constructor(private filesService: GithubFilesService) {}

  initialize(): void {
    if (this.initialized) return;
    
    const featuredRepoNames = FEATURED_PROJECTS.slice(0, 5).map(p => p.repoName);
    console.debug('Prefetching common files for featured repositories:', featuredRepoNames);
    this.filesService.prefetchCommonFiles(featuredRepoNames);
    
    this.initialized = true;
  }
}
