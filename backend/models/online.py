from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.book import Reference
from models.legal import ManualLink


class OnlineBook(BaseModel):
    """Obra localizada em acervo on-line. O trecho e a página só existem depois de importar o PDF."""

    source: str
    title: str
    authors: list[str] = []
    year: str | None = None
    publisher: str | None = None
    doc_type: str | None = None
    access: Literal["aberto", "restrito", "desconhecido"] = "desconhecido"
    license: str | None = None
    landing_url: str | None = None
    pdf_url: str | None = None
    pdf_size: int | None = None
    catalog_citation: str | None = None
    # Referência ABNT montada com os dados do registro do acervo (não conferidos no exemplar).
    reference: Reference | None = None
    isbn: str | None = None
    # Trecho devolvido pela própria fonte, sem indicação de página.
    snippet: str | None = None
    note: str | None = None


class OnlineSearchResponse(BaseModel):
    query: str
    source: str
    source_note: str
    total: int | None
    page: int
    page_size: int
    items: list[OnlineBook]
    error: str | None = None
    manual_links: list[ManualLink] = []


class UrlImport(BaseModel):
    """Importação de um PDF de acesso aberto a partir do endereço indicado por um acervo."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    url: str = Field(min_length=12, max_length=2000, pattern=r"^https://")
    source: str = Field(default="acervo on-line", max_length=80)
    landing_url: str | None = Field(default=None, max_length=2000, pattern=r"^https?://")
    title: str | None = Field(default=None, max_length=500)
    authors: list[str] = Field(default=[], max_length=30)
    year: str | None = Field(default=None, pattern=r"^\d{4}$")
    publisher: str | None = Field(default=None, max_length=200)
