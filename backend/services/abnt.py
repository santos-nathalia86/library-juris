"""Referência (ABNT NBR 6023) e citação direta (ABNT NBR 10520) de livros.

Somente campos confirmados pelo usuário entram na referência e na chamada da
citação. O que falta é sinalizado com as expressões usuais ([S. l.], [s. n.],
[s. d.]) e listado em `missing`; valores apenas sugeridos pela extração
automática ficam de fora e são listados em `unconfirmed`.

A chamada segue a NBR 10520:2023: sobrenome só com a inicial maiúscula, mesmo
entre parênteses — (Silva, 2020, p. 45).
"""
import re
from collections.abc import Mapping

from models.book import Citation, Reference

_SUFFIXES = {"junior", "júnior", "jr", "jr.", "filho", "neto", "sobrinho", "segundo"}
_PARTICLES = {"de", "da", "do", "das", "dos", "e", "del", "di", "von", "van"}
_REFERENCE_FIELDS = ("author", "title", "subtitle", "edition", "city", "publisher", "year", "isbn")
_OPTIONAL = {"subtitle", "edition", "isbn"}


def _title_case_name(name: str) -> str:
    words = [w.lower() if w.lower() in _PARTICLES else w.capitalize() for w in name.split()]
    return " ".join(words)


_CORPORATE = re.compile(
    r"\(|\b(brasil|conselho|tribunal|minist[eé]rio|secretaria|universidade|instituto|funda[çc][ãa]o|associa[çc][ãa]o"
    r"|ordem|c[âa]mara|senado|centro|comiss[ãa]o|ag[êe]ncia|procuradoria|defensoria|escola|faculdade)\b",
    re.IGNORECASE,
)
# Uma citação direta com mais de três linhas é "longa"; em página A4 isso equivale a cerca de 250 caracteres.
LONG_QUOTE_CHARS = 250


def is_corporate(name: str) -> bool:
    """Autor-entidade (órgão, tribunal, universidade): não se inverte como nome de pessoa."""
    return "," not in name and bool(_CORPORATE.search(name))


def split_author(name: str) -> tuple[str, str]:
    """Separa (sobrenome, prenomes) de um nome de pessoa."""
    name = " ".join(name.split())
    if "," in name:
        surname, given = (p.strip() for p in name.split(",", 1))
        return surname, given
    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    n = 2 if parts[-1].lower() in _SUFFIXES and len(parts) > 2 else 1
    return " ".join(parts[-n:]), " ".join(parts[:-n])


def format_author(name: str) -> str:
    """"Humberto Theodoro Júnior" -> "THEODORO JÚNIOR, Humberto"; entidades vão em maiúsculas."""
    name = " ".join(name.split())
    if is_corporate(name):
        jurisdiction, dot, rest = name.partition(". ")
        return f"{jurisdiction.upper()}. {rest}" if dot else name.upper()
    surname, given = split_author(name)
    if given.isupper():
        given = _title_case_name(given)
    return f"{surname.upper()}, {given}" if given else surname.upper()


def format_authors(value: str) -> str:
    return "; ".join(format_author(a) for a in value.split(";") if a.strip())


