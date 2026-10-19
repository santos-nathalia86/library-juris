import httpx
import pytest

from core.config import Settings, get_settings
from main import app
from services.http_client import get_http_client

from services import remote_download
from tests.conftest import upload

REAL_HOST_CHECK = remote_download.host_is_public
BITSTREAM = "https://bdjur.stj.jus.br/server/api/core/bitstreams/abc/content"


def bdjur_item(status="open.access", doc_type="Livro"):
    return {"_embedded": {"indexableObject": {
        "name": "Direito à informação",
        "metadata": {
            "dc.title": [{"value": "Direito à informação: repercussões"}],
            "dc.contributor.author": [{"value": "Barros, João Pedro Leite"}],
            "dc.date.issued": [{"value": "2022-05"}],
            "dc.publisher": [{"value": "Foco"}],
            "dc.type": [{"value": doc_type}],
            "dc.identifier.uri": [{"value": "https://bdjur.stj.jus.br/handle/2011/1"}],
            "dc.identifier.citation": [{"value": "BARROS, João Pedro Leite. Direito à informação. Indaiatuba: Foco, 2022."}],
        },
        "_embedded": {
            "accessStatus": {"status": status},
            "bundles": {"_embedded": {"bundles": [
                {"name": "LICENSE", "_embedded": {"bitstreams": {"_embedded": {"bitstreams": [{"name": "license.txt"}]}}}},
                {"name": "ORIGINAL", "_embedded": {"bitstreams": {"_embedded": {"bitstreams": [
                    {"name": "livro.pdf", "sizeBytes": 1886123, "_links": {"content": {"href": BITSTREAM}}}]}}}},
            ]}},
        },
    }}}


def bdjur_response(*items):
    return httpx.Response(200, json={"_embedded": {"searchResult": {
        "page": {"totalElements": len(items)}, "_embedded": {"objects": list(items)}}}})


@pytest.fixture(autouse=True)
def public_hosts(monkeypatch):
    """Os testes não resolvem DNS: hosts de exemplo contam como públicos, salvo os listados."""
    monkeypatch.setattr(remote_download, "host_is_public", lambda host: host not in ("interno.exemplo",))


def test_bdjur_search(client, external):
    external["bdjur.stj.jus.br/server/api/discover"] = bdjur_response(
        bdjur_item(), bdjur_item("restricted", "Capítulo de livro"), bdjur_item(doc_type="Sumário de livro")
    )
    result = client.get("/api/livros-online", params={"q": "boa-fé objetiva"}).json()
    assert result["total"] == 3 and result["error"] is None
    book, restricted, summary = result["items"]
    assert book["authors"] == ["Barros, João Pedro Leite"] and book["year"] == "2022" and book["publisher"] == "Foco"
    assert book["access"] == "aberto" and book["pdf_url"] == BITSTREAM and book["pdf_size"] == 1886123
    assert book["catalog_citation"].startswith("BARROS, João Pedro Leite.")
    assert book["reference"]["text"] == "BARROS, João Pedro Leite. Direito à informação: repercussões. [S. l.]: Foco, 2022."
    assert restricted["reference"] is None  # capítulo de livro: o modelo de referência de livro não se aplica
    assert restricted["access"] == "restrito" and restricted["pdf_url"] is None and "restrito" in restricted["note"]
    assert "apenas o sumário" in summary["note"]
    assert client.get("/api/search/history").json()[0]["kind"] == "livros_online"
    assert client.get("/api/livros-online", params={"q": "abc", "tipo": "Inexistente"}).status_code == 422


