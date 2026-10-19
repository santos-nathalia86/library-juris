"""Proteção por senha (HTTP Basic) e entrega da interface compilada.

Servem para expor o JurisFind fora do computador, por exemplo por um túnel:
com JURISFIND_ACCESS_PASSWORD definida, nada é respondido sem a senha.
"""
import asyncio
import base64
import binascii
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from core.config import Settings, get_settings

_REALM = 'Basic realm="JurisFind", charset="UTF-8"'
_FAILURE_DELAY = 1.0  # segundos; torna lenta a tentativa de adivinhar a senha


def _settings(app: FastAPI) -> Settings:
    return app.dependency_overrides.get(get_settings, get_settings)()


def _password_from(header: str | None) -> str | None:
    scheme, _, encoded = (header or "").partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    return decoded.partition(":")[2]


def install_access_control(app: FastAPI) -> None:
    @app.middleware("http")
    async def require_password(request: Request, call_next):
        expected = _settings(app).access_password
        if not expected or request.method == "OPTIONS":
            return await call_next(request)
        given = _password_from(request.headers.get("authorization"))
        if given is not None and secrets.compare_digest(given.encode(), expected.encode()):
            return await call_next(request)
        if given is not None:
            await asyncio.sleep(_FAILURE_DELAY)
        return Response("Acesso restrito: informe a senha do JurisFind.", 401, {"WWW-Authenticate": _REALM})


def install_frontend(app: FastAPI) -> None:
    """Entrega o Angular compilado; rotas da interface caem no index.html."""

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        root = _settings(app).frontend_dir
        if path.startswith("api/") or path == "api":
            return JSONResponse({"detail": "Rota não encontrada."}, 404)
        if not (root / "index.html").is_file():
            return JSONResponse(
                {"detail": "Interface não compilada. Rode `npm run build` em frontend/ ou use `npm start`."}, 404
            )
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
