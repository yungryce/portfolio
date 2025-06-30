import { Component, OnInit } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { GithubFilesService } from './services/github-files.service';
import { FEATURED_PROJECTS } from './projects/projects-config';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit {
  title = 'Chigbu Joshua';

  constructor(private filesService: GithubFilesService) {}

  ngOnInit(): void {
    // Prefetch the first 5 featured repositories' common files on app load
    const featuredRepoNames = FEATURED_PROJECTS.slice(0, 5).map(p => p.repoName);
    console.debug('Prefetching common files for featured repositories:', featuredRepoNames);
    this.filesService.prefetchCommonFiles(featuredRepoNames);
  }
}
