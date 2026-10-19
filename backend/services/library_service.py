"""Biblioteca: importação, correção manual e exclusão de livros."""
import sqlite3
from datetime import datetime, timezone
from typing import BinaryIO

from core.config import Settings
from models.book import BIBLIO_FIELDS, BookDetail, BookUpdate, ImportResult, Suggestion
from repositories.book_repository import BookRepository
from repositories.page_repository import PageRepository
from services import storage_service
from services.abnt import build_reference
from services.metadata_extractor import suggest_metadata
from services.pdf_service import PdfError, extract_document
from services.storage_service import UploadError


# O que foi lido na ficha catalográfica do próprio PDF prevalece sobre o registro do acervo.
_READ_IN_DOCUMENT = ("ficha catalográfica", "ISBN impresso")


class DuplicateBook(Exception):
    def __init__(self, book_id: int):
        super().__init__("Documento já importado")
        self.book_id = book_id


def to_detail(book: dict) -> BookDetail:
    return BookDetail(**book, reference=build_reference(book))


class LibraryService:
    def __init__(self, conn: sqlite3.Connection, settings: Settings):
        self.conn = conn
        self.settings = settings
        self.books = BookRepository(conn)
        self.pages = PageRepository(conn)

    def import_pdf(
        self,
        stream: BinaryIO,
        filename: str | None,
        content_type: str | None,
        catalog: dict[str, Suggestion] | None = None,
        source_url: str | None = None,
    ) -> ImportResult:
        """`catalog` traz dados do registro do acervo de origem; entram como sugestões, não como confirmados."""
        display_name = storage_service.sanitize_filename(filename)
        storage_service.validate_declared_type(display_name, content_type)
        upload = storage_service.save_upload(stream, self.settings)
        try:
            if existing := self.books.find_by_sha256(upload.sha256):
                raise DuplicateBook(existing["id"])
            try:
                document = extract_document(upload.path)
            except PdfError as exc:
                raise UploadError(str(exc), 422) from exc

            suggestions = suggest_metadata(document.front_pages, document.pdf_metadata)
            for name, suggestion in (catalog or {}).items():
                if name not in suggestions or suggestions[name].source not in _READ_IN_DOCUMENT:
                    suggestions[name] = suggestion
            data = {name: (suggestions[name].value if name in suggestions else None) for name in BIBLIO_FIELDS}
            data.update(
                suggestions={k: v.model_dump() for k, v in suggestions.items()},
                original_filename=display_name,
                stored_filename=upload.path.name.removesuffix(".part"),
                sha256=upload.sha256,
                size_bytes=upload.size_bytes,
                page_count=len(document.pages),
                text_page_count=document.text_page_count,
                imported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source_url=source_url,
            )
            try:
                book_id = self.books.insert(data)
                self.pages.insert_many(
                    book_id,
                    [
                        {
                            "pdf_page": p.pdf_page,
                            "printed_page": p.label.label if p.label else None,
                            "printed_page_source": p.label.source if p.label else None,
                            "chapter": p.chapter,
                            "text": p.text,
                        }
                        for p in document.pages
                    ],
                )
                storage_service.finalize(upload)
                self.conn.commit()
            except BaseException:
                self.conn.rollback()
                raise
        except BaseException:
            upload.path.unlink(missing_ok=True)
            raise

        warnings = []
        if document.text_page_count == 0:
            warnings.append(
                "O PDF não tem camada de texto (provavelmente é digitalizado). Ele foi guardado, "
                "mas não será encontrado nas pesquisas: o JurisFind não faz OCR."
            )
        elif document.text_page_count < len(document.pages) * 0.5:
            warnings.append(
                f"Apenas {document.text_page_count} de {len(document.pages)} páginas têm texto pesquisável."
            )
        if not any(p.label for p in document.pages):
            warnings.append(
                "Não foi possível identificar a paginação impressa; os resultados mostrarão só a página do PDF."
            )
        labels = {"author": "autor", "title": "título", "year": "ano", "edition": "edição", "publisher": "editora"}
        missing = [label for name, label in labels.items() if not data[name]]
        if missing:
            warnings.append("Dados não identificados automaticamente: " + ", ".join(missing) + ".")
        return ImportResult(book=to_detail(self.books.get(book_id)), warnings=warnings)

    def update(self, book_id: int, payload: BookUpdate) -> BookDetail | None:
        book = self.books.get(book_id)
        if book is None:
            return None
        sent = payload.model_dump(exclude_unset=True)
        values = {name: (value or None) for name, value in sent.items()}
        confirmed = sorted(set(book["confirmed_fields"]) | set(values))
        self.books.update_fields(book_id, values, confirmed)
        self.conn.commit()
        return to_detail(self.books.get(book_id))

    def delete(self, book_id: int) -> bool:
        book = self.books.get(book_id)
        if book is None:
            return False
        self.pages.delete_for_book(book_id)
        self.books.delete(book_id)
        self.conn.commit()
        storage_service.pdf_path(self.settings, book["stored_filename"]).unlink(missing_ok=True)
        return True
