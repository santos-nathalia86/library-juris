from pydantic import BaseModel, ConfigDict, Field

NOT_IDENTIFIED = "Não identificado"

# Campos bibliográficos editáveis pelo usuário.
BIBLIO_FIELDS = ("author", "title", "subtitle", "year", "edition", "publisher", "city", "isbn")


class Suggestion(BaseModel):
    """Valor detectado automaticamente, sempre com a indicação de onde veio."""

    value: str
    source: str
    pdf_page: int | None = None


class Book(BaseModel):
    id: int
    author: str | None
    title: str | None
    subtitle: str | None
    year: str | None
    edition: str | None
    publisher: str | None
    city: str | None
    isbn: str | None
    confirmed_fields: list[str]
    suggestions: dict[str, Suggestion]
    original_filename: str
    size_bytes: int
    page_count: int
    text_page_count: int
    imported_at: str
    source_url: str | None = None


class BookUpdate(BaseModel):
    """Correção manual: todo campo enviado passa a ser considerado confirmado.

    Enviar um campo vazio confirma que o dado não existe ("Não identificado").
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    author: str | None = Field(default=None, max_length=500)
    title: str | None = Field(default=None, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    year: str | None = Field(default=None, pattern=r"^(\d{4})?$")
    edition: str | None = Field(default=None, max_length=60)
    publisher: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    isbn: str | None = Field(default=None, max_length=20)


class Reference(BaseModel):
    """Referência no padrão ABNT NBR 6023, separada para destacar o título."""

    before: str
    emphasis: str
    after: str
    text: str
    missing: list[str]
    unconfirmed: list[str]


class Citation(BaseModel):
    """Citação direta no sistema autor-data da ABNT NBR 10520."""

    text: str
    call: str
    long: bool
    warnings: list[str]


class BookDetail(Book):
    reference: Reference


class ImportResult(BaseModel):
    book: BookDetail
    warnings: list[str]
