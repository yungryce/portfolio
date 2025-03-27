import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';
import { GithubService, Repository } from '../services/github.service';

@Component({
  selector: 'app-projects',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './projects.component.html',
  styleUrls: ['./projects.component.css']
})
export class ProjectsComponent implements OnInit {
  repositories: Repository[] = [];
  loading = true;
  error = false;
  
  constructor(private githubService: GithubService) {}
  
  ngOnInit(): void {
    // Use featured repositories instead of all repositories
    this.githubService.getFeaturedRepositories().subscribe({
      next: (repos) => {
        this.repositories = repos;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error fetching repositories', err);
        this.error = true;
        this.loading = false;
      }
    });
  }
}
