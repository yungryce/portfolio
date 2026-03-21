import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class App implements OnInit {
  title = 'Portfolio';
  theme: 'light' | 'dark' = 'light';
  foliohiveUrl: string = '';

  
  ngOnInit(): void {
    this.initTheme();
    this.foliohiveUrl = `${environment.foliohiveUrl}/?username=${environment.foliohiveUsername}`;
  }

  private initTheme(): void {
    const saved = (localStorage.getItem('theme') as 'light' | 'dark') || null;
    this.theme = saved ?? (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    this.applyTheme();
  }

  toggleTheme(): void {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('theme', this.theme);
    this.applyTheme();
  }

  private applyTheme(): void {
    const root = document.documentElement; // <html>
    if (this.theme === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
    root.setAttribute('data-theme', this.theme);
  }
}
