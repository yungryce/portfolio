import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RepoBundleService, RepoBundleResponse } from '../services/repo-bundle.service';
import { Observable, map } from 'rxjs';

interface RepositoryData {
  name: string;
  metadata: {
    name: string;
    description?: string;
    html_url: string;
    fork: boolean;
    created_at: string;
    updated_at: string;
    pushed_at: string;
    stargazers_count: number;
  };
  languages: Record<string, number>;
  categorized_types: Record<string, string[]>;
  readme: string;
  has_documentation: boolean;
}

@Component({
  selector: 'app-projects',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './projects.component.html',
  styleUrls: ['./projects.component.css']
})
export class ProjectsComponent implements OnInit {
  private repoBundleService = inject(RepoBundleService);
  repoBundle$!: Observable<RepoBundleResponse>;
  filteredRepos$!: Observable<RepositoryData[]>;
  username = 'yungryce'; // Default username
  
  // Filter options
  showForks = false;
  selectedLanguage = '';
  selectedTechnology = '';
  searchTerm = '';
  
  // Sorting
  sortBy = 'updated'; // Options: 'name', 'stars', 'updated'
  sortDirection = 'desc'; // 'asc' or 'desc'
  
  // Available filter options
  allLanguages: string[] = [];
  allTechnologies: string[] = [];

  ngOnInit(): void {
    this.loadRepoBundle();
  }

  loadRepoBundle(): void {
    this.repoBundle$ = this.repoBundleService.getUserBundle(this.username);
    
    // Apply filtering and sorting
    this.filteredRepos$ = this.repoBundle$.pipe(
      map(bundle => {
        // Extract all unique languages and technologies
        this.extractFilterOptions(bundle.data);
        
        // Apply filters
        return this.filterAndSortRepos(bundle.data);
      })
    );
  }
  
  private extractFilterOptions(repos: RepositoryData[]): void {
    const languages = new Set<string>();
    const technologies = new Set<string>();
    
    repos.forEach(repo => {
      // Extract languages
      if (repo.languages) {
        Object.keys(repo.languages).forEach(lang => languages.add(lang));
      }
      
      // Extract technologies
      if (repo.categorized_types) {
        Object.values(repo.categorized_types).forEach(techArray => {
          techArray.forEach(tech => technologies.add(tech));
        });
      }
    });
    
    this.allLanguages = Array.from(languages).sort();
    this.allTechnologies = Array.from(technologies).sort();
  }
  
  private filterAndSortRepos(repos: RepositoryData[]): RepositoryData[] {
    // Apply filters
    let result = repos.filter(repo => {
      // Filter by fork status
      if (!this.showForks && repo.metadata.fork) {
        return false;
      }
      
      // Filter by search term
      if (this.searchTerm && !this.matchesSearchTerm(repo, this.searchTerm)) {
        return false;
      }
      
      // Filter by language
      if (this.selectedLanguage && 
          (!repo.languages || !Object.keys(repo.languages).includes(this.selectedLanguage))) {
        return false;
      }
      
      // Filter by technology
      if (this.selectedTechnology && !this.hasTechnology(repo, this.selectedTechnology)) {
        return false;
      }
      
      return true;
    });
    
    // Then sort
    result = this.sortRepos(result, this.sortBy, this.sortDirection);
    
    return result;
  }
  
  private matchesSearchTerm(repo: RepositoryData, term: string): boolean {
    const lowerTerm = term.toLowerCase();
    return (
      repo.metadata.name.toLowerCase().includes(lowerTerm) ||
      (repo.metadata.description && repo.metadata.description.toLowerCase().includes(lowerTerm))
    );
  }
  
  private hasTechnology(repo: RepositoryData, tech: string): boolean {
    if (!repo.categorized_types) return false;
    
    return Object.values(repo.categorized_types).some(
      techArray => techArray.includes(tech)
    );
  }
  
  private sortRepos(repos: RepositoryData[], sortBy: string, direction: string): RepositoryData[] {
    return [...repos].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'name':
          comparison = a.metadata.name.localeCompare(b.metadata.name);
          break;
        case 'stars':
          comparison = a.metadata.stargazers_count - b.metadata.stargazers_count;
          break;
        case 'updated':
        default:
          comparison = new Date(a.metadata.pushed_at).getTime() - 
                       new Date(b.metadata.pushed_at).getTime();
          break;
      }
      
      return direction === 'asc' ? comparison : -comparison;
    });
  }
  
  // Template helper methods
  applyFilters(): void {
    this.loadRepoBundle();
  }
  
  resetFilters(): void {
    this.showForks = false;
    this.selectedLanguage = '';
    this.selectedTechnology = '';
    this.searchTerm = '';
    this.sortBy = 'updated';
    this.sortDirection = 'desc';
    this.loadRepoBundle();
  }
  
  objectKeys(obj: any): string[] {
    return obj ? Object.keys(obj) : [];
  }
}
