from typing import Literal

from pydantic import BaseModel

from models.book import Citation, Reference

SearchMode = Literal["frase", "todas", "qualquer"]


class Highlight(BaseModel):
    start: int
    end: int


class Occurrence(BaseModel):
    book_id: int
    excerpt: str
    highlights: list[Highlight]
    truncated_start: bool
    truncated_end: bool
    pdf_page: int
    printed_page: str | None
    printed_page_source: str | None
    chapter: str | None
    author: str
    title: str
    subtitle: str | None
    year: str
    edition: str
    publisher: str
    isbn: str | None
    original_filename: str
    imported_at: str
    unconfirmed: list[str]
    reference: Reference
    citation: Citation


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    total_pages: int
    offset: int
    limit: int
    occurrences: list[Occurrence]


class SearchLog(BaseModel):
    id: int
    kind: str
    query: str
    params: dict
    total: int
    created_at: str
