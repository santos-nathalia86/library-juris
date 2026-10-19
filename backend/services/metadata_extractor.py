"""Sugestão de dados bibliográficos a partir das páginas iniciais e finais do PDF.

Tudo o que sai daqui é sugestão: cada valor foi lido no próprio documento e
carrega a indicação de onde foi encontrado. O que não aparece no texto não é
preenchido.
"""
import re

from models.book import Suggestion
from services.pdf_service import FrontPage

_CIP_MARKERS = ("dados internacionais de cataloga", "cip-brasil", "catalogação na", "ficha catalográfica")
# Ficha sem título próprio: reconhecida pela menção de responsabilidade (" / ") junto de ISBN, CDD ou CDU.
_CIP_STRUCTURE = re.compile(r"\bISBN\b|\bCD[DU]\b")
_CUTTER = re.compile(r"^[A-Z]\d{2,4}[a-z]?(?=\s|$)")
_MONTH_YEAR = re.compile(
    r"\b(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
    r" de ((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_NOT_A_TITLE = {"sumário", "sumario", "índice", "indice", "prefácio", "apresentação", "agradecimentos", "nota"}
_TITLE_SIZE_RATIO = 1.4
_ISBN = re.compile(r"ISBN(?:[-\s]?1[03])?[\s:]*((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])", re.IGNORECASE)
_EDITION = re.compile(r"\b(\d{1,3})\s*[ªaº.]{0,2}\s*(?:edi[çc][ãa]o|ed\.)", re.IGNORECASE)
_IMPRINT = re.compile(
    r"(?:[–—-]|\.)\s*([A-ZÀ-Ý][^\n:;,.\d]{2,40}?)\s*:\s*([^\n,:;]{2,80}?),\s*(?:c|©)?\s*((?:1[89]|20)\d{2})\b"
)
_COPYRIGHT = re.compile(r"(?:©|\(c\)|copyright)\D{0,40}((?:19|20)\d{2})", re.IGNORECASE)
_CIP_HEADING = re.compile(
    r"^\s*(?:[A-Z]\d{2,4}[a-z]?\s+)?[A-ZÀ-Ý][\wÀ-ÿ'’-]+(?: [\wÀ-ÿ'’-]+){0,3},\s+[A-ZÀ-Ý][\wÀ-ÿ'’. -]+?(?:,\s*\d{4}-?(?:\d{4})?)?\.?\s*$",
    re.MULTILINE,
)
_RESPONSIBILITY = re.compile(r"\s/\s+([^\n/]{3,200}?)\s*(?:\.\s|\.$|\s[–—-]\s|;|\n\s*\n|$)", re.MULTILINE)
_PUBLISHER_LINE = re.compile(
    r"^\s*((?:Editora|Edições|Livraria)\s+[A-ZÀ-Ý][^\n]{1,50}?|[A-ZÀ-Ý][^\n]{1,40}?\s+Editora)\s*$", re.MULTILINE
)
_PERSON_NAME = re.compile(
    r"^(?:[A-ZÀ-Ý][a-zà-ÿ'’]+\.?|[A-ZÀ-Ý]\.)(?: (?:d[aeo]s?|e|[A-ZÀ-Ý][a-zà-ÿ'’]+\.?|[A-ZÀ-Ý]\.)){1,5}$"
)
_PERSON_NAME_CAPS = re.compile(r"^[A-ZÀ-Ý'’]{2,}(?: (?:D[AEO]S?|E|[A-ZÀ-Ý'’.]{2,})){1,5}$")
_ROLE_PREFIX = re.compile(
    r"^(?:coordena[çc][ãa]o|organiza[çc][ãa]o|coordenador(?:es|a|as)?|organizador(?:es|a|as)?|por)\s*(?:de|:)?\s+",
    re.IGNORECASE,
)
_JUNK_META = re.compile(r"\.(pdf|docx?|indd|qxd|p65)$|microsoft word|untitled|sem t[ií]tulo", re.IGNORECASE)
# Editoras jurídicas frequentes; só são sugeridas quando o nome aparece no texto.
_KNOWN_PUBLISHERS = (
    "Saraiva", "Forense", "Atlas", "Revista dos Tribunais", "JusPodivm", "Método", "Malheiros", "Juruá",
    "Lumen Juris", "Del Rey", "Fórum", "Almedina", "Renovar", "Thomson Reuters", "Dialética", "Tirant lo Blanch",
    "Mizuno", "Foco", "Rideel", "Impetus", "LTr", "Quartier Latin", "Noeses", "Livraria do Advogado",
    "Marcial Pons", "Contracorrente", "Manole", "Elsevier", "Martins Fontes",
)


def valid_isbn(digits: str) -> bool:
    if len(digits) == 13 and digits.isdigit():
        return sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits)) % 10 == 0
    if len(digits) == 10 and digits[:9].isdigit() and (digits[9].isdigit() or digits[9] == "X"):
        total = sum((10 - i) * (10 if d == "X" else int(d)) for i, d in enumerate(digits))
        return total % 11 == 0
    return False


