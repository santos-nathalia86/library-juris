"""PDFs de teste são gerados com PyMuPDF; nenhum livro real é usado."""
import io

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from core.config import Settings, get_settings
from main import app
from services.http_client import get_http_client

CIP = """Dados Internacionais de Catalogação na Publicação (CIP)

Teste, Maria Exemplo
    Manual de direito fictício : teoria e prática / Maria Exemplo Teste. - 3. ed. - São Paulo : Editora Modelo, 2021.

    ISBN 978-85-333-0227-3

    1. Direito. I. Título.
"""

BODY = {
    1: "A responsabilidade civil pressupõe conduta, dano e nexo de causalidade. "
       "Sem a prova do dano não há dever de indenizar.",
    2: "O princípio da boa-fé objetiva impõe deveres anexos de lealdade e infor-\nmação às partes contratantes.",
    3: "A função social do contrato limita a autonomia privada. A boa-fé objetiva orienta a interpretação.",
    4: "A prescrição extingue a pretensão; a decadência extingue o próprio direito potestativo.",
    5: "O dano moral coletivo prescinde da demonstração de sofrimento individual.",
    6: "Conclui-se que a reparação integral é a regra no direito privado.",
}


def build_book_pdf(with_cip: bool = True, with_numbers: bool = True) -> bytes:
    """Capa, folha de rosto, ficha, sumário e seis páginas de texto numeradas de 1 a 6
    (páginas 5 a 10 do PDF); a página 3 impressa abre capítulo e não traz número."""
    doc = pymupdf.open()

    def page():
        return doc.new_page(width=420, height=595)

    cover = page()
    cover.insert_text((60, 150), "Maria Exemplo Teste", fontsize=14)
    cover.insert_text((60, 220), "MANUAL DE DIREITO FICTÍCIO", fontsize=22)
    cover.insert_text((60, 520), "Editora Modelo", fontsize=12)

    title = page()
    title.insert_text((60, 150), "Maria Exemplo Teste", fontsize=13)
    title.insert_text((60, 220), "MANUAL DE DIREITO FICTÍCIO", fontsize=20)
    title.insert_text((60, 250), "Teoria e prática", fontsize=13)
    title.insert_text((60, 480), "3ª edição", fontsize=11)

    credits = page()
    if with_cip:
        credits.insert_textbox((50, 80, 380, 400), CIP, fontsize=9)
    else:
        credits.insert_text((60, 100), "Todos os direitos reservados.", fontsize=9)

    summary = page()
    summary.insert_text((60, 80), "SUMÁRIO", fontsize=14)
    summary.insert_text((60, 120), "Capítulo 1 - Responsabilidade ..... 1", fontsize=10)
    summary.insert_text((60, 140), "Capítulo 2 - Contratos ..... 3", fontsize=10)
    summary.insert_text((60, 160), "Capítulo 3 - Prescrição ..... 5", fontsize=10)

    chapters = {1: "Capítulo 1", 3: "Capítulo 2", 5: "Capítulo 3"}
    names = {1: "Responsabilidade civil", 3: "Contratos", 5: "Prescrição e dano"}
    for printed, text in BODY.items():
        p = page()
        if printed in chapters:
            p.insert_text((60, 110), chapters[printed], fontsize=13)
            p.insert_text((60, 130), names[printed], fontsize=13)
        p.insert_textbox((60, 180, 370, 480), text, fontsize=11)
        if with_numbers and printed != 3:
            p.insert_text((205, 570), str(printed), fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        storage_dir=tmp_path / "storage", max_upload_mb=2, google_books_api_key="chave-de-teste",
        access_password="", frontend_dir=tmp_path / "frontend",
    )


@pytest.fixture
def external():
    """Respostas simuladas das fontes públicas: os testes não acessam a internet."""
    routes: dict[str, httpx.Response | Exception] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        for fragment, response in routes.items():
            if fragment in str(request.url):
                if isinstance(response, Exception):
                    raise response
                return response
        return httpx.Response(404, json={"message": "não simulado"})

    routes["_handler"] = handler  # type: ignore[assignment]
    return routes


@pytest.fixture
def client(settings, external):
    handler = external.pop("_handler")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_http_client] = lambda: httpx.Client(transport=httpx.MockTransport(handler))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def book_pdf() -> bytes:
    return build_book_pdf()


def upload(client, data: bytes, name: str = "manual.pdf", content_type: str = "application/pdf"):
    return client.post("/api/books", files={"file": (name, io.BytesIO(data), content_type)})
