import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CliService } from '../services/cli.service';
import { CacheService } from '../services/cache.service';
import { of } from 'rxjs';
import { tap, catchError } from 'rxjs/operators';

@Component({
  selector: 'app-cli-tool',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './cli-tool.component.html',
  styleUrls: ['./cli-tool.component.css']
})
export class CliToolComponent {
  commandDescription = '';
  suggestedCommands: string[] = [];
  isLoading = false;
  errorMessage = '';
  isCopied: {[key: number]: boolean} = {};
  cacheHit = false;
  
  constructor(
    private cliService: CliService,
    private cacheService: CacheService
  ) {}

  getCommandSuggestions(forceRefresh = false) {
    if (!this.commandDescription.trim()) {
      return;
    }
    
    this.isLoading = true;
    this.errorMessage = '';
    this.isCopied = {};
    
    this.cliService.getSuggestedCommands(this.commandDescription, forceRefresh)
      .pipe(
        catchError(error => {
          this.errorMessage = 'Failed to get command suggestions. Please try again.';
          return of({ commands: [], fromCache: false });
        })
      )
      .subscribe(response => {
        this.suggestedCommands = response.commands;
        this.cacheHit = response.fromCache || false;
        this.isLoading = false;
      });
  }

  refreshResults() {
    this.getCommandSuggestions(true);
  }

  copyToClipboard(command: string, index: number) {
    navigator.clipboard.writeText(command)
      .then(() => {
        // Show temporary "Copied!" message
        this.isCopied[index] = true;
        setTimeout(() => {
          this.isCopied[index] = false;
        }, 2000);
      })
      .catch(err => {
        console.error('Could not copy text: ', err);
      });
  }
  
  isComment(command: string): boolean {
    return command.trim().startsWith('#');
  }
  
  clearCache() {
    if (this.commandDescription.trim()) {
      const cacheKey = `cli_commands:${this.commandDescription.trim().toLowerCase()}`;
      this.cacheService.clear(cacheKey);
    }
  }
}
