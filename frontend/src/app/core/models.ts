export type BiblioField = 'author' | 'title' | 'subtitle' | 'year' | 'edition' | 'publisher' | 'city' | 'isbn';

export const BIBLIO_FIELDS: BiblioField[] = [
  'author', 'title', 'subtitle', 'edition', 'city', 'publisher', 'year', 'isbn',
];

export const FIELD_LABELS: Record<BiblioField, string> = {
  author: 'Autor',
  title: 'Título',
  subtitle: 'Subtítulo',
  year: 'Ano',
  edition: 'Edição',
  publisher: 'Editora',
  city: 'Local de publicação',
  isbn: 'ISBN',
};

export const NOT_IDENTIFIED = 'Não identificado';

export interface Suggestion {
  value: string;
  source: string;
  pdf_page: number | null;
}

export interface Reference {
  before: string;
  emphasis: string;
  after: string;
  text: string;
  missing: BiblioField[];
  unconfirmed: BiblioField[];
}

export interface Citation {
  text: string;
  call: string;
  long: boolean;
  warnings: string[];
}

export interface Book extends Record<BiblioField, string | null> {
  id: number;
  confirmed_fields: BiblioField[];
  suggestions: Partial<Record<BiblioField, Suggestion>>;
  original_filename: string;
  size_bytes: number;
  page_count: number;
  text_page_count: number;
  imported_at: string;
  source_url: string | null;
}

export interface BookDetail extends Book {
  reference: Reference;
}

export interface ImportResult {
  book: BookDetail;
  warnings: string[];
}

export type SearchMode = 'frase' | 'todas' | 'qualquer';
export type PageSource = 'impressa' | 'inferida' | 'rotulo_pdf';

export interface Occurrence {
  book_id: number;
  excerpt: string;
  highlights: { start: number; end: number }[];
  truncated_start: boolean;
  truncated_end: boolean;
  pdf_page: number;
  printed_page: string | null;
  printed_page_source: PageSource | null;
  chapter: string | null;
  author: string;
  title: string;
  subtitle: string | null;
  year: string;
  edition: string;
  publisher: string;
  isbn: string | null;
  original_filename: string;
  imported_at: string;
  unconfirmed: BiblioField[];
  reference: Reference;
  citation: Citation;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  total_pages: number;
  offset: number;
  limit: number;
  occurrences: Occurrence[];
}

export interface SearchLog {
  id: number;
  kind: 'citacoes' | 'jurisprudencia' | 'legislacao' | 'livros_online';
  query: string;
  params: Record<string, unknown>;
  total: number;
  created_at: string;
}

export interface ManualLink {
  name: string;
  url: string;
  note: string;
}

export interface LegalItem {
  source: string;
  title: string;
  summary: string | null;
  details: Record<string, string>;
  url: string | null;
}

export interface LegalSearchResponse {
  query: string;
  source: string;
  source_note: string;
  total: number | null;
  items: LegalItem[];
  error: string | null;
  manual_links: ManualLink[];
}

export interface OnlineBook {
  source: string;
  title: string;
  authors: string[];
  year: string | null;
  publisher: string | null;
  doc_type: string | null;
  access: 'aberto' | 'restrito' | 'desconhecido';
  license: string | null;
  landing_url: string | null;
  pdf_url: string | null;
  pdf_size: number | null;
  catalog_citation: string | null;
  reference: Reference | null;
  isbn: string | null;
  snippet: string | null;
  note: string | null;
}

export interface OnlineSearchResponse {
  query: string;
  source: string;
  source_note: string;
  total: number | null;
  page: number;
  page_size: number;
  items: OnlineBook[];
  error: string | null;
  manual_links: ManualLink[];
}

export interface LookupCandidate extends Partial<Record<BiblioField, string | null>> {
  source: string;
}

export interface LookupResponse {
  candidates: LookupCandidate[];
  errors: string[];
  manual_links: ManualLink[];
}
