"""Download de PDFs de acervos on-line para o armazenamento local.

O endereço vem de uma resposta de acervo exibida ao usuário, mas ainda assim é
tratado como não confiável: só HTTPS, só hosts públicos (nada de rede local ou
loopback), redirecionamentos conferidos um a um e limite de tamanho aplicado
durante a transferência.
"""
import ipaddress
import socket
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from services.storage_service import UploadError

_MAX_REDIRECTS = 5
_CHUNK = 1024 * 1024
DOWNLOAD_TIMEOUT = 120


def host_is_public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    addresses = {info[4][0] for info in infos}
    return bool(addresses) and all(ipaddress.ip_address(addr).is_global for addr in addresses)


def check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise UploadError("Só é possível importar de endereços https públicos.", 400)
    if not host_is_public(parts.hostname):
        raise UploadError("O endereço informado não é um servidor público da internet.", 400)


def filename_from_url(url: str, fallback: str | None) -> str:
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    if not name.lower().endswith(".pdf"):
        name = (fallback or "documento")[:120] + ".pdf"
    return name


class _ResponseStream:
    """Expõe o corpo da resposta como arquivo (read) para o armazenamento."""

    def __init__(self, response: httpx.Response):
        self._chunks = response.iter_bytes(_CHUNK)
        self._buffer = b""

    def read(self, size: int = -1) -> bytes:
        while size < 0 or len(self._buffer) < size:
            chunk = next(self._chunks, None)
            if chunk is None:
                break
            self._buffer += chunk
        if size < 0:
            data, self._buffer = self._buffer, b""
        else:
            data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data


class RemoteDownload:
    """Uso: `with RemoteDownload(client, url) as stream: ...`"""

    def __init__(self, client: httpx.Client, url: str):
        self.client = client
        self.url = url
        self._response: httpx.Response | None = None

    def __enter__(self) -> _ResponseStream:
        url = self.url
        try:
            for _ in range(_MAX_REDIRECTS + 1):
                check_url(url)
                request = self.client.build_request("GET", url, headers={"Accept": "application/pdf,*/*;q=0.5"})
                response = self.client.send(request, stream=True, follow_redirects=False)
                if response.is_redirect and response.headers.get("location"):
                    response.close()
                    url = urljoin(url, response.headers["location"])
                    continue
                break
            else:
                raise UploadError("O endereço redireciona vezes demais.", 502)
        except httpx.TimeoutException as exc:
            raise UploadError("O acervo não respondeu a tempo.", 504) from exc
        except httpx.HTTPError as exc:
            raise UploadError("Não foi possível conectar ao acervo para baixar o PDF.", 502) from exc

        self._response = response
        if response.status_code in (401, 403):
            self.__exit__()
            raise UploadError("O acervo não libera este arquivo sem login (acesso restrito).", 403)
        if response.status_code != 200:
            self.__exit__()
            raise UploadError(f"O acervo respondeu com erro HTTP {response.status_code} ao baixar o PDF.", 502)
        return _ResponseStream(response)

    def __exit__(self, *exc_info) -> None:
        if self._response is not None:
            self._response.close()
