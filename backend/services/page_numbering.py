"""Identificação da paginação impressa a partir de cabeçalhos e rodapés.

Um número só é aceito como página impressa quando forma sequência coerente com
páginas vizinhas (mesma diferença em relação à página do PDF). Números isolados
— notas, artigos de lei, "Capítulo 3" — são descartados.
"""
import re
from dataclasses import dataclass

PRINTED = "impressa"
INFERRED = "inferida"
PDF_LABEL = "rotulo_pdf"

_WINDOW = 4
_MIN_SUPPORT = 2
_INFER_REACH = 3

_ARABIC_ONLY = re.compile(r"^\W*(\d{1,4})\W*$")
_ROMAN_ONLY = re.compile(r"^\W*([ivxlc]{1,7}|[IVXLC]{1,7})\W*$")
_ARABIC_START = re.compile(r"^(\d{1,4})\s+\D")
_ARABIC_END = re.compile(r"\D\s+(\d{1,4})$")
_ROMAN_VALID = re.compile(r"^(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}


@dataclass(frozen=True)
class Candidate:
    kind: str  # "arabic", "roman" (minúsculo) ou "ROMAN" (maiúsculo)
    value: int


@dataclass(frozen=True)
class PageLabel:
    label: str
    source: str


def roman_to_int(text: str) -> int | None:
    low = text.lower()
    if not low or not _ROMAN_VALID.match(low):
        return None
    total = 0
    for ch, nxt in zip(low, low[1:] + " "):
        v = _ROMAN_VALUES[ch]
        total += -v if _ROMAN_VALUES.get(nxt, 0) > v else v
    return total


def int_to_roman(number: int) -> str:
    out = []
    for value, sym in ((90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while number >= value:
            out.append(sym)
            number -= value
    return "".join(out)


def candidates_from_lines(lines: list[str]) -> set[Candidate]:
    found: set[Candidate] = set()
    for line in lines:
        line = line.strip()
        if not line or len(line) > 120:
            continue
        if m := _ARABIC_ONLY.match(line):
            found.add(Candidate("arabic", int(m.group(1))))
            continue
        if m := _ROMAN_ONLY.match(line):
            value = roman_to_int(m.group(1))
            if value:
                found.add(Candidate("ROMAN" if m.group(1).isupper() else "roman", value))
            continue
        for pattern in (_ARABIC_START, _ARABIC_END):
            if m := pattern.search(line):
                found.add(Candidate("arabic", int(m.group(1))))
    return {c for c in found if c.value >= 1}


def _render(kind: str, value: int) -> str:
    if kind == "arabic":
        return str(value)
    roman = int_to_roman(value)
    return roman.upper() if kind == "ROMAN" else roman


def resolve_labels(
    page_candidates: list[set[Candidate]], pdf_labels: list[str | None] | None = None
) -> list[PageLabel | None]:
    """Recebe os candidatos de cada página (índice 0 = página 1 do PDF)."""
    n = len(page_candidates)
    keys = [{(c.kind, i + 1 - c.value) for c in cands} for i, cands in enumerate(page_candidates)]
    chosen: list[tuple[str, int] | None] = [None] * n

    for i in range(n):
        best, best_support = None, 0
        for key in keys[i]:
            lo, hi = max(0, i - _WINDOW), min(n, i + _WINDOW + 1)
            support = sum(1 for j in range(lo, hi) if j != i and key in keys[j])
            if support > best_support or (support == best_support and best and key[0] == "arabic"):
                best, best_support = key, support
        if best_support >= _MIN_SUPPORT:
            chosen[i] = best

    labels: list[PageLabel | None] = [None] * n
    for i, key in enumerate(chosen):
        if key:
            labels[i] = PageLabel(_render(key[0], i + 1 - key[1]), PRINTED)

    # Página sem número visível (abertura de capítulo, por exemplo) entre duas
    # páginas próximas com a mesma sequência: o número é deduzido e marcado como tal.
    for i in range(n):
        if chosen[i]:
            continue
        before = next((chosen[j] for j in range(i - 1, max(-1, i - 1 - _INFER_REACH), -1) if chosen[j]), None)
        after = next((chosen[j] for j in range(i + 1, min(n, i + 1 + _INFER_REACH)) if chosen[j]), None)
        if before and before == after and i + 1 - before[1] >= 1:
            labels[i] = PageLabel(_render(before[0], i + 1 - before[1]), INFERRED)

    if pdf_labels:
        for i, pdf_label in enumerate(pdf_labels[:n]):
            if labels[i] is None and pdf_label:
                labels[i] = PageLabel(pdf_label, PDF_LABEL)
    return labels
