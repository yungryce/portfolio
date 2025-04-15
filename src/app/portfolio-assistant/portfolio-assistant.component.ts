import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PortfolioService } from '../services/portfolio.service';
import { MarkdownModule } from 'ngx-markdown';

@Component({
  selector: 'app-portfolio-assistant',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownModule],
  templateUrl: './portfolio-assistant.component.html',
  styleUrls: ['./portfolio-assistant.component.css']
})
export class PortfolioAssistantComponent {
  userQuery = '';
  response = '';
  isLoading = false;
  errorMessage = '';
  
  constructor(private portfolioService: PortfolioService) {}

  askQuestion() {
    if (!this.userQuery.trim()) {
      return;
    }
    
    this.isLoading = true;
    this.errorMessage = '';
    
    this.portfolioService.queryPortfolio(this.userQuery)
      .subscribe({
        next: (result) => {
          this.response = result.response;
          this.isLoading = false;
        },
        error: (error) => {
          console.error('Error querying portfolio:', error);
          this.errorMessage = 'Failed to get a response. Please try again.';
          this.isLoading = false;
        }
      });
  }
}