def isbn_digits(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", value).upper()


def _squash(text: str) -> str:
    return " ".join(text.split())


def _find_isbn(pages: list[FrontPage]) -> Suggestion | None:
    best: Suggestion | None = None
    for page in pages:
        for m in _ISBN.finditer(page.text):
            digits = isbn_digits(m.group(1))
            if not valid_isbn(digits):
                continue
            found = Suggestion(value=_squash(m.group(1)).replace(" ", "-"), source="ISBN impresso", pdf_page=page.pdf_page)
            if len(digits) == 13:
                return found
            best = best or found
    return best


def _authors_from_responsibility(text: str) -> str | None:
    text = _ROLE_PREFIX.sub("", _squash(text)).strip(" .,;")
    names = [n.strip() for n in re.split(r",\s+|\s+e\s+|;\s*", text) if n.strip()]
    names = [n for n in names if len(n.split()) >= 2 and not any(ch.isdigit() for ch in n)]
    return "; ".join(names) if names else None


def _from_cip(page: FrontPage, out: dict[str, Suggestion]) -> None:
    source = "ficha catalográfica"
    text = page.text

    def put(name: str, value: str) -> None:
        value = _squash(value).strip(" .,;:")
        if value and name not in out:
            out[name] = Suggestion(value=value, source=source, pdf_page=page.pdf_page)

    flat = _squash(text)
    if m := _IMPRINT.search(flat):
        put("city", m.group(1))
        put("publisher", m.group(2))
        put("year", m.group(3))
    if m := _EDITION.search(flat):
        put("edition", str(int(m.group(1))))

    resp = _RESPONSIBILITY.search(text)
    if not resp:
        return
    authors = _authors_from_responsibility(resp.group(1))
    if authors:
        put("author", authors)
    before = text[: resp.start()]
    headings = list(_CIP_HEADING.finditer(before))
    if headings:
        title_block = before[headings[-1].end():]
    else:
        # Sem entrada "Sobrenome, Nome": descarta o código Cutter e a entrada do autor-entidade.
        lines = [_CUTTER.sub("", ln.strip()).strip() for ln in before.rstrip().splitlines()[-3:]]
        while len(lines) > 1 and (not lines[0] or lines[0].lower() == (authors or "").lower()):
            lines.pop(0)
        title_block = "\n".join(lines)
    title_block = _squash(title_block)
    if 3 <= len(title_block) <= 300:
        title, _, subtitle = title_block.partition(" : ")
        put("title", title)
        if subtitle:
            put("subtitle", subtitle)


def _title_page(pages: list[FrontPage], out: dict[str, Suggestion]) -> None:
    """Sem ficha catalográfica: título pelo maior destaque tipográfico das primeiras páginas."""
    sizes = sorted(line.size for page in pages for line in page.lines)
    if not sizes:
        return
    body_size = sizes[len(sizes) // 2]
    best_page, best_size = None, 0.0
    for page in pages[:3]:
        for line in page.lines:
            letters = sum(c.isalpha() for c in line.text)
            if line.size > best_size and letters >= 4 and line.text.lower().strip(" .:") not in _NOT_A_TITLE:
                best_page, best_size = page, line.size
    # Só vale como título o que se destaca claramente do corpo do texto.
    if best_page is None or best_size < body_size * _TITLE_SIZE_RATIO:
        return
    title_lines = [ln.text for ln in best_page.lines if ln.size >= best_size * 0.9]
    title = _squash(" ".join(title_lines))
    source = "capa ou folha de rosto (maior destaque tipográfico)"
    if "title" not in out and 3 <= len(title) <= 200:
        out["title"] = Suggestion(value=title, source=source, pdf_page=best_page.pdf_page)
    if "author" in out:
        return
    for line in best_page.lines:
        text = line.text.strip()
        if text in title_lines or "editora" in text.lower():
            continue
        if _PERSON_NAME.match(text) or _PERSON_NAME_CAPS.match(text):
            out["author"] = Suggestion(
                value=text, source="capa ou folha de rosto (linha com formato de nome)", pdf_page=best_page.pdf_page
            )
            return


def _fallbacks(pages: list[FrontPage], out: dict[str, Suggestion]) -> None:
    head = pages[:8]
    for page in head:
        if "edition" not in out and (m := _EDITION.search(page.text)):
            out["edition"] = Suggestion(value=str(int(m.group(1))), source="indicação de edição", pdf_page=page.pdf_page)
        if "year" not in out and (m := _COPYRIGHT.search(page.text)):
            out["year"] = Suggestion(value=m.group(1), source="aviso de copyright", pdf_page=page.pdf_page)
        if "year" not in out and page.pdf_page <= 4 and (m := _MONTH_YEAR.search(page.text)):
            out["year"] = Suggestion(
                value=m.group(1), source="data impressa nas páginas iniciais", pdf_page=page.pdf_page
            )
        if "publisher" not in out:
            if m := _PUBLISHER_LINE.search(page.text):
                out["publisher"] = Suggestion(
                    value=_squash(m.group(1)), source="linha com nome de editora", pdf_page=page.pdf_page
                )
            else:
                for name in _KNOWN_PUBLISHERS:
                    if re.search(rf"\b{re.escape(name)}\b", page.text, re.IGNORECASE):
                        out["publisher"] = Suggestion(
                            value=name, source="nome de editora citado no texto", pdf_page=page.pdf_page
                        )
                        break


def _from_pdf_metadata(meta: dict[str, str], out: dict[str, Suggestion]) -> None:
    for name, key in (("title", "title"), ("author", "author")):
        value = meta.get(key, "")
        if name not in out and len(value) >= 3 and not _JUNK_META.search(value):
            out[name] = Suggestion(value=value, source="campo de metadados interno do PDF")


def suggest_metadata(front_pages: list[FrontPage], pdf_metadata: dict[str, str]) -> dict[str, Suggestion]:
    out: dict[str, Suggestion] = {}
    if isbn := _find_isbn(front_pages):
        out["isbn"] = isbn
    for page in front_pages:
        low = page.text.lower()
        if any(marker in low for marker in _CIP_MARKERS) or (" / " in page.text and _CIP_STRUCTURE.search(page.text)):
            _from_cip(page, out)
            break
    front = [p for p in front_pages if p.pdf_page <= 12]
    _title_page(front, out)
    _fallbacks(front, out)
    _from_pdf_metadata(pdf_metadata, out)
    return out
