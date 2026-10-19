from pydantic import BaseModel


class ManualLink(BaseModel):
    """Fonte sem consulta automatizada viável: o usuário pesquisa no próprio site."""

    name: str
    url: str
    note: str


class LegalItem(BaseModel):
    source: str
    title: str
    summary: str | None = None
    details: dict[str, str] = {}
    url: str | None = None


class LegalSearchResponse(BaseModel):
    query: str
    source: str
    source_note: str
    total: int | None
    items: list[LegalItem]
    error: str | None = None
    manual_links: list[ManualLink]


class LookupCandidate(BaseModel):
    source: str
    author: str | None = None
    title: str | None = None
    subtitle: str | None = None
    year: str | None = None
    edition: str | None = None
    publisher: str | None = None
    city: str | None = None
    isbn: str | None = None


class LookupResponse(BaseModel):
    candidates: list[LookupCandidate]
    errors: list[str]
    manual_links: list[ManualLink]
