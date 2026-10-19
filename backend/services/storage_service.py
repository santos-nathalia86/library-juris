"""Armazenamento local dos PDFs, com validação de nome, tipo e tamanho."""
import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from core.config import Settings

_CHUNK = 1024 * 1024
_UNSAFE = re.compile(r"[^\w\-. ()]+")


class UploadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class StoredUpload:
    path: Path
    sha256: str
    size_bytes: int


def sanitize_filename(name: str | None) -> str:
    """Nome apenas para exibição; o arquivo é gravado com um nome gerado."""
    name = unicodedata.normalize("NFKC", name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    name = _UNSAFE.sub("_", name).strip(" .")
    if not name:
        name = "documento.pdf"
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, "pdf"
    return f"{stem[:150]}.{ext}"


def validate_declared_type(filename: str, content_type: str | None) -> None:
    if not filename.lower().endswith(".pdf"):
        raise UploadError("Apenas arquivos .pdf são aceitos.", 415)
    if content_type and content_type not in ("application/pdf", "application/x-pdf", "application/octet-stream"):
        raise UploadError("O tipo do arquivo enviado não é PDF.", 415)


def save_upload(stream: BinaryIO, settings: Settings) -> StoredUpload:
    """Grava em arquivo temporário conferindo assinatura %PDF- e limite de tamanho."""
    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    path = settings.pdf_dir / f"{uuid.uuid4().hex}.pdf.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("wb") as out:
            first = True
            while chunk := stream.read(_CHUNK):
                if first:
                    if b"%PDF-" not in chunk[:1024]:
                        raise UploadError("O conteúdo do arquivo não é um PDF válido.", 415)
                    first = False
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise UploadError(f"O arquivo excede o limite de {settings.max_upload_mb} MB.", 413)
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UploadError("O arquivo enviado está vazio.")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return StoredUpload(path, digest.hexdigest(), size)


def finalize(upload: StoredUpload) -> str:
    final = upload.path.with_name(upload.path.name.removesuffix(".part"))
    upload.path.rename(final)
    return final.name


def pdf_path(settings: Settings, stored_filename: str) -> Path:
    return settings.pdf_dir / Path(stored_filename).name
