import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { ProjectsComponent } from './projects/projects.component';
import { ProjectComponent } from './projects/project/project.component';
import { PortfolioAssistantComponent } from './portfolio-assistant/portfolio-assistant.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'projects', component: ProjectsComponent },
  { path: 'projects/:repo', component: ProjectComponent },
  { path: 'assistant', component: PortfolioAssistantComponent },
  { path: '**', redirectTo: '' }
];
