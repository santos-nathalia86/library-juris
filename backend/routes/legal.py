import sqlite3
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from core.config import Settings, get_settings
from core.database import get_db
from models.legal import LegalSearchResponse, LookupResponse
from models.online import OnlineSearchResponse
from repositories.search_log_repository import SearchLogRepository
from services.http_client import get_http_client
from services.jurisprudence_service import COURT_PATTERN, JurisprudenceService
from services.legislation_service import NORM_TYPES, LegislationService
from services.metadata_lookup import MetadataLookup, manual_links
from services.online_books_service import BDJUR_TYPES, OnlineBooksService

router = APIRouter(prefix="/api", tags=["fontes públicas"])


def _log(conn: sqlite3.Connection, kind: str, result: LegalSearchResponse, params: dict) -> None:
    if result.error is None:
        SearchLogRepository(conn).add(kind, result.query, params, result.total or 0)


@router.get("/jurisprudencia", response_model=LegalSearchResponse)
def search_jurisprudence(
    q: str = Query(min_length=3, max_length=200),
    fonte: Literal["tst", "datajud"] = "tst",
    tribunal: str = Query(default="stj", pattern=COURT_PATTERN),
    pagina: int = Query(default=1, ge=1, le=50),
    so_ementa: bool = False,
    client: httpx.Client = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
):
    service = JurisprudenceService(client, settings.datajud_api_key)
    if fonte == "tst":
        result = service.search_tst(q.strip(), pagina, so_ementa)
    else:
        result = service.search_datajud(q.strip(), tribunal, pagina)
    if pagina == 1:
        _log(conn, "jurisprudencia", result, {"fonte": fonte, "tribunal": tribunal if fonte == "datajud" else None})
    return result


@router.get("/livros-online/fontes")
def online_book_sources(settings: Settings = Depends(get_settings)) -> dict[str, bool]:
    """Fontes de livros on-line e se estão habilitadas nesta instalação."""
    return {"bdjur": True, "openalex": True, "google": bool(settings.google_books_api_key)}


@router.get("/livros-online/tipos")
def online_book_types() -> list[str]:
    return list(BDJUR_TYPES)


@router.get("/livros-online", response_model=OnlineSearchResponse)
def search_online_books(
    q: str = Query(min_length=3, max_length=200),
    fonte: Literal["bdjur", "openalex", "google"] = "bdjur",
    tipo: str | None = Query(default=None, max_length=40),
    pagina: int = Query(default=1, ge=1, le=50),
    so_direito: bool = True,
    client: httpx.Client = Depends(get_http_client),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_db),
):
    if tipo and tipo not in BDJUR_TYPES:
        raise HTTPException(422, "Tipo de documento desconhecido.")
    service = OnlineBooksService(client)
    if fonte == "bdjur":
        result = service.search_bdjur(q.strip(), tipo, pagina)
    elif fonte == "openalex":
        result = service.search_openalex(q.strip(), pagina, so_direito)
    elif settings.google_books_api_key:
        result = service.search_google(q.strip(), pagina, settings.google_books_api_key, so_direito)
    else:
        raise HTTPException(
            400, "A fonte Google Livros exige uma chave: defina JURISFIND_GOOGLE_BOOKS_KEY em backend/.env."
        )
    if pagina == 1 and result.error is None:
        SearchLogRepository(conn).add(
            "livros_online", result.query, {"fonte": fonte, "tipo": tipo, "so_direito": so_direito}, result.total or 0
        )
    return result


@router.get("/legislacao/tipos")
def legislation_types() -> dict[str, str]:
    return NORM_TYPES


@router.get("/legislacao", response_model=LegalSearchResponse)
def search_legislation(
    termo: str | None = Query(default=None, max_length=120),
    tipo: str | None = Query(default=None, pattern=r"^[A-Z]{2,4}$"),
    numero: str | None = Query(default=None, pattern=r"^\d{1,6}$"),
    ano: int | None = Query(default=None, ge=1808, le=2100),
    client: httpx.Client = Depends(get_http_client),
    conn: sqlite3.Connection = Depends(get_db),
):
    termo = (termo or "").strip() or None
    if not (numero or ano):
        raise HTTPException(
            422,
            "Informe o número ou o ano da norma. A fonte oficial não pesquisa por palavras isoladas: "
            "as palavras apenas filtram as normas do ano ou número informado.",
        )
    result = LegislationService(client).search(termo, tipo, numero, ano)
    _log(conn, "legislacao", result, {"tipo": tipo, "numero": numero, "ano": ano, "termo": termo})
    return result


@router.get("/metadata/lookup", response_model=LookupResponse)
def lookup_metadata(
    isbn: str = Query(min_length=10, max_length=20),
    title: str | None = Query(default=None, max_length=300),
    client: httpx.Client = Depends(get_http_client),
):
    return MetadataLookup(client).by_isbn(isbn, title)


@router.get("/metadata/links", response_model=LookupResponse)
def lookup_links(title: str | None = Query(default=None, max_length=300)):
    """Fontes para pesquisa manual quando não há ISBN ou conexão."""
    return LookupResponse(candidates=[], errors=[], manual_links=manual_links(title))
