import { Component, OnInit, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService, errorMessage } from '../core/api.service';
import { Book, FIELD_LABELS, NOT_IDENTIFIED, Occurrence, SearchLog, SearchMode, SearchResponse } from '../core/models';
import { CopyButton } from '../shared/copy-button';
import { Icon } from '../shared/icon';
import { ReferenceView } from '../shared/reference-view';

interface Segment {
  text: string;
  hit: boolean;
}

const PAGE_SIZE = 20;

@Component({
  selector: 'app-citations-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, CopyButton, ReferenceView, Icon],
  templateUrl: './citations.html',
})
export class CitationsPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly fb = inject(FormBuilder);

  /** Parâmetros `?q=` e `?livro=` da rota: abrem a página já pesquisando. */
  readonly q = input<string>();
  readonly livro = input<string>();
  readonly modo = input<string>();

  protected readonly form = this.fb.nonNullable.group({
    q: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(300)]],
    mode: ['frase' as SearchMode],
    bookId: [null as number | null],
  });

  protected readonly books = signal<Book[]>([]);
  protected readonly history = signal<SearchLog[]>([]);
  protected readonly result = signal<SearchResponse | null>(null);
  protected readonly occurrences = signal<Occurrence[]>([]);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notIdentified = NOT_IDENTIFIED;

  ngOnInit(): void {
    this.api.listBooks().subscribe({
      next: (books) => this.books.set(books),
      error: (err) => this.error.set(errorMessage(err)),
    });
    this.loadHistory();
    const query = this.q()?.trim();
    if (query) {
      const bookId = Number(this.livro());
      const mode = (['frase', 'todas', 'qualquer'] as const).find((m) => m === this.modo()) ?? 'frase';
      this.form.patchValue({ q: query, mode, bookId: Number.isInteger(bookId) && bookId > 0 ? bookId : null });
      this.search();
    }
  }

  protected search(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.occurrences.set([]);
    this.result.set(null);
    this.fetch(0);
  }

  protected more(): void {
    const current = this.result();
    if (current) this.fetch(current.offset + current.limit);
  }

  protected hasMore(): boolean {
    const current = this.result();
    return !!current && current.offset + current.limit < current.total_pages;
  }

  protected repeat(log: SearchLog): void {
    const bookId = typeof log.params['book_id'] === 'number' ? log.params['book_id'] : null;
    this.form.setValue({
      q: log.query,
      mode: (log.params['mode'] as SearchMode) ?? 'frase',
      bookId: this.books().some((b) => b.id === bookId) ? bookId : null,
    });
    this.search();
  }

  protected clearHistory(): void {
    this.api.clearHistory().subscribe(() => this.history.set([]));
  }

  protected segments(occurrence: Occurrence): Segment[] {
    const out: Segment[] = [];
    let cursor = 0;
    for (const { start, end } of [...occurrence.highlights].sort((a, b) => a.start - b.start)) {
      if (start > cursor) out.push({ text: occurrence.excerpt.slice(cursor, start), hit: false });
      out.push({ text: occurrence.excerpt.slice(start, end), hit: true });
      cursor = end;
    }
    if (cursor < occurrence.excerpt.length) out.push({ text: occurrence.excerpt.slice(cursor), hit: false });
    return out;
  }

  /** Trecho como está no documento, com [...] onde o recorte suprime texto. */
  protected excerptToCopy(occurrence: Occurrence): string {
    return (occurrence.truncated_start ? '[...] ' : '') + occurrence.excerpt + (occurrence.truncated_end ? ' [...]' : '');
  }

  protected suggested(occurrence: Occurrence, field: keyof typeof FIELD_LABELS): boolean {
    return occurrence.unconfirmed.includes(field);
  }

  protected fileUrl(occurrence: Occurrence): string {
    return this.api.fileUrl(occurrence.book_id, occurrence.pdf_page);
  }

  protected fullTitle(occurrence: Occurrence): string {
    return occurrence.subtitle ? `${occurrence.title}: ${occurrence.subtitle}` : occurrence.title;
  }

  protected bookTitle(book: Book): string {
    return book.title ?? book.original_filename;
  }

  private fetch(offset: number): void {
    const { q, mode, bookId } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set(null);
    this.api.search(q.trim(), mode, bookId, PAGE_SIZE, offset).subscribe({
      next: (response) => {
        this.result.set(response);
        this.occurrences.update((list) => [...list, ...response.occurrences]);
        this.loading.set(false);
        if (offset === 0) this.loadHistory();
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private loadHistory(): void {
    this.api.history().subscribe({
      next: (logs) => this.history.set(logs.filter((log) => log.kind === 'citacoes').slice(0, 8)),
      error: () => this.history.set([]),
    });
  }
}
