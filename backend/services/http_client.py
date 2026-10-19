from collections.abc import Iterator

import httpx
from fastapi import Depends

from core.config import Settings, get_settings

USER_AGENT = "JurisFind/0.1 (pesquisa juridica local)"


def get_http_client(settings: Settings = Depends(get_settings)) -> Iterator[httpx.Client]:
    with httpx.Client(
        timeout=settings.http_timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    ) as client:
        yield client


def describe_error(exc: Exception, source: str) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return f"{source} não respondeu a tempo."
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return f"{source} está sobrecarregada ou limitou as consultas (HTTP 429). Tente novamente em instantes."
        return f"{source} respondeu com erro HTTP {code}."
    if isinstance(exc, httpx.HTTPError):
        return f"Não foi possível conectar a {source}. Verifique a conexão com a internet."
    return f"{source} devolveu uma resposta em formato inesperado."
