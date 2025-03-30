import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Observable, switchMap } from 'rxjs';
import { GithubService } from '../../services/github.service';
import { Repository } from '../../services/github.service';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MarkdownModule } from 'ngx-markdown';

@Component({
  selector: 'app-project-about',
  standalone: true,
  imports: [CommonModule, RouterModule, MarkdownModule],
  templateUrl: './project-about.component.html',
  styleUrls: ['./project-about.component.css']
})
export class ProjectAboutComponent implements OnInit {
  repository$!: Observable<Repository>;
  
  constructor(
    private route: ActivatedRoute,
    private githubService: GithubService
  ) { }

  ngOnInit(): void {
    this.repository$ = this.route.params.pipe(
      switchMap(params => this.githubService.getRepository(params['repoName']))
    );
  }
}