def format_edition(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        return f"{int(value)}. ed."
    return _end(value)


def _end(text: str) -> str:
    return text if text.endswith((".", "?", "!")) else text + "."


def build_reference(book: Mapping, printed_page: str | None = None) -> Reference:
    confirmed = set(book["confirmed_fields"])
    values: dict[str, str] = {}
    missing: list[str] = []
    unconfirmed: list[str] = []
    for name in _REFERENCE_FIELDS:
        value = (book.get(name) or "").strip()
        if name in confirmed and value:
            values[name] = value
        elif name not in confirmed and value:
            unconfirmed.append(name)
        elif name not in _OPTIONAL:
            missing.append(name)

    title = values.get("title")
    if "author" in values:
        before = _end(format_authors(values["author"])) + " "
        emphasis = title or "[Título não identificado]"
        head_after = ""
    else:
        # Sem autoria, a entrada é feita pelo título com a primeira palavra em maiúsculas.
        before, emphasis = "", ""
        if title:
            first, _, rest = title.partition(" ")
            head_after = first.upper() + (" " + rest if rest else "")
        else:
            head_after = "[Título não identificado]"

    head = head_after + (f": {values['subtitle']}" if "subtitle" in values else "")
    if head:
        head = _end(head)
    elif not emphasis.endswith((".", "?", "!")):
        head = "."
    parts = [head]
    if "edition" in values:
        parts.append(format_edition(values["edition"]))

    city, publisher = values.get("city"), values.get("publisher")
    if city and publisher:
        imprint = f"{city}: {publisher}"
    elif city:
        imprint = f"{city}: [s. n.]"
    elif publisher:
        imprint = f"[S. l.]: {publisher}"
    else:
        imprint = "[S. l.: s. n.]"
    parts.append(f"{imprint}, {values.get('year', '[s. d.]')}.")

    if printed_page:
        parts.append(f"p. {printed_page}.")
    if "isbn" in values:
        parts.append(f"ISBN {values['isbn']}.")

    after = " ".join(part for part in parts if part)
    if emphasis and not after.startswith((".", ":")):
        after = " " + after
    return Reference(
        before=before,
        emphasis=emphasis,
        after=after,
        text=(before + emphasis + after).strip(),
        missing=missing,
        unconfirmed=unconfirmed,
    )


def build_call(book: Mapping, printed_page: str | None = None) -> tuple[str, list[str]]:
    """Chamada autor-data: (Sobrenome, ano, p. N). Devolve também os avisos sobre o que falta."""
    confirmed = set(book["confirmed_fields"])

    def value(name: str) -> str:
        return (book.get(name) or "").strip() if name in confirmed else ""

    warnings: list[str] = []
    authors = [a.strip() for a in value("author").split(";") if a.strip()]
    if authors:
        names = []
        for author in authors:
            if is_corporate(author):
                names.append(author.partition(". ")[0] if ". " in author else author)
            else:
                surname = split_author(author)[0]
                names.append(_title_case_name(surname) if surname.isupper() else surname)
        entry = f"{names[0]} et al." if len(names) > 3 else "; ".join(names)
    elif value("title"):
        # Sem autoria: primeira palavra do título seguida de supressão.
        first, _, rest = value("title").partition(" ")
        entry = first + (" [...]" if rest else "")
        warnings.append("autor não confirmado: a chamada usa o título")
    else:
        entry = "[autoria não identificada]"
        warnings.append("autor e título não confirmados")

    year = value("year") or "[s. d.]"
    if not value("year"):
        warnings.append("ano não confirmado")
    parts = [entry, year]
    if printed_page:
        parts.append(f"p. {printed_page}")
    else:
        warnings.append("página impressa não identificada: a citação direta exige a página; confira no exemplar")
    return "(" + ", ".join(parts) + ")", warnings


def build_citation(
    book: Mapping, excerpt: str, printed_page: str | None, truncated_start: bool = False, truncated_end: bool = False
) -> Citation:
    """Citação direta: até três linhas entre aspas; mais longa, em bloco recuado e sem aspas."""
    call, warnings = build_call(book, printed_page)
    body = ("[...] " if truncated_start else "") + excerpt.strip() + (" [...]" if truncated_end else "")
    long = len(body) > LONG_QUOTE_CHARS
    if long:
        text = f"{body} {call}."
    else:
        # Aspas que já existem no trecho passam a aspas simples.
        inner = re.sub(r"[\"“”]", "'", body)
        text = f"\"{inner}\" {call}."
    return Citation(text=text, call=call, long=long, warnings=warnings)


def catalog_reference(
    title: str | None, authors: list[str], year: str | None, publisher: str | None, isbn: str | None = None,
    subtitle: str | None = None,
) -> Reference:
    """Referência a partir de um registro de acervo on-line, cujos dados não foram conferidos no exemplar."""
    if title and not subtitle and ": " in title:
        title, subtitle = (part.strip() for part in title.split(": ", 1))
    book = {
        "author": "; ".join(authors) or None, "title": title, "subtitle": subtitle, "year": year,
        "publisher": publisher, "isbn": isbn, "edition": None, "city": None,
        "confirmed_fields": list(_REFERENCE_FIELDS),
    }
    return build_reference(book)
