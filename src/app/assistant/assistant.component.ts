import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { AIAssistantService, AIAssistantResponse } from '../services/assistant.service';

@Component({
  selector: 'app-assistant',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './assistant.component.html',
  styleUrls: ['./assistant.component.css']
})
export class AssistantComponent implements OnInit {
  private ai = inject(AIAssistantService);
  private sanitizer = inject(DomSanitizer);

  username = 'yungryce';
  query = '';
  loading = false;
  error = '';

  answerHtml: SafeHtml | null = null;
  repositoriesUsed: { name: string; relevance_score: number }[] = [];

  ngOnInit(): void {
    // no local theme handling; global toggle in AppComponent
  }

  ask(): void {
    this.error = '';
    const q = (this.query || '').trim();
    if (!q) {
      this.error = 'Enter a question.';
      return;
    }
    this.loading = true;
    this.answerHtml = null;
    this.repositoriesUsed = [];

    this.ai.askPortfolio({ query: q, username: this.username }).subscribe({
      next: (res: AIAssistantResponse) => {
        this.loading = false;
        this.repositoriesUsed = res.repositories_used || [];
        const rawHtml = marked.parse(res.response || '', { async: false }) as string;
        const clean = DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } }) as string;
        this.answerHtml = this.sanitizer.bypassSecurityTrustHtml(clean);
      },
      error: () => {
        this.loading = false;
        this.error = 'Failed to get response.';
      }
    });
  }

  clear(): void {
    this.query = '';
    this.answerHtml = null;
    this.repositoriesUsed = [];
    this.error = '';
  }
}
