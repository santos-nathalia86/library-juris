"""Pesquisa de jurisprudência em fontes oficiais.

Situação verificada em 09/10/2026:
- TST: o serviço REST usado pelo próprio site jurisprudencia.tst.jus.br responde
  a consultas diretas e devolve ementas. Não é uma API documentada e pode mudar.
- DataJud (CNJ): API pública documentada. Devolve metadados processuais (classe,
  assuntos, órgão julgador), não o texto das decisões.
- STF, STJ e LexML: respondem com verificação anti-robô; apenas links manuais.
"""
import re
from urllib.parse import quote_plus

import httpx

from models.legal import LegalItem, LegalSearchResponse, ManualLink
from services.http_client import describe_error

TST_URL = "https://jurisprudencia-backend2.tst.jus.br/rest/pesquisa-textual/{start}/{size}"
TST_DOCUMENT_URL = "https://jurisprudencia-backend2.tst.jus.br/rest/documentos/{id}"
DATAJUD_URL = "https://api-publica.datajud.cnj.jus.br/api_publica_{court}/_search"
COURT_PATTERN = r"^(stj|tst|tse|stm|trf[1-6]|tj[a-z]{2,4}|trt(?:[1-9]|1\d|2[0-4]))$"
PAGE_SIZE = 20
# O DataJud costuma levar perto de 20 s para responder.
DATAJUD_TIMEOUT = 60

TST_SOURCE = "TST — Pesquisa de Jurisprudência"
TST_NOTE = (
    "Acórdãos do Tribunal Superior do Trabalho, do mais recente para o mais antigo, obtidos do serviço usado "
    "pelo site oficial (não é uma API documentada; pode deixar de funcionar sem aviso). As palavras são "
    "procuradas no inteiro teor, salvo se a pesquisa for restrita à ementa; use aspas para expressão exata."
)
DATAJUD_SOURCE = "CNJ — DataJud"
DATAJUD_NOTE = (
    "Metadados processuais da API Pública do DataJud. Não contém ementas nem inteiro teor: "
    "use para localizar processos por assunto ou número e consulte a decisão no tribunal."
)


def manual_links(query: str) -> list[ManualLink]:
    q = quote_plus(query)
    blocked = "Bloqueia consultas automatizadas (verificação anti-robô); pesquise no site."
    return [
        ManualLink(
            name="STF — Jurisprudência",
            url=f"https://jurisprudencia.stf.jus.br/pages/search?base=acordaos&queryString={q}&sort=_score&sortBy=desc",
            note=blocked,
        ),
        ManualLink(name="STJ — SCON", url=f"https://scon.stj.jus.br/SCON/pesquisar.jsp?b=ACOR&livre={q}", note=blocked),
        ManualLink(name="LexML", url=f"https://www.lexml.gov.br/busca/search?keyword={q}", note=blocked),
        ManualLink(
            name="CJF — Jurisprudência Unificada",
            url="https://jurisprudencia.cjf.jus.br/unificada/",
            note="Formulário sem API; reúne STF, STJ, TRFs e turmas recursais.",
        ),
    ]


def _date(value: str | None) -> str | None:
    m = re.match(r"(\d{4})-?(\d{2})-?(\d{2})", value or "")
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else None


def _repair(value: str | None) -> str | None:
    """Alguns registros do DataJud chegam com UTF-8 lido como Latin-1 ("PRESIDÃ\x8aNCIA")."""
    try:
        return value.encode("latin-1").decode("utf-8") if value else value
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


