import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse, HttpEventType } from '@angular/common/http';
import { FormControl, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService, errorMessage } from '../core/api.service';
import { Book, NOT_IDENTIFIED } from '../core/models';
import { Icon } from '../shared/icon';

@Component({
  selector: 'app-library-page',
  imports: [ReactiveFormsModule, RouterLink, DatePipe, Icon],
  templateUrl: './library.html',
})
export class LibraryPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  protected readonly books = signal<Book[] | null>(null);
  protected readonly maxMb = signal(200);
  protected readonly progress = signal<number | null>(null);
  protected readonly processing = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly duplicateId = signal<number | null>(null);
  protected readonly notIdentified = NOT_IDENTIFIED;

  protected readonly file = new FormControl<File | null>(null, [Validators.required, (c) => this.validateFile(c.value)]);
  protected readonly authorized = new FormControl(false, { nonNullable: true, validators: Validators.requiredTrue });
  protected readonly form = new FormGroup({ authorized: this.authorized });

  ngOnInit(): void {
    this.api.health().subscribe({ next: (h) => this.maxMb.set(h.max_upload_mb), error: () => undefined });
    this.api.listBooks().subscribe({
      next: (books) => this.books.set(books),
      error: (err) => this.error.set(errorMessage(err)),
    });
  }

  protected pick(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file.setValue(input.files?.[0] ?? null);
    this.file.markAsTouched();
    this.error.set(null);
    this.duplicateId.set(null);
  }

  protected upload(input: HTMLInputElement): void {
    const file = this.file.value;
    if (!file || this.file.invalid || this.authorized.invalid) {
      this.file.markAsTouched();
      this.authorized.markAsTouched();
      return;
    }
    this.error.set(null);
    this.duplicateId.set(null);
    this.progress.set(0);
    this.api.importBook(file).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.progress.set(event.total ? Math.round((100 * event.loaded) / event.total) : null);
          this.processing.set(event.loaded === event.total);
        } else if (event.type === HttpEventType.Response && event.body) {
          this.router.navigate(['/biblioteca', event.body.book.id], { state: { warnings: event.body.warnings } });
        }
      },
      error: (err: HttpErrorResponse) => {
        this.progress.set(null);
        this.processing.set(false);
        this.error.set(errorMessage(err));
        this.duplicateId.set(err.status === 409 ? (err.error?.detail?.book_id ?? null) : null);
        input.value = '';
        this.file.reset();
      },
    });
  }

  protected pending(book: Book): number {
    const fields = ['author', 'title', 'year', 'edition', 'publisher'] as const;
    return fields.filter((f) => !book.confirmed_fields.includes(f)).length;
  }

  protected fileSize(bytes: number): string {
    const mb = bytes / 1024 / 1024;
    return mb >= 1 ? `${mb.toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  private validateFile(file: File | null): ValidationErrors | null {
    if (!file) return null;
    if (!file.name.toLowerCase().endsWith('.pdf')) return { type: true };
    if (file.size > this.maxMb() * 1024 * 1024) return { size: true };
    return null;
  }
}
