import { Component, OnInit, computed, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService, errorMessage } from '../core/api.service';
import { BIBLIO_FIELDS, BiblioField, BookDetail, FIELD_LABELS, LookupCandidate, LookupResponse } from '../core/models';
import { ReferenceView } from '../shared/reference-view';

type FieldState = 'confirmed' | 'suggested' | 'missing' | 'empty';

const HINTS: Partial<Record<BiblioField, string>> = {
  author: 'Nome completo. Separe vários autores com ponto e vírgula.',
  edition: 'Apenas o número (ex.: 3) ou o texto como consta na obra.',
  year: 'Ano da edição consultada, com quatro dígitos.',
  city: 'Cidade da editora, usada na referência ABNT.',
};

@Component({
  selector: 'app-book-detail-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, ReferenceView],
  templateUrl: './book-detail.html',
})
export class BookDetailPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder);

  /** Parâmetro `:id` da rota. */
  readonly id = input.required<string>();

  protected readonly fields = BIBLIO_FIELDS;
  protected readonly labels = FIELD_LABELS;
  protected readonly hints = HINTS;

  protected readonly book = signal<BookDetail | null>(null);
  protected readonly pagination = signal<Record<string, number>>({});
  protected readonly warnings = signal<string[]>(history.state?.warnings ?? []);
  protected readonly error = signal<string | null>(null);
  protected readonly saving = signal(false);
  protected readonly saved = signal(false);
  protected readonly lookup = signal<LookupResponse | null>(null);
  protected readonly lookingUp = signal(false);

  protected readonly form = this.fb.nonNullable.group({
    author: ['', Validators.maxLength(500)],
    title: ['', Validators.maxLength(500)],
    subtitle: ['', Validators.maxLength(500)],
    edition: ['', Validators.maxLength(60)],
    city: ['', Validators.maxLength(120)],
    publisher: ['', Validators.maxLength(200)],
    year: ['', Validators.pattern(/^\d{4}$/)],
    isbn: ['', Validators.maxLength(20)],
  });

  protected readonly pendingCount = computed(() => {
    const book = this.book();
    return book ? this.fields.filter((f) => this.state(f) === 'suggested').length : 0;
  });

  protected readonly paginationText = computed(() => {
    const counts = this.pagination();
    const book = this.book();
    if (!book) return '';
    const printed = counts['impressa'] ?? 0;
    const inferred = counts['inferida'] ?? 0;
    const labelled = counts['rotulo_pdf'] ?? 0;
    if (printed + inferred + labelled === 0) {
      return 'Paginação impressa não identificada: as pesquisas mostrarão apenas a página do arquivo PDF.';
    }
    const parts = [`${printed} de ${book.page_count} páginas com o número impresso identificado`];
    if (inferred) parts.push(`${inferred} deduzida(s) pela sequência das páginas vizinhas`);
    if (labelled) parts.push(`${labelled} apenas com o rótulo informado pelo PDF`);
    return parts.join('; ') + '.';
  });

  ngOnInit(): void {
    const id = Number(this.id());
    this.api.getBook(id).subscribe({
      next: (book) => this.setBook(book),
      error: (err) => this.error.set(errorMessage(err)),
    });
    this.api.paginationSummary(id).subscribe({ next: (p) => this.pagination.set(p), error: () => undefined });
  }

  protected state(field: BiblioField): FieldState {
    const book = this.book();
    if (!book) return 'empty';
    if (book.confirmed_fields.includes(field)) return book[field] ? 'confirmed' : 'missing';
    return book[field] ? 'suggested' : 'empty';
  }

  protected origin(field: BiblioField): string | null {
    const suggestion = this.book()?.suggestions[field];
    if (!suggestion) return null;
    if (suggestion.pdf_page) {
      return `Lido no documento: “${suggestion.value}” (${suggestion.source}, página ${suggestion.pdf_page} do PDF).`;
    }
    return `Sugerido pelo ${suggestion.source}: “${suggestion.value}”.`;
  }

  protected fileUrl(page?: number | null): string {
    return this.api.fileUrl(Number(this.id()), page ?? undefined);
  }

  protected fileSize(bytes: number): string {
    const mb = bytes / 1024 / 1024;
    return mb >= 1 ? `${mb.toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  protected save(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.saved.set(false);
    this.error.set(null);
    this.api.updateBook(Number(this.id()), this.form.getRawValue()).subscribe({
      next: (book) => {
        this.setBook(book);
        this.saving.set(false);
        this.saved.set(true);
        this.warnings.set([]);
      },
      error: (err) => {
        this.error.set(errorMessage(err));
        this.saving.set(false);
      },
    });
  }

  protected searchOnline(): void {
    const { isbn, title } = this.form.getRawValue();
    this.lookingUp.set(true);
    const request = isbn.trim() ? this.api.lookupIsbn(isbn.trim(), title || null) : this.api.lookupLinks(title || null);
    request.subscribe({
      next: (response) => {
        this.lookup.set(response);
        this.lookingUp.set(false);
      },
      error: (err) => {
        this.lookup.set({ candidates: [], errors: [errorMessage(err)], manual_links: [] });
        this.lookingUp.set(false);
      },
    });
  }

  /** Preenche o formulário com o registro externo; nada é gravado até o usuário confirmar. */
  protected apply(candidate: LookupCandidate): void {
    for (const field of this.fields) {
      const value = candidate[field];
      if (value) this.form.controls[field].setValue(value);
    }
    this.form.markAsDirty();
    this.saved.set(false);
  }

  protected candidateSummary(candidate: LookupCandidate): string {
    return this.fields
      .filter((f) => candidate[f])
      .map((f) => `${FIELD_LABELS[f]}: ${candidate[f]}`)
      .join(' · ');
  }

  protected remove(): void {
    const book = this.book();
    if (!book || !confirm(`Excluir "${book.title ?? book.original_filename}" e o PDF armazenado?`)) return;
    this.api.deleteBook(book.id).subscribe({
      next: () => this.router.navigate(['/citacoes']),
      error: (err) => this.error.set(errorMessage(err)),
    });
  }

  private setBook(book: BookDetail): void {
    this.book.set(book);
    this.form.reset(Object.fromEntries(this.fields.map((f) => [f, book[f] ?? ''])) as Record<BiblioField, string>);
  }
}