class JurisprudenceService:
    def __init__(self, client: httpx.Client, datajud_api_key: str):
        self.client = client
        self.datajud_api_key = datajud_api_key

    def _failure(self, query: str, source: str, note: str, exc: Exception, label: str) -> LegalSearchResponse:
        return LegalSearchResponse(
            query=query, source=source, source_note=note, total=None, items=[],
            error=describe_error(exc, label), manual_links=manual_links(query),
        )

    def search_tst(self, query: str, page: int, summary_only: bool = False) -> LegalSearchResponse:
        start = (page - 1) * PAGE_SIZE + 1
        body = {"e": query, "tipos": ["ACORDAO"]}
        if summary_only:
            body["ementa"] = query
        try:
            response = self.client.post(TST_URL.format(start=start, size=PAGE_SIZE), json=body)
            response.raise_for_status()
            data = response.json()
            items = [self._tst_item(entry.get("registro") or {}) for entry in data.get("registros") or []]
            total = data.get("totalRegistros")
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as exc:
            return self._failure(query, TST_SOURCE, TST_NOTE, exc, "O serviço de jurisprudência do TST")
        return LegalSearchResponse(
            query=query, source=TST_SOURCE, source_note=TST_NOTE, total=total, items=items,
            manual_links=manual_links(query),
        )

    @staticmethod
    def _tst_item(record: dict) -> LegalItem:
        details = {
            "Órgão judicante": (record.get("orgaoJudicante") or {}).get("descricao"),
            "Relator(a)": " ".join((record.get("nomRelatorSemTratamento") or "").split()),
            "Julgamento": _date(record.get("dtaJulgamento")),
            "Publicação": _date(record.get("dtaPublicacao")),
        }
        return LegalItem(
            source="TST",
            title=record.get("numFormatado") or record.get("numero") or "Processo sem número",
            summary=(record.get("ementa") or "").strip() or None,
            details={k: v for k, v in details.items() if v},
            url=TST_DOCUMENT_URL.format(id=record["id"]) if record.get("id") else None,
        )

    def search_datajud(self, query: str, court: str, page: int) -> LegalSearchResponse:
        source = f"{DATAJUD_SOURCE} ({court.upper()})"
        digits = re.sub(r"\D", "", query)
        if len(digits) == 20 and not re.search(r"[A-Za-zÀ-ÿ]", query):
            es_query = {"match": {"numeroProcesso": digits}}
        else:
            es_query = {"match": {"assuntos.nome": {"query": query, "operator": "and"}}}
        body = {
            "size": PAGE_SIZE,
            "from": (page - 1) * PAGE_SIZE,
            "query": es_query,
            "_source": {"excludes": ["movimentos"]},
            "sort": [{"@timestamp": {"order": "desc"}}],
        }
        try:
            response = self.client.post(
                DATAJUD_URL.format(court=court), json=body,
                headers={"Authorization": f"APIKey {self.datajud_api_key}"},
                timeout=DATAJUD_TIMEOUT,
            )
            response.raise_for_status()
            hits = response.json()["hits"]
            items = [self._datajud_item(hit.get("_source") or {}) for hit in hits.get("hits") or []]
            total = (hits.get("total") or {}).get("value")
        except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as exc:
            return self._failure(query, source, DATAJUD_NOTE, exc, "A API do DataJud")
        return LegalSearchResponse(
            query=query, source=source, source_note=DATAJUD_NOTE, total=total, items=items,
            manual_links=manual_links(query),
        )

    @staticmethod
    def _datajud_item(src: dict) -> LegalItem:
        subjects = [s.get("nome") for s in src.get("assuntos") or [] if isinstance(s, dict) and s.get("nome")]
        details = {
            "Tribunal": src.get("tribunal"),
            "Grau": src.get("grau"),
            "Órgão julgador": _repair((src.get("orgaoJulgador") or {}).get("nome")),
            "Ajuizamento": _date(src.get("dataAjuizamento")),
            "Última atualização": _date(src.get("dataHoraUltimaAtualizacao")),
        }
        classe = (src.get("classe") or {}).get("nome") or "Processo"
        return LegalItem(
            source="DataJud",
            title=f"{classe} nº {src.get('numeroProcesso', 'não informado')}",
            summary=("Assuntos: " + "; ".join(subjects)) if subjects else None,
            details={k: v for k, v in details.items() if v},
        )
