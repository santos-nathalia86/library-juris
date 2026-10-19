"""Pesquisa de legislação federal nos Dados Abertos do Senado Federal.

API pública e documentada: https://legis.senado.leg.br/dadosabertos/docs/
Ela localiza normas pela identificação (tipo, número, ano) e não faz busca por
palavras; por isso as palavras informadas filtram, aqui, as ementas e os nomes
das normas devolvidas para o tipo/ano escolhidos.
O LexML e o Planalto não oferecem consulta automatizada utilizável (o LexML
responde com verificação anti-robô), por isso entram como links manuais.
"""
from urllib.parse import quote_plus

import httpx

from core.text import tokenize

from models.legal import LegalItem, LegalSearchResponse, ManualLink
from services.http_client import describe_error

SENADO_URL = "https://legis.senado.leg.br/dadosabertos/legislacao/lista"
SOURCE = "Senado Federal — Dados Abertos"
NOTE = (
    "Normas federais catalogadas pelo Senado Federal, localizadas por tipo, número e ano. "
    "As palavras informadas filtram a ementa e o nome das normas encontradas; não há busca no texto integral."
)
MAX_ITEMS = 50
NORM_TYPES = {
    "LEI": "Lei",
    "LCP": "Lei Complementar",
    "DEC": "Decreto",
    "DEL": "Decreto-Lei",
    "MPV": "Medida Provisória",
    "EMC": "Emenda Constitucional",
}


def manual_links(query: str) -> list[ManualLink]:
    q = quote_plus(query)
    return [
        ManualLink(
            name="LexML",
            url=f"https://www.lexml.gov.br/busca/search?keyword={q}",
            note="Rede de informação legislativa e jurídica; bloqueia consultas automatizadas.",
        ),
        ManualLink(
            name="Planalto — Legislação",
            url="https://www.planalto.gov.br/legislacao",
            note="Textos compilados da legislação federal; sem API de pesquisa.",
        ),
        ManualLink(
            name="Normas.leg.br",
            url="https://normas.leg.br/busca",
            note="Portal de normas do Congresso Nacional; pesquisa manual.",
        ),
    ]


class LegislationService:
    def __init__(self, client: httpx.Client):
        self.client = client

    def search(self, term: str | None, norm_type: str | None, number: str | None, year: int | None) -> LegalSearchResponse:
        params = {"tipo": norm_type, "numero": number, "ano": year}
        params = {k: v for k, v in params.items() if v not in (None, "")}
        query = " ".join(str(v) for v in (*params.values(), term) if v)
        links = manual_links(term or query)
        try:
            response = self.client.get(SENADO_URL, params=params, headers={"Accept": "application/json"})
            response.raise_for_status()
            documents = ((response.json().get("ListaDocumento") or {}).get("documentos") or {}).get("documento") or []
            if isinstance(documents, dict):
                documents = [documents]
            words = tokenize(term or "")
            if words:
                documents = [doc for doc in documents if self._matches(doc, words)]
            items = [self._item(doc) for doc in documents[:MAX_ITEMS]]
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            return LegalSearchResponse(
                query=query, source=SOURCE, source_note=NOTE, total=None, items=[],
                error=describe_error(exc, "A API do Senado Federal"), manual_links=links,
            )
        return LegalSearchResponse(
            query=query, source=SOURCE, source_note=NOTE, total=len(documents), items=items, manual_links=links
        )

    @staticmethod
    def _matches(doc: dict, words: list[str]) -> bool:
        haystack = set(tokenize(" ".join(str(doc.get(k) or "") for k in ("ementa", "normaNome", "apelido"))))
        return all(word in haystack for word in words)

    @staticmethod
    def _item(doc: dict) -> LegalItem:
        details = {
            "Tipo": doc.get("descricao"),
            "Assinatura": doc.get("dataassinatura"),
            "Também conhecida como": ", ".join(
                part.strip() for part in (doc.get("apelido") or "").split(",")
                if part.strip() and part.strip() != doc.get("norma")
            ),
        }
        return LegalItem(
            source=SOURCE,
            title=doc.get("normaNome") or doc.get("norma") or "Norma sem identificação",
            summary=doc.get("ementa"),
            details={k: v for k, v in details.items() if v},
            url=f"https://legis.senado.leg.br/norma/{doc['id']}" if doc.get("id") else None,
        )
