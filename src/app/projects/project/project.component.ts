import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { RepoBundleService, SingleRepoBundleResponse } from '../../services/repo-bundle.service';
import { Observable, map } from 'rxjs';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

interface RepoDetailVM {
  name: string;
  updatedAt?: string;
  type: string;
  description: string;
  primaryStack: string[];
  languagesPct: { k: string; pct: number }[];
  htmlUrl?: string;
  isFork?: boolean;
  readme?: string;
}

@Component({
  selector: 'app-project',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './project.component.html',
  styleUrls: ['./project.component.css']
})
export class ProjectComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private repoBundleService = inject(RepoBundleService);
  private sanitizer = inject(DomSanitizer);

  username = 'yungryce';
  repoName = '';
  repo$!: Observable<RepoDetailVM | null>;

  readmeHtml: SafeHtml | null = null;
  toc: { text: string; id: string; level: number }[] = [];

  ngOnInit(): void {
    this.repoName = this.route.snapshot.paramMap.get('repo') || '';
    this.repo$ = this.repoBundleService
      .getUserSingleRepoBundle(this.username, this.repoName)
      .pipe(map(res => {
        const vm = this.toVM(res?.data);
        if (vm?.readme) this.renderMarkdown(vm.readme);
        return vm;
      }));
  }

  private toVM(r: any | undefined | null): RepoDetailVM | null {
    if (!r) return null;
    const pid = r?.repoContext?.project_identity ?? {};
    const type = r?.repoContext?.type ?? pid?.type ?? 'Unknown';
    const description = r?.repoContext?.description ?? pid?.description ?? 'No description';
    const langs = r?.languages ?? {};
    const total = Object.values(langs).reduce((a: number, b: any) => a + Number(b), 0) || 1;
    const languagesPct = Object.entries(langs)
      .map(([k, v]) => ({ k, pct: Math.round((Number(v) / total) * 100) }))
      .sort((a, b) => b.pct - a.pct);

    return {
      name: r?.name ?? r?.metadata?.name ?? this.repoName,
      updatedAt: r?.metadata?.updated_at ?? r?.metadata?.pushed_at,
      type,
      description,
      primaryStack: r?.repoContext?.tech_stack?.primary ?? [],
      languagesPct,
      htmlUrl: r?.metadata?.html_url,
      isFork: !!r?.metadata?.fork,
      readme: r?.readme
    };
  }

  private renderMarkdown(md: string): void {
    this.toc = [];

    const slug = (s: string) =>
      s.toLowerCase().trim().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');

    // 1) Parse markdown (sync) and sanitize
    const rawHtml = marked.parse(md, { async: false }) as string;
    const cleanHtml = DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } }) as string;

    // 2) Post-process headings to assign ids and build TOC
    const parser = new DOMParser();
    const doc = parser.parseFromString(cleanHtml, 'text/html');

    const headings = doc.body.querySelectorAll('h1,h2,h3,h4,h5,h6');
    headings.forEach(h => {
      const text = (h.textContent || '').trim();
      const level = Number(h.tagName.substring(1));
      const id = slug(text);
      if (!h.id) h.id = id;
      this.toc.push({ text, id, level });
    });

    // 3) Trust processed HTML for rendering
    this.readmeHtml = this.sanitizer.bypassSecurityTrustHtml(doc.body.innerHTML);
  }
}
