"""Leitura do PDF com PyMuPDF: texto por página, margens, sumário e páginas iniciais."""
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from core.text import clean_page_text
from services.page_numbering import PRINTED, PageLabel, candidates_from_lines, resolve_labels

_MARGIN = 0.12
_FRONT_PAGES = 12
_BACK_PAGES = 4
_CHAPTER_LINE = re.compile(
    r"^(cap[ií]tulo|t[ií]tulo|parte|livro|se[cç][aã]o)\s+([0-9]{1,3}|[ivxlc]{1,7})\b[\s.:–—-]*(.*)$",
    re.IGNORECASE,
)
_TOC_NOISE = re.compile(r"\s*(figura|tabela|gr[áa]fico|quadro)\b", re.IGNORECASE)
_TRAILING_PAGE = re.compile(r"[\s.]+\d{1,4}$")


class PdfError(Exception):
    """PDF ilegível, corrompido ou protegido por senha."""


@dataclass
class TextLine:
    text: str
    size: float


@dataclass
class FrontPage:
    pdf_page: int
    text: str
    lines: list[TextLine]


@dataclass
class ExtractedPage:
    pdf_page: int
    text: str
    label: PageLabel | None = None
    chapter: str | None = None


@dataclass
class ExtractedDocument:
    pages: list[ExtractedPage]
    front_pages: list[FrontPage]
    pdf_metadata: dict[str, str] = field(default_factory=dict)

    @property
    def text_page_count(self) -> int:
        return sum(1 for p in self.pages if p.text)


def _margin_lines(page: pymupdf.Page, raw: str) -> list[str]:
    height = page.rect.height
    lines: list[str] = []
    for block in page.get_text("blocks"):
        if block[6] != 0:
            continue
        center = (block[1] + block[3]) / 2
        if center < height * _MARGIN or center > height * (1 - _MARGIN):
            lines.extend(block[4].splitlines())
    body = [ln for ln in raw.splitlines() if ln.strip()]
    return lines + body[:2] + body[-2:]


def _front_page(page: pymupdf.Page, number: int, raw: str) -> FrontPage:
    lines: list[TextLine] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s["text"].strip()]
            if spans:
                text = " ".join("".join(s["text"] for s in spans).split())
                lines.append(TextLine(text, max(s["size"] for s in spans)))
    return FrontPage(number, raw, lines)


def _chapters_from_toc(toc: list, page_count: int) -> list[str | None]:
    chapters: list[str | None] = [None] * page_count
    current: dict[int, str] = {}
    entries = sorted(
        (e for e in toc if e[0] <= 2 and e[2] >= 1 and not _TOC_NOISE.match(str(e[1]))), key=lambda e: e[2]
    )
    idx = 0
    for page in range(1, page_count + 1):
        while idx < len(entries) and entries[idx][2] <= page:
            level, title = entries[idx][0], " ".join(str(entries[idx][1]).split())
            current[level] = title
            if level == 1:
                current.pop(2, None)
            idx += 1
        if current:
            chapters[page - 1] = " — ".join(current[k] for k in sorted(current))
    return chapters


def _chapter_heading(raw: str) -> str | None:
    all_lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    # Várias linhas "Capítulo N" na mesma página indicam sumário, não abertura de capítulo.
    if sum(1 for ln in all_lines if _CHAPTER_LINE.match(ln)) >= 3:
        return None
    lines = all_lines[:6]
    for i, line in enumerate(lines):
        if len(line) > 100:
            continue
        m = _CHAPTER_LINE.match(line)
        if not m:
            continue
        heading = f"{m.group(1)} {m.group(2)}"
        rest = _TRAILING_PAGE.sub("", m.group(3)).strip(" .:–—-•·")
        if not rest and i + 1 < len(lines) and len(lines[i + 1]) <= 80 and not lines[i + 1][-1:].isdigit():
            rest = lines[i + 1].strip(" •·")
        return f"{heading} — {rest}" if rest else heading
    return None


def _strip_page_number(text: str, label: str) -> str:
    """Tira do texto o número de página já identificado na borda, para não poluir os trechos."""
    if text.endswith(" " + label):
        return text[: -len(label)].rstrip()
    if text.startswith(label + " "):
        return text[len(label):].lstrip()
    return text


def extract_document(path: Path) -> ExtractedDocument:
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except Exception as exc:  # PyMuPDF levanta tipos diferentes conforme a falha
        raise PdfError("O arquivo não pôde ser aberto como PDF.") from exc
    with doc:
        if doc.needs_pass:
            raise PdfError("O PDF está protegido por senha e não pode ser lido.")
        count = doc.page_count
        if count == 0:
            raise PdfError("O PDF não contém páginas.")

        pages: list[ExtractedPage] = []
        front: list[FrontPage] = []
        candidates = []
        has_labels = bool(doc.get_page_labels())
        pdf_labels: list[str | None] = []
        headings: list[str | None] = []
        for index, page in enumerate(doc):
            number = index + 1
            raw = page.get_text("text", sort=True)
            pages.append(ExtractedPage(number, clean_page_text(raw)))
            candidates.append(candidates_from_lines(_margin_lines(page, raw)))
            pdf_labels.append((page.get_label() or None) if has_labels else None)
            headings.append(_chapter_heading(raw))
            if number <= _FRONT_PAGES or number > count - _BACK_PAGES:
                front.append(_front_page(page, number, raw))

        toc = doc.get_toc(simple=True)
        if toc:
            chapters = _chapters_from_toc(toc, count)
        else:
            chapters, current = [], None
            for heading in headings:
                current = heading or current
                chapters.append(current)

        for page, label, chapter in zip(pages, resolve_labels(candidates, pdf_labels), chapters):
            page.label, page.chapter = label, chapter
            if label and label.source == PRINTED:
                page.text = _strip_page_number(page.text, label.label)

        metadata = {k: v.strip() for k, v in (doc.metadata or {}).items() if isinstance(v, str) and v.strip()}
        return ExtractedDocument(pages, front, metadata)
