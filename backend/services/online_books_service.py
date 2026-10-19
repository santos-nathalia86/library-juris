"""Busca de obras jurídicas em acervos on-line de acesso aberto.

Situação verificada em 09/10/2026:
- BDJur (STJ): DSpace 7 com API REST pública. A busca cobre o texto integral dos
  PDFs; os itens de acesso aberto podem ser baixados sem login.
- OpenAlex: API pública com busca em texto integral (`fulltext.search`) de obras
  em acesso aberto. Sem chave, o limite é de cerca de 100 buscas por dia.
- Google Livros: a Books API exige chave pessoal (JURISFIND_GOOGLE_BOOKS_KEY).
  Devolve um trecho curto de obras protegidas, sem página, e não libera o PDF.
- OAPEN e DOAB recusam o acesso à API (HTTP 403), a Biblioteca Digital do Senado responde com verificação anti-robô e
  o Internet Archive não devolveu resultados para termos jurídicos em português.

Nenhuma dessas APIs informa a página em que o termo aparece. Por isso o
resultado aqui é a obra; o trecho e a página só são exibidos depois que o PDF
é importado e passa pela mesma extração dos livros locais.
"""
import html
import re
from urllib.parse import quote_plus

import httpx

from models.legal import ManualLink
from models.online import OnlineBook, OnlineSearchResponse
from services.abnt import catalog_reference
from services.http_client import describe_error

PAGE_SIZE = 10
BDJUR_URL = "https://bdjur.stj.jus.br/server/api/discover/search/objects"
BDJUR_SOURCE = "BDJur — Biblioteca Digital Jurídica do STJ"
BDJUR_NOTE = (
    "Acervo oficial do Superior Tribunal de Justiça. A busca considera o texto integral dos documentos. "
    "Itens do tipo “Sumário de livro” contêm apenas o sumário da obra, não o texto completo."
)
BDJUR_TYPES = ("Livro", "Capítulo de livro", "Artigo", "Trabalho acadêmico", "Sumário de livro")
OPENALEX_URL = "https://api.openalex.org/works"
OPENALEX_SOURCE = "OpenAlex — livros em acesso aberto"
OPENALEX_NOTE = (
    "Catálogo internacional de publicações. São listados livros e capítulos em acesso aberto cujo texto "
    "integral contém os termos. O uso gratuito é limitado a cerca de 100 buscas por dia."
)
_OPENALEX_FIELDS = "id,title,publication_year,type,doi,authorships,best_oa_location,open_access"
_OPENALEX_TYPES = {"book": "Livro", "book-chapter": "Capítulo de livro"}
GOOGLE_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_SOURCE = "Google Livros"
GOOGLE_NOTE = (
    "Inclui obras protegidas por direito autoral. O Google exibe, quando muito, um trecho curto e não informa "
    "a página; o texto completo não pode ser importado. Use para descobrir em que obra procurar e confira "
    "o trecho no exemplar antes de citar."
)
_GOOGLE_VIEW = {
    "ALL_PAGES": "Leitura integral no Google Livros.",
    "PARTIAL": "Visualização parcial no Google Livros.",
    "NO_PAGES": "Sem visualização no Google Livros; apenas dados do catálogo.",
}
_TAGS = re.compile(r"<[^>]+>")
# Filtros de assunto oferecidos pelas próprias fontes (verificados em 09/10/2026).
GOOGLE_LAW_SUBJECT = "subject:law"
OPENALEX_LAW_SUBFIELD = "primary_topic.subfield.id:3308"
LAW_ONLY_NOTE = (
    " Filtro “apenas Direito” ativo: usa a classificação de assunto da própria fonte, que pode deixar de fora "
    "obras jurídicas mal classificadas."
)


def manual_links(query: str) -> list[ManualLink]:
    q = quote_plus(query)
    return [
        ManualLink(
            name="Google Livros",
            url=f"https://www.google.com/books?q={q}",
            note="Mostra trechos de obras protegidas; no site é possível ver a página do trecho quando liberada.",
        ),
        ManualLink(
            name="Biblioteca Digital do Senado Federal",
            url=f"https://www2.senado.leg.br/bdsf/discover?query={q}",
            note="Publicações do Senado em acesso aberto; bloqueia consultas automatizadas.",
        ),
        ManualLink(
            name="SciELO Livros",
            url=f"https://search.livros.scielo.org/search/?q={q}",
            note="Livros acadêmicos em acesso aberto; sem API de busca utilizável.",
        ),
        ManualLink(
            name="OAPEN",
            url=f"https://library.oapen.org/discover?query={q}",
            note="Livros acadêmicos em acesso aberto; a API recusa consultas automatizadas.",
        ),
    ]