def test_openalex_search_and_failure(client, external):
    external["api.openalex.org"] = httpx.Response(200, json={"meta": {"count": 2}, "results": [
        {"title": "Contratos", "publication_year": 2015, "type": "book",
         "authorships": [{"author": {"display_name": "Eline Teixeira"}}],
         "best_oa_location": {"pdf_url": "https://repo.exemplo/livro.pdf", "license": "cc-by",
                              "landing_page_url": "https://repo.exemplo/1", "source": {"display_name": "Repositório"}}},
        {"title": "Capítulo", "type": "book-chapter", "doi": "https://doi.org/10.1/x", "best_oa_location": None},
    ]})
    first, second = client.get("/api/livros-online", params={"q": "boa-fé", "fonte": "openalex"}).json()["items"]
    assert first["pdf_url"] == "https://repo.exemplo/livro.pdf" and first["license"] == "cc-by"
    assert first["doc_type"] == "Livro" and first["publisher"] == "Repositório"
    assert second["pdf_url"] is None and second["landing_url"] == "https://doi.org/10.1/x" and second["note"]

    external["api.openalex.org"] = httpx.Response(429)
    failed = client.get("/api/livros-online", params={"q": "boa-fé", "fonte": "openalex"}).json()
    assert failed["items"] == [] and "429" in failed["error"] and failed["manual_links"]


def test_import_from_url_keeps_origin_and_catalog_as_suggestions(client, external, book_pdf):
    external["bdjur.stj.jus.br/redirect"] = httpx.Response(302, headers={"location": BITSTREAM})
    external[BITSTREAM] = httpx.Response(200, content=book_pdf, headers={"content-type": "application/pdf"})
    payload = {
        "url": "https://bdjur.stj.jus.br/redirect", "source": "BDJur (STJ)",
        "landing_url": "https://bdjur.stj.jus.br/handle/2011/1", "title": "Título do catálogo",
        "authors": ["Teste, Maria Exemplo", "Outro, Autor"], "year": "2020", "publisher": "Foco",
    }
    response = client.post("/api/books/import-url", json=payload)
    assert response.status_code == 201, response.text
    book = response.json()["book"]
    assert book["source_url"] == "https://bdjur.stj.jus.br/handle/2011/1"
    assert book["original_filename"] == "Título do catálogo.pdf"
    assert book["confirmed_fields"] == []
    # A ficha catalográfica do próprio PDF prevalece; o catálogo não a sobrescreve.
    assert book["title"] == "Manual de direito fictício" and book["year"] == "2021"
    assert book["suggestions"]["title"]["source"] == "ficha catalográfica"
    # Mesmo documento enviado depois pelo formulário é reconhecido como repetido.
    assert upload(client, book_pdf).status_code == 409
    assert client.get("/api/search", params={"q": "nexo de causalidade"}).json()["total_pages"] == 1


def test_catalog_fills_what_the_pdf_does_not_say(client, external):
    from tests.conftest import build_book_pdf

    external[BITSTREAM] = httpx.Response(200, content=build_book_pdf(with_cip=False))
    payload = {"url": BITSTREAM, "source": "BDJur (STJ)", "title": "Título do catálogo", "year": "2020"}
    book = client.post("/api/books/import-url", json=payload).json()["book"]
    assert book["title"] == "Título do catálogo" and book["year"] == "2020"
    assert book["suggestions"]["year"] == {"value": "2020", "source": "registro do acervo BDJur (STJ)", "pdf_page": None}
    assert book["confirmed_fields"] == [] and "year" in book["reference"]["unconfirmed"]


def test_import_from_url_refusals(client, external, settings):
    def post(url):
        return client.post("/api/books/import-url", json={"url": url})

    assert post("http://bdjur.stj.jus.br/arquivo.pdf").status_code == 422
    assert post("https://interno.exemplo/arquivo.pdf").status_code == 400
    assert post("https://usuario:senha@repo.exemplo/arquivo.pdf").status_code == 400
    external["repo.exemplo/para-dentro"] = httpx.Response(302, headers={"location": "https://interno.exemplo/x.pdf"})
    assert post("https://repo.exemplo/para-dentro").status_code == 400
    external["repo.exemplo/restrito"] = httpx.Response(401)
    assert post("https://repo.exemplo/restrito").status_code == 403
    external["repo.exemplo/pagina"] = httpx.Response(200, text="<html>Baixe aqui</html>")
    assert post("https://repo.exemplo/pagina").status_code == 415
    external["repo.exemplo/grande"] = httpx.Response(200, content=b"%PDF-1.7\n" + b"0" * (3 * 1024 * 1024))
    assert post("https://repo.exemplo/grande").status_code == 413
    assert post("https://repo.exemplo/inexistente").status_code == 502
    assert list(settings.pdf_dir.iterdir()) == []


