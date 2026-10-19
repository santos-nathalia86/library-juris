import sqlite3

import httpx

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from core.config import Settings, get_settings
from core.database import get_db
from models.book import Book, BookDetail, BookUpdate, ImportResult, Reference, Suggestion
from models.online import UrlImport
from repositories.book_repository import BookRepository
from repositories.page_repository import PageRepository
from services import storage_service
from services.abnt import build_reference
from services.http_client import get_http_client
from services.library_service import DuplicateBook, LibraryService, to_detail
from services.remote_download import DOWNLOAD_TIMEOUT, RemoteDownload, filename_from_url
from services.storage_service import UploadError

router = APIRouter(prefix="/api/books", tags=["biblioteca"])


def get_library(conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> LibraryService:
    return LibraryService(conn, settings)


def _require(library: LibraryService, book_id: int) -> dict:
    book = library.books.get(book_id)
    if book is None:
        raise HTTPException(404, "Livro não encontrado.")
    return book


@router.get("", response_model=list[Book])
def list_books(library: LibraryService = Depends(get_library)):
    return library.books.list()


@router.post("", response_model=ImportResult, status_code=201)
def import_book(file: UploadFile = File(...), library: LibraryService = Depends(get_library)):
    try:
        return library.import_pdf(file.file, file.filename, file.content_type)
    except UploadError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    except DuplicateBook as exc:
        raise HTTPException(
            409, {"message": "Este documento já está na biblioteca.", "book_id": exc.book_id}
        ) from exc


@router.post("/import-url", response_model=ImportResult, status_code=201)
def import_book_from_url(
    payload: UrlImport,
    library: LibraryService = Depends(get_library),
    client: httpx.Client = Depends(get_http_client),
):
    """Baixa um PDF de acesso aberto indicado por um acervo on-line e o importa como os demais."""
    origin = f"registro do acervo {payload.source}"
    values = {
        "title": payload.title,
        "author": "; ".join(payload.authors) or None,
        "year": payload.year,
        "publisher": payload.publisher,
    }
    catalog = {name: Suggestion(value=value, source=origin) for name, value in values.items() if value}
    client.timeout = httpx.Timeout(DOWNLOAD_TIMEOUT)
    try:
        with RemoteDownload(client, payload.url) as stream:
            return library.import_pdf(
                stream, filename_from_url(payload.url, payload.title), "application/pdf",
                catalog=catalog, source_url=payload.landing_url or payload.url,
            )
    except UploadError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    except DuplicateBook as exc:
        raise HTTPException(
            409, {"message": "Este documento já está na biblioteca.", "book_id": exc.book_id}
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "A transferência do PDF foi interrompida.") from exc


@router.get("/{book_id}", response_model=BookDetail)
def get_book(book_id: int, library: LibraryService = Depends(get_library)):
    return to_detail(_require(library, book_id))


@router.put("/{book_id}", response_model=BookDetail)
def update_book(book_id: int, payload: BookUpdate, library: LibraryService = Depends(get_library)):
    updated = library.update(book_id, payload)
    if updated is None:
        raise HTTPException(404, "Livro não encontrado.")
    return updated


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, library: LibraryService = Depends(get_library)):
    if not library.delete(book_id):
        raise HTTPException(404, "Livro não encontrado.")


@router.get("/{book_id}/reference", response_model=Reference)
def get_reference(
    book_id: int,
    printed_page: str | None = Query(default=None, max_length=12, pattern=r"^[0-9ivxlcIVXLC]+$"),
    library: LibraryService = Depends(get_library),
):
    return build_reference(_require(library, book_id), printed_page)


@router.get("/{book_id}/pagination")
def get_pagination_summary(book_id: int, library: LibraryService = Depends(get_library)) -> dict[str, int]:
    """Quantas páginas tiveram a paginação impressa identificada, e por qual meio."""
    _require(library, book_id)
    return PageRepository(library.conn).labeling_summary(book_id)


@router.get("/{book_id}/file")
def get_file(book_id: int, library: LibraryService = Depends(get_library)):
    book = _require(library, book_id)
    path = storage_service.pdf_path(library.settings, book["stored_filename"])
    if not path.is_file():
        raise HTTPException(404, "O arquivo PDF não está mais no armazenamento local.")
    return FileResponse(
        path, media_type="application/pdf", filename=book["original_filename"], content_disposition_type="inline"
    )
