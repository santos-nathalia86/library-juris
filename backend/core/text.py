"""Utilitários de texto usados na extração e na busca."""
import re
import unicodedata

_HYPHEN_BREAK = re.compile(r"(?<=[^\W\d_])-\s*\n\s*(?=[a-zà-ÿ])")
_WHITESPACE = re.compile(r"\s+")


def clean_page_text(raw: str) -> str:
    """Une palavras hifenizadas na quebra de linha e reduz espaços em branco.

    Uma palavra composta partida exatamente no hífen ("decreto-\\nlei") também é
    unida; o PDF original permanece como fonte para conferência.
    """
    return _WHITESPACE.sub(" ", _HYPHEN_BREAK.sub("", raw)).strip()


def fold_char(ch: str) -> str:
    """Um caractere sem acento e em minúscula, sempre com comprimento 1."""
    base = unicodedata.normalize("NFD", ch)[0].lower()
    return base[0] if base else ch


def fold(text: str) -> str:
    """Normaliza para comparação preservando o comprimento (índices equivalentes)."""
    return "".join(fold_char(c) for c in text)


def tokenize(query: str) -> list[str]:
    return re.findall(r"[^\W_]+", fold(query))
