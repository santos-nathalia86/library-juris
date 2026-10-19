import { HttpClient, HttpErrorResponse, HttpEvent, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  BiblioField, Book, BookDetail, ImportResult, LegalSearchResponse, LookupResponse, OnlineBook,
  OnlineSearchResponse, Reference, SearchLog, SearchMode, SearchResponse,
} from './models';

type Params = Record<string, string | number | null | undefined>;

function toParams(values: Params): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== '') {
      params = params.set(key, String(value));
    }
  }
  return params;
}

/** Mensagem legível a partir dos erros do FastAPI (`detail` em texto, objeto ou lista de validação). */
export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0 || error.status === 504) {
      return 'Não foi possível falar com a API do JurisFind. Verifique se o backend está em execução.';
    }
    const detail = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((d) => d.msg).join(' ');
    if (detail?.message) return detail.message;
    return `Erro ${error.status} ao consultar a API.`;
  }
  return 'Ocorreu um erro inesperado.';
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = '/api';

  health(): Observable<{ status: string; max_upload_mb: number }> {
    return this.http.get<{ status: string; max_upload_mb: number }>(`${this.base}/health`);
  }

  listBooks(): Observable<Book[]> {
    return this.http.get<Book[]>(`${this.base}/books`);
  }

  getBook(id: number): Observable<BookDetail> {
    return this.http.get<BookDetail>(`${this.base}/books/${id}`);
  }

  importBook(file: File): Observable<HttpEvent<ImportResult>> {
    const body = new FormData();
    body.append('file', file, file.name);
    return this.http.post<ImportResult>(`${this.base}/books`, body, { reportProgress: true, observe: 'events' });
  }

  /** Pede ao backend que baixe e importe o PDF de acesso aberto indicado pelo acervo. */
  importFromUrl(book: OnlineBook): Observable<ImportResult> {
    return this.http.post<ImportResult>(`${this.base}/books/import-url`, {
      url: book.pdf_url,
      source: book.source,
      landing_url: book.landing_url,
      title: book.title.slice(0, 500),
      authors: book.authors.slice(0, 30),
      year: book.year,
      publisher: book.publisher?.slice(0, 200) ?? null,
    });
  }

  onlineBookSources(): Observable<Record<string, boolean>> {
    return this.http.get<Record<string, boolean>>(`${this.base}/livros-online/fontes`);
  }

  onlineBookTypes(): Observable<string[]> {
    return this.http.get<string[]>(`${this.base}/livros-online/tipos`);
  }

  onlineBooks(
    q: string, fonte: string, tipo: string, pagina: number, soDireito: boolean,
  ): Observable<OnlineSearchResponse> {
    const params = toParams({ q, fonte, tipo: fonte === 'bdjur' ? tipo : null, pagina, so_direito: String(soDireito) });
    return this.http.get<OnlineSearchResponse>(`${this.base}/livros-online`, { params });
  }

  updateBook(id: number, values: Partial<Record<BiblioField, string>>): Observable<BookDetail> {
    return this.http.put<BookDetail>(`${this.base}/books/${id}`, values);
  }

  deleteBook(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/books/${id}`);
  }

  getReference(id: number): Observable<Reference> {
    return this.http.get<Reference>(`${this.base}/books/${id}/reference`);
  }

  paginationSummary(id: number): Observable<Record<string, number>> {
    return this.http.get<Record<string, number>>(`${this.base}/books/${id}/pagination`);
  }

  /** Endereço do PDF original, aberto na página indicada. */
  fileUrl(id: number, pdfPage?: number): string {
    return `${this.base}/books/${id}/file` + (pdfPage ? `#page=${pdfPage}` : '');
  }

  search(q: string, mode: SearchMode, bookId: number | null, limit: number, offset: number): Observable<SearchResponse> {
    const params = toParams({ q, mode, book_id: bookId, limit, offset });
    return this.http.get<SearchResponse>(`${this.base}/search`, { params });
  }

  history(limit = 20): Observable<SearchLog[]> {
    return this.http.get<SearchLog[]>(`${this.base}/search/history`, { params: toParams({ limit }) });
  }

  clearHistory(): Observable<void> {
    return this.http.delete<void>(`${this.base}/search/history`);
  }

  jurisprudence(
    q: string, fonte: string, tribunal: string, pagina: number, soEmenta: boolean,
  ): Observable<LegalSearchResponse> {
    const params = toParams({ q, fonte, tribunal, pagina, so_ementa: soEmenta ? 'true' : null });
    return this.http.get<LegalSearchResponse>(`${this.base}/jurisprudencia`, { params });
  }

  legislationTypes(): Observable<Record<string, string>> {
    return this.http.get<Record<string, string>>(`${this.base}/legislacao/tipos`);
  }

  legislation(values: Params): Observable<LegalSearchResponse> {
    return this.http.get<LegalSearchResponse>(`${this.base}/legislacao`, { params: toParams(values) });
  }

  lookupIsbn(isbn: string, title: string | null): Observable<LookupResponse> {
    return this.http.get<LookupResponse>(`${this.base}/metadata/lookup`, { params: toParams({ isbn, title }) });
  }

  lookupLinks(title: string | null): Observable<LookupResponse> {
    return this.http.get<LookupResponse>(`${this.base}/metadata/links`, { params: toParams({ title }) });
  }
}
