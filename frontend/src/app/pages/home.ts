import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { KIND_LABELS, historyLink } from '../core/history';
import { SearchLog } from '../core/models';
import { Icon } from '../shared/icon';

type Category = 'citacoes' | 'livros_online' | 'jurisprudencia' | 'legislacao';

/** Segundo filtro da busca: muda conforme a categoria e reflete opções que as fontes realmente oferecem. */
const OPTIONS: Record<Category, { label: string; items: [string, string][] }> = {
  citacoes: {
    label: 'Como pesquisar',
    items: [['frase', 'Expressão exata'], ['todas', 'Todas as palavras'], ['qualquer', 'Qualquer palavra']],
  },
  livros_online: {
    label: 'Acervo',
    items: [['bdjur', 'BDJur (STJ)'], ['openalex', 'OpenAlex'], ['google', 'Google Livros']],
  },
  jurisprudencia: {
    label: 'Tribunal',
    items: [
      ['tst', 'TST — acórdãos'], ['stj', 'STJ — processos (DataJud)'], ['trf1', 'TRF1 — processos (DataJud)'],
      ['trf3', 'TRF3 — processos (DataJud)'], ['trf4', 'TRF4 — processos (DataJud)'],
      ['tjsp', 'TJSP — processos (DataJud)'], ['tjrj', 'TJRJ — processos (DataJud)'],
      ['tjmg', 'TJMG — processos (DataJud)'],
    ],
  },
  legislacao: { label: '', items: [] },
};

@Component({
  selector: 'app-home-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, Icon],
  templateUrl: './home.html',
})
export class HomePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  protected readonly form = this.fb.nonNullable.group({
    q: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(200)]],
    category: ['citacoes' as Category],
    option: ['frase'],
  });
  protected readonly category = signal<Category>('citacoes');
  protected readonly option = computed(() => {
    const config = OPTIONS[this.category()];
    const items = config.items.filter(([value]) => value !== 'google' || this.googleEnabled());
    return { label: config.label, items };
  });
  protected readonly googleEnabled = signal(false);
  protected readonly recent = signal<SearchLog[]>([]);
  protected readonly maxMb = signal<number | null>(null);
  protected readonly bookCount = signal<number | null>(null);
  protected readonly kindLabels = KIND_LABELS;

  ngOnInit(): void {
    this.api.history().subscribe({ next: (logs) => this.recent.set(logs.slice(0, 4)), error: () => undefined });
    this.api.health().subscribe({ next: (h) => this.maxMb.set(h.max_upload_mb), error: () => undefined });
    this.api.listBooks().subscribe({ next: (books) => this.bookCount.set(books.length), error: () => undefined });
    this.api.onlineBookSources().subscribe({
      next: (sources) => this.googleEnabled.set(!!sources['google']),
      error: () => undefined,
    });
  }

  protected changeCategory(): void {
    const category = this.form.controls.category.value;
    this.category.set(category);
    this.form.controls.option.setValue(OPTIONS[category].items[0]?.[0] ?? '');
  }

  protected search(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { q, category, option } = this.form.getRawValue();
    const query = q.trim();
    switch (category) {
      case 'livros_online':
        this.router.navigate(['/livros-online'], { queryParams: { q: query, fonte: option } });
        break;
      case 'jurisprudencia':
        this.router.navigate(['/jurisprudencia'], {
          queryParams: option === 'tst' ? { q: query, fonte: 'tst' } : { q: query, fonte: 'datajud', tribunal: option },
        });
        break;
      case 'legislacao':
        this.router.navigate(['/legislacao'], { queryParams: { texto: query } });
        break;
      default:
        this.router.navigate(['/citacoes'], { queryParams: { q: query, modo: option } });
    }
  }

  protected link(log: SearchLog) {
    return historyLink(log);
  }
}
