import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService, errorMessage } from '../core/api.service';
import { KIND_LABELS, historyLink } from '../core/history';
import { SearchLog } from '../core/models';
import { Icon } from '../shared/icon';

@Component({
  selector: 'app-history-page',
  imports: [RouterLink, DatePipe, Icon],
  template: `
    <header class="page-head">
      <span class="bubble"><app-icon name="clock" [size]="26" /></span>
      <div>
        <h1>Histórico</h1>
        <p class="lead">Pesquisas feitas neste computador. Clique em uma delas para repeti-la.</p>
      </div>
    </header>

    @if (error()) {
      <p class="alert error">{{ error() }}</p>
    }
    @if (logs(); as list) {
      @if (list.length === 0) {
        <p class="alert">Nenhuma pesquisa registrada.</p>
      } @else {
        <section class="recent">
          @for (log of list; track log.id) {
            @let target = link(log);
            <a class="recent-row" [routerLink]="target.path" [queryParams]="target.queryParams">
              <app-icon name="search" [size]="20" />
              <span>
                <strong>{{ log.query }}</strong>
                <small>
                  {{ kindLabels[log.kind] }} · {{ log.total }} resultado(s) · {{ log.created_at | date: 'dd/MM/yyyy • HH:mm' }}
                </small>
              </span>
              <app-icon name="chevron" [size]="18" />
            </a>
          }
        </section>
        <button type="button" class="btn danger" (click)="clear()">Limpar histórico</button>
      }
    }
  `,
})
export class HistoryPage implements OnInit {
  private readonly api = inject(ApiService);

  protected readonly logs = signal<SearchLog[] | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly kindLabels = KIND_LABELS;

  ngOnInit(): void {
    this.api.history(100).subscribe({
      next: (logs) => this.logs.set(logs),
      error: (err) => this.error.set(errorMessage(err)),
    });
  }

  protected link(log: SearchLog) {
    return historyLink(log);
  }

  protected clear(): void {
    if (!confirm('Apagar todo o histórico de pesquisas?')) return;
    this.api.clearHistory().subscribe({
      next: () => this.logs.set([]),
      error: (err) => this.error.set(errorMessage(err)),
    });
  }
}
