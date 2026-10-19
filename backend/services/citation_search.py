"""Pesquisa de citações: o FTS5 localiza as páginas e os trechos são recortados
do texto extraído, de modo que todo resultado aponta para livro e página reais."""
import re
import sqlite3
from dataclasses import dataclass

from core.text import fold, tokenize
from models.book import NOT_IDENTIFIED
from models.search import Highlight, Occurrence, SearchMode, SearchResponse
from repositories.book_repository import BookRepository
from repositories.page_repository import PageRepository
from services.abnt import build_citation, build_reference
from services.page_numbering import PRINTED

_CONTEXT = 240
_MAX_PER_PAGE = 5
_SENTENCE_END = re.compile(r"[.!?…][\"”’)\]]*\s")
_DISPLAY_FIELDS = ("author", "title", "year", "edition", "publisher")


class EmptyQuery(ValueError):
    pass


def build_queries(query: str, mode: SearchMode) -> tuple[str, re.Pattern]:
    """Consulta FTS5 e expressão equivalente sobre o texto normalizado."""
    tokens = tokenize(query)
    if not tokens:
        raise EmptyQuery("Informe ao menos uma palavra para pesquisar.")
    if mode == "frase":
        fts = '"' + " ".join(tokens) + '"'
        pattern = r"(?<![^\W_])" + r"[\W_]+".join(map(re.escape, tokens)) + r"(?![^\W_])"
    else:
        fts = (" AND " if mode == "todas" else " OR ").join(f'"{t}"' for t in tokens)
        pattern = r"(?<![^\W_])(?:" + "|".join(map(re.escape, dict.fromkeys(tokens))) + r")(?![^\W_])"
    return fts, re.compile(pattern)


@dataclass
class Excerpt:
    start: int
    end: int
    spans: list[tuple[int, int]]
    truncated_start: bool
    truncated_end: bool


def _window(text: str, start: int, end: int) -> Excerpt:
    """Amplia o recorte até limites de frase; se não houver, corta em espaço e marca a supressão."""
    lo = max(0, start - _CONTEXT)
    hi = min(len(text), end + _CONTEXT)
    cut_start = cut_end = False
    if lo > 0:
        ends = [m.end() for m in _SENTENCE_END.finditer(text, lo, start)]
        if ends:
            lo = ends[0]
        else:
            lo = text.find(" ", lo, start) + 1 or lo
            cut_start = True
    if hi < len(text):
        last = None
        for last in _SENTENCE_END.finditer(text, end, hi):
            pass
        if last:
            hi = last.end() - 1
        else:
            space = text.rfind(" ", end, hi)
            hi = space if space > end else hi
            cut_end = True
    return Excerpt(lo, hi, [(start, end)], cut_start, cut_end)


def excerpts(text: str, pattern: re.Pattern) -> list[Excerpt]:
    """Recortes em torno das ocorrências de uma página, sem sobreposição."""
    out: list[Excerpt] = []
    for m in pattern.finditer(fold(text)):
        if out and m.end() <= out[-1].end:
            out[-1].spans.append(m.span())
            continue
        if len(out) == _MAX_PER_PAGE:
            break
        item = _window(text, m.start(), m.end())
        if out and item.start < out[-1].end:
            item.start = min(out[-1].end, m.start())
            item.truncated_start = False
        out.append(item)
    return out


class CitationSearch:
    def __init__(self, conn: sqlite3.Connection):
        self.books = BookRepository(conn)
        self.pages = PageRepository(conn)

    def search(self, query: str, mode: SearchMode, book_id: int | None, limit: int, offset: int) -> SearchResponse:
        fts, pattern = build_queries(query, mode)
        total = self.pages.count_matches(fts, book_id)
        rows = self.pages.search(fts, book_id, limit, offset)
        books = self.books.get_many(row["book_id"] for row in rows)

        occurrences: list[Occurrence] = []
        for row in rows:
            book = books[row["book_id"]]
            text = row["text"]
            # Só a paginação efetivamente lida na página entra na referência.
            cited_page = row["printed_page"] if row["printed_page_source"] == PRINTED else None
            reference = build_reference(book, cited_page)
            confirmed = set(book["confirmed_fields"])
            shown = {name: book[name] or NOT_IDENTIFIED for name in _DISPLAY_FIELDS}
            for item in excerpts(text, pattern):
                raw = text[item.start:item.end]
                shift = item.start + len(raw) - len(raw.lstrip())
                occurrences.append(
                    Occurrence(
                        book_id=book["id"],
                        excerpt=raw.strip(),
                        highlights=[Highlight(start=s - shift, end=e - shift) for s, e in item.spans],
                        truncated_start=item.truncated_start,
                        truncated_end=item.truncated_end,
                        pdf_page=row["pdf_page"],
                        printed_page=row["printed_page"],
                        printed_page_source=row["printed_page_source"],
                        chapter=row["chapter"],
                        subtitle=book["subtitle"],
                        isbn=book["isbn"],
                        original_filename=book["original_filename"],
                        imported_at=book["imported_at"],
                        unconfirmed=[n for n in (*_DISPLAY_FIELDS, "subtitle", "isbn") if book[n] and n not in confirmed],
                        reference=reference,
                        citation=build_citation(
                            book, raw.strip(), cited_page, item.truncated_start, item.truncated_end
                        ),
                        **shown,
                    )
                )
        return SearchResponse(
            query=query, mode=mode, total_pages=total, offset=offset, limit=limit, occurrences=occurrences
        )
