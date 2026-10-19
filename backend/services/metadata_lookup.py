"""Consulta opcional de dados bibliográficos em fontes públicas.

Situação verificada em 09/10/2026:
- BrasilAPI (https://brasilapi.com.br/docs#tag/ISBN): API pública e gratuita por
  ISBN, que consulta CBL, Mercado Editorial, Open Library e Google Books.
- Biblioteca Nacional (Sophia): sem API pública; o catálogo recusa clientes
  automatizados (HTTP 403). Apenas link para pesquisa manual.
- CBL: não publica API própria; a busca de ISBN do site é manual. Os registros
  da CBL chegam aqui por meio da BrasilAPI.
"""
from urllib.parse import quote_plus

import httpx

from models.legal import LookupCandidate, LookupResponse, ManualLink
from services.http_client import describe_error
from services.metadata_extractor import isbn_digits, valid_isbn

BRASILAPI_ISBN = "https://brasilapi.com.br/api/isbn/v1/{isbn}"
_PROVIDERS = {
    "cbl": "Câmara Brasileira do Livro",
    "mercado-editorial": "Mercado Editorial",
    "open-library": "Open Library",
    "google-books": "Google Books",
}


def manual_links(title: str | None = None) -> list[ManualLink]:
    links = [
        ManualLink(
            name="Biblioteca Nacional — catálogo",
            url="https://acervo.bn.gov.br/Sophia_web/",
            note="Sem API pública; o catálogo bloqueia consultas automatizadas. Pesquise manualmente.",
        ),
        ManualLink(
            name="CBL — pesquisa de ISBN",
            url="https://www.cblservicos.org.br/isbn/pesquisa/",
            note="A CBL não oferece API própria; a busca no site é manual.",
        ),
    ]
    if title:
        links.append(
            ManualLink(
                name="Open Library — busca por título",
                url=f"https://openlibrary.org/search?q={quote_plus(title)}",
                note="Catálogo aberto; confira se a edição encontrada é a mesma do seu exemplar.",
            )
        )
    return links


def _text(value) -> str | None:
    return str(value).strip() or None if value is not None else None


class MetadataLookup:
    def __init__(self, client: httpx.Client):
        self.client = client

    def by_isbn(self, isbn: str, title: str | None = None) -> LookupResponse:
        links = manual_links(title)
        digits = isbn_digits(isbn)
        if not valid_isbn(digits):
            return LookupResponse(
                candidates=[], errors=["ISBN inválido: confira os dígitos (10 ou 13 algarismos)."], manual_links=links
            )
        try:
            response = self.client.get(BRASILAPI_ISBN.format(isbn=digits))
            if response.status_code == 404:
                return LookupResponse(
                    candidates=[], errors=["ISBN não encontrado nas bases consultadas pela BrasilAPI."],
                    manual_links=links,
                )
            response.raise_for_status()
            data = response.json()
            authors = data.get("authors") or []
            provider = _PROVIDERS.get(data.get("provider"), data.get("provider") or "fonte não informada")
            candidate = LookupCandidate(
                source=f"BrasilAPI — {provider}",
                author="; ".join(a.strip() for a in authors if a and a.strip()) or None,
                title=_text(data.get("title")),
                subtitle=_text(data.get("subtitle")),
                year=_text(data.get("year")),
                publisher=_text(data.get("publisher")),
                city=_text(data.get("location")),
                isbn=_text(data.get("isbn")) or digits,
            )
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            return LookupResponse(candidates=[], errors=[describe_error(exc, "A BrasilAPI")], manual_links=links)
        return LookupResponse(candidates=[candidate], errors=[], manual_links=links)
