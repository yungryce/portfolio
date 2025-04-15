import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { ProjectsComponent } from './projects/projects.component';
import { ProjectAboutComponent } from './projects/project-about/project-about.component';
import { PortfolioAssistantComponent } from './portfolio-assistant/portfolio-assistant.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'projects', component: ProjectsComponent },
  { path: 'projects/:repoName/about', component: ProjectAboutComponent },
  { path: 'assistant', component: PortfolioAssistantComponent },
  { path: '**', redirectTo: '' }
];