def test_private_addresses_are_not_public():
    assert not REAL_HOST_CHECK("127.0.0.1") and not REAL_HOST_CHECK("10.0.0.5")
    assert not REAL_HOST_CHECK("localhost") and not REAL_HOST_CHECK("169.254.169.254")


def test_google_books_snippet_has_no_page_and_no_download(client, external):
    seen = {}

    def volumes(request):
        seen.update(request.url.params)
        return httpx.Response(200, json={"totalItems": 1, "items": [{
            "volumeInfo": {
                "title": "Curso de direito civil", "subtitle": "contratos", "authors": ["Fulana de Tal"],
                "publisher": "Editora X", "publishedDate": "2019-03-01", "previewLink": "https://books.google/x",
                "industryIdentifiers": [{"type": "ISBN_10", "identifier": "853330227X"},
                                        {"type": "ISBN_13", "identifier": "9788533302273"}],
            },
            "accessInfo": {"viewability": "PARTIAL", "publicDomain": False, "pdf": {"isAvailable": True}},
            "searchInfo": {"textSnippet": "A <b>boa-f&eacute; objetiva</b> imp&otilde;e&nbsp;deveres anexos"},
        }]})

    app.dependency_overrides[get_http_client] = lambda: httpx.Client(transport=httpx.MockTransport(volumes))
    result = client.get("/api/livros-online", params={"q": "boa-fé objetiva", "fonte": "google", "pagina": 2}).json()
    assert seen["key"] == "chave-de-teste" and seen["startIndex"] == "10"
    item = result["items"][0]
    assert item["title"] == "Curso de direito civil: contratos" and item["year"] == "2019"
    assert item["snippet"] == "A boa-fé objetiva impõe deveres anexos"
    assert item["isbn"] == "9788533302273" and item["pdf_url"] is None
    assert item["note"] == "Visualização parcial no Google Livros."
    assert item["reference"]["text"] == (
        "TAL, Fulana de. Curso de direito civil: contratos. [S. l.]: Editora X, 2019. ISBN 9788533302273."
    )
    assert "chave-de-teste" not in str(result)


def test_google_books_rejected_key_and_missing_key(client, external, settings):
    external["googleapis.com"] = httpx.Response(403, json={"error": {"message": "API key not valid"}})
    result = client.get("/api/livros-online", params={"q": "boa-fé", "fonte": "google"}).json()
    assert result["items"] == [] and "recusou a chave" in result["error"]
    assert client.get("/api/livros-online/fontes").json() == {"bdjur": True, "openalex": True, "google": True}

    app.dependency_overrides[get_settings] = lambda: Settings(storage_dir=settings.storage_dir, google_books_api_key="")
    assert client.get("/api/livros-online/fontes").json()["google"] is False
    assert client.get("/api/livros-online", params={"q": "boa-fé", "fonte": "google"}).status_code == 400


def test_law_only_filter_is_on_by_default_and_can_be_turned_off(client, external):
    sent = []

    def capture(request):
        sent.append(dict(request.url.params))
        return httpx.Response(200, json={"totalItems": 0, "meta": {"count": 0}, "results": []})

    app.dependency_overrides[get_http_client] = lambda: httpx.Client(transport=httpx.MockTransport(capture))
    for fonte in ("google", "openalex"):
        on = client.get("/api/livros-online", params={"q": "diário de um banana", "fonte": fonte}).json()
        off = client.get("/api/livros-online", params={"q": "diário de um banana", "fonte": fonte, "so_direito": "false"}).json()
        assert "apenas Direito" in on["source_note"] and "apenas Direito" not in off["source_note"]
        assert on["query"] == off["query"] == "diário de um banana"
    assert sent[0]["q"] == "diário de um banana subject:law" and sent[1]["q"] == "diário de um banana"
    assert sent[2]["filter"].endswith(",primary_topic.subfield.id:3308")
    assert "subfield" not in sent[3]["filter"]
