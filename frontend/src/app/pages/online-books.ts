import { Component, OnInit, inject, input, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService, errorMessage } from '../core/api.service';
import { OnlineBook, OnlineSearchResponse } from '../core/models';
import { CopyButton } from '../shared/copy-button';
import { Icon } from '../shared/icon';
import { ReferenceView } from '../shared/reference-view';

@Component({
  selector: 'app-online-books-page',
  imports: [ReactiveFormsModule, CopyButton, ReferenceView, Icon],
  templateUrl: './online-books.html',
})
export class OnlineBooksPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  /** Parâmetros da rota (`?q=&fonte=&tipo=`): abrem a página já pesquisando. */
  readonly q = input<string>();
  readonly fonte = input<string>();
  readonly tipo = input<string>();

  protected readonly form = this.fb.nonNullable.group({
    q: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(200)]],
    fonte: ['bdjur'],
    tipo: [''],
    soDireito: [true],
  });
  protected readonly examples = ['"boa-fé objetiva"', 'responsabilidade civil do Estado', 'usucapião extrajudicial', '"proteção de dados pessoais"'];
  protected readonly types = signal<string[]>([]);
  protected readonly googleEnabled = signal(false);
  protected readonly result = signal<OnlineSearchResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  /** Endereço do PDF em importação e mensagens de falha por obra. */
  protected readonly importing = signal<string | null>(null);
  protected readonly importErrors = signal<Record<string, string>>({});

  ngOnInit(): void {
    this.api.onlineBookTypes().subscribe({ next: (types) => this.types.set(types), error: () => undefined });
    this.api.onlineBookSources().subscribe({
      next: (sources) => this.googleEnabled.set(!!sources['google']),
      error: () => undefined,
    });
    const query = this.q()?.trim();
    if (query) {
      const fonte = ['bdjur', 'openalex', 'google'].includes(this.fonte() ?? '') ? this.fonte()! : 'bdjur';
      // A opção do Google só é desenhada depois da consulta às fontes; o valor do formulário já vale.
      if (fonte === 'google') this.googleEnabled.set(true);
      this.form.patchValue({ q: query, fonte, tipo: this.tipo() ?? '' });
      this.search(1);
    }
  }

  protected search(page: number): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const { q, fonte, tipo, soDireito } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set(null);
    this.importErrors.set({});
    this.api.onlineBooks(q.trim(), fonte, tipo, page, soDireito).subscribe({
      next: (response) => {
        this.result.set(response);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  protected tryExample(example: string): void {
    this.form.controls.q.setValue(example);
    this.search(1);
  }

  protected hasNext(data: OnlineSearchResponse): boolean {
    return data.total !== null && data.page * data.page_size < data.total && data.page < 50;
  }

  /** Baixa o PDF para a biblioteca e abre a pesquisa de citações já restrita a ele. */
  protected importAndSearch(book: OnlineBook): void {
    if (!book.pdf_url || this.importing()) return;
    const url = book.pdf_url;
    const query = this.result()?.query ?? this.form.controls.q.value;
    this.importing.set(url);
    this.api.importFromUrl(book).subscribe({
      next: (imported) => this.openCitations(query, imported.book.id),
      error: (err: HttpErrorResponse) => {
        this.importing.set(null);
        const existing = err.status === 409 ? err.error?.detail?.book_id : null;
        if (existing) {
          this.openCitations(query, existing);
        } else {
          this.importErrors.update((errors) => ({ ...errors, [url]: errorMessage(err) }));
        }
      },
    });
  }

  protected fileSize(bytes: number | null): string {
    if (!bytes) return '';
    const mb = bytes / 1024 / 1024;
    return mb >= 1 ? ` (${mb.toFixed(1).replace('.', ',')} MB)` : ` (${Math.max(1, Math.round(bytes / 1024))} KB)`;
  }

  private openCitations(query: string, bookId: number): void {
    // As aspas do termo servem à busca nos acervos; a pesquisa local já tem o modo "expressão exata".
    this.router.navigate(['/citacoes'], { queryParams: { q: query.replaceAll('"', ''), livro: bookId } });
  }
}
