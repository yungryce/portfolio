import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { ProjectsComponent } from './projects/projects.component';
import { ProjectAboutComponent } from './projects/project-about/project-about.component';
import { CliToolComponent } from './cli-tool/cli-tool.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'projects', component: ProjectsComponent },
  { path: 'projects/:repoName/about', component: ProjectAboutComponent },
  { path: 'cli-tool', component: CliToolComponent },
  { path: '**', redirectTo: '' }
];