def _values(metadata: dict, key: str) -> list[str]:
    return [str(v.get("value")).strip() for v in metadata.get(key) or [] if v.get("value")]


def _first(metadata: dict, key: str) -> str | None:
    values = _values(metadata, key)
    return values[0] if values else None


class OnlineBooksService:
    def __init__(self, client: httpx.Client):
        self.client = client

    def _failure(self, query, source, note, page, exc, label) -> OnlineSearchResponse:
        return OnlineSearchResponse(
            query=query, source=source, source_note=note, total=None, page=page, page_size=PAGE_SIZE, items=[],
            error=describe_error(exc, label), manual_links=manual_links(query),
        )

    def search_bdjur(self, query: str, doc_type: str | None, page: int) -> OnlineSearchResponse:
        params: list[tuple[str, str]] = [
            ("query", query),
            ("dsoType", "ITEM"),
            ("size", str(PAGE_SIZE)),
            ("page", str(page - 1)),
            ("embed", "bundles/bitstreams,accessStatus"),
            ("f.has_content_in_original_bundle", "true,equals"),
        ]
        if doc_type:
            params.append(("f.itemtype", f"{doc_type},equals"))
        try:
            response = self.client.get(BDJUR_URL, params=params)
            response.raise_for_status()
            result = response.json()["_embedded"]["searchResult"]
            objects = (result.get("_embedded") or {}).get("objects") or []
            items = [self._bdjur_item(obj["_embedded"]["indexableObject"]) for obj in objects]
            total = (result.get("page") or {}).get("totalElements")
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as exc:
            return self._failure(query, BDJUR_SOURCE, BDJUR_NOTE, page, exc, "A BDJur")
        return OnlineSearchResponse(
            query=query, source=BDJUR_SOURCE, source_note=BDJUR_NOTE, total=total, page=page, page_size=PAGE_SIZE,
            items=items, manual_links=manual_links(query),
        )

    @staticmethod
    def _bdjur_item(item: dict) -> OnlineBook:
        metadata = item.get("metadata") or {}
        embedded = item.get("_embedded") or {}
        status = (embedded.get("accessStatus") or {}).get("status") or ""
        access = "aberto" if status == "open.access" else "restrito" if status else "desconhecido"

        pdf_url, pdf_size = None, None
        for bundle in ((embedded.get("bundles") or {}).get("_embedded") or {}).get("bundles") or []:
            if bundle.get("name") != "ORIGINAL":
                continue
            files = (((bundle.get("_embedded") or {}).get("bitstreams") or {}).get("_embedded") or {}).get("bitstreams")
            for file in files or []:
                if str(file.get("name", "")).lower().endswith(".pdf"):
                    pdf_url = file["_links"]["content"]["href"]
                    pdf_size = file.get("sizeBytes")
                    break
        doc_type = _first(metadata, "dc.type")
        note = None
        if doc_type == "Sumário de livro":
            note = "Contém apenas o sumário da obra; o texto completo não está disponível no acervo."
        elif access == "restrito":
            note = "Acesso restrito a usuários do STJ; o PDF não pode ser baixado."
        year = (_first(metadata, "dc.date.issued") or "")[:4]
        year = year if year.isdigit() else None
        title = _first(metadata, "dc.title") or item.get("name") or "Sem título"
        authors = _values(metadata, "dc.contributor.author")
        publisher = _first(metadata, "dc.publisher")
        return OnlineBook(
            source="BDJur (STJ)",
            title=title,
            authors=authors,
            year=year,
            publisher=publisher,
            # Só livros: capítulos, artigos e sumários pedem outros modelos de referência.
            reference=catalog_reference(title, authors, year, publisher) if doc_type == "Livro" else None,
            doc_type=doc_type,
            access=access,
            landing_url=_first(metadata, "dc.identifier.uri"),
            pdf_url=pdf_url if access == "aberto" else None,
            pdf_size=pdf_size if access == "aberto" else None,
            catalog_citation=_first(metadata, "dc.identifier.citation"),
            note=note,
        )

    def search_openalex(self, query: str, page: int, law_only: bool = True) -> OnlineSearchResponse:
        note = OPENALEX_NOTE + (LAW_ONLY_NOTE if law_only else "")
        filters = [f"fulltext.search:{query.replace(',', ' ')}", "open_access.is_oa:true", "type:book|book-chapter"]
        if law_only:
            filters.append(OPENALEX_LAW_SUBFIELD)
        params = {
            "filter": ",".join(filters),
            "per-page": PAGE_SIZE,
            "page": page,
            "select": _OPENALEX_FIELDS,
        }
        try:
            response = self.client.get(OPENALEX_URL, params=params)
            response.raise_for_status()
            data = response.json()
            items = [self._openalex_item(work) for work in data.get("results") or []]
            total = (data.get("meta") or {}).get("count")
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as exc:
            return self._failure(query, OPENALEX_SOURCE, note, page, exc, "O OpenAlex")
        return OnlineSearchResponse(
            query=query, source=OPENALEX_SOURCE, source_note=note, total=total, page=page,
            page_size=PAGE_SIZE, items=items, manual_links=manual_links(query),
        )

    @staticmethod
    def _openalex_item(work: dict) -> OnlineBook:
        location = work.get("best_oa_location") or {}
        source = location.get("source") or {}
        pdf_url = location.get("pdf_url")
        if not (isinstance(pdf_url, str) and pdf_url.startswith("https://")):
            pdf_url = None
        authors = [
            (a.get("author") or {}).get("display_name") for a in work.get("authorships") or [] if isinstance(a, dict)
        ]
        authors = [a for a in authors if a]
        title = work.get("title") or "Sem título"
        year = str(work["publication_year"]) if work.get("publication_year") else None
        # O OpenAlex informa o repositório, que nem sempre é a editora: fica fora da referência.
        return OnlineBook(
            source="OpenAlex",
            title=title,
            authors=authors,
            year=year,
            publisher=source.get("host_organization_name") or source.get("display_name"),
            reference=catalog_reference(title, authors, year, None) if work.get("type") == "book" else None,
            doc_type=_OPENALEX_TYPES.get(work.get("type"), work.get("type")),
            access="aberto",
            license=location.get("license"),
            landing_url=location.get("landing_page_url") or work.get("doi") or work.get("id"),
            pdf_url=pdf_url,
            note=None if pdf_url else "A fonte não informa um endereço direto do PDF; baixe na página da obra e importe pela Biblioteca.",
        )

    def search_google(self, query: str, page: int, api_key: str, law_only: bool = True) -> OnlineSearchResponse:
        note = GOOGLE_NOTE + (LAW_ONLY_NOTE if law_only else "")
        params = {
            "q": f"{query} {GOOGLE_LAW_SUBJECT}" if law_only else query,
            "printType": "books",
            "maxResults": PAGE_SIZE,
            "startIndex": (page - 1) * PAGE_SIZE,
            "key": api_key,
        }
        try:
            response = self.client.get(GOOGLE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            items = [self._google_item(volume) for volume in data.get("items") or []]
            total = data.get("totalItems")
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as exc:
            failure = self._failure(query, GOOGLE_SOURCE, note, page, exc, "O Google Livros")
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (400, 403):
                failure.error = (
                    "O Google recusou a chave da Books API. Confira se a API está ativada no projeto e se a "
                    "chave em backend/.env está correta."
                )
            return failure
        return OnlineSearchResponse(
            query=query, source=GOOGLE_SOURCE, source_note=note, total=total, page=page,
            page_size=PAGE_SIZE, items=items, manual_links=manual_links(query),
        )

    @staticmethod
    def _google_item(volume: dict) -> OnlineBook:
        info = volume.get("volumeInfo") or {}
        access = volume.get("accessInfo") or {}
        snippet = (volume.get("searchInfo") or {}).get("textSnippet")
        if snippet:
            snippet = " ".join(html.unescape(_TAGS.sub("", snippet)).split())
        identifiers = {i.get("type"): i.get("identifier") for i in info.get("industryIdentifiers") or []}
        title = info.get("title") or "Sem título"
        if info.get("subtitle"):
            title = f"{title}: {info['subtitle']}"
        year = str(info.get("publishedDate") or "")[:4]
        year = year if year.isdigit() else None
        authors = [a for a in info.get("authors") or [] if a]
        isbn = identifiers.get("ISBN_13") or identifiers.get("ISBN_10")
        return OnlineBook(
            source=GOOGLE_SOURCE,
            title=title,
            authors=authors,
            year=year,
            publisher=info.get("publisher"),
            reference=catalog_reference(
                info.get("title"), authors, year, info.get("publisher"), isbn, info.get("subtitle")
            ),
            doc_type="Livro",
            access="aberto" if access.get("publicDomain") else "desconhecido",
            landing_url=info.get("previewLink") or info.get("infoLink"),
            isbn=isbn,
            snippet=snippet or None,
            note=_GOOGLE_VIEW.get(access.get("viewability")),
        )
