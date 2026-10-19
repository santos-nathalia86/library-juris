import pymupdf

from tests.conftest import upload


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "max_upload_mb": 2}


def test_import_suggests_but_does_not_confirm(client, book_pdf, settings):
    response = upload(client, book_pdf, "Manual de Direito.pdf")
    assert response.status_code == 201, response.text
    book = response.json()["book"]
    assert book["title"] == "Manual de direito fictício"
    assert book["author"] == "Maria Exemplo Teste"
    assert book["original_filename"] == "Manual de Direito.pdf"
    assert book["page_count"] == 10 and book["text_page_count"] == 10
    assert book["confirmed_fields"] == []
    assert book["suggestions"]["year"] == {"value": "2021", "source": "ficha catalográfica", "pdf_page": 3}
    # Nada confirmado: a referência não usa as sugestões.
    assert book["reference"]["text"] == "[Título não identificado]. [S. l.: s. n.], [s. d.]."
    assert "author" in book["reference"]["unconfirmed"]
    stored = list(settings.pdf_dir.iterdir())
    assert len(stored) == 1 and stored[0].suffix == ".pdf" and stored[0].read_bytes() == book_pdf


def test_manual_correction_confirms_fields(client, book_pdf):
    book_id = upload(client, book_pdf).json()["book"]["id"]
    payload = {
        "author": "Maria Exemplo Teste", "title": "Manual de direito fictício", "subtitle": "teoria e prática",
        "year": "2021", "edition": "3", "publisher": "Modelo", "city": "São Paulo", "isbn": "978-85-333-0227-3",
    }
    response = client.put(f"/api/books/{book_id}", json=payload)
    assert response.status_code == 200, response.text
    book = response.json()
    assert book["publisher"] == "Modelo"
    assert book["reference"]["text"] == (
        "TESTE, Maria Exemplo. Manual de direito fictício: teoria e prática. 3. ed. "
        "São Paulo: Modelo, 2021. ISBN 978-85-333-0227-3."
    )
    assert book["reference"]["missing"] == [] and book["reference"]["unconfirmed"] == []
    ref = client.get(f"/api/books/{book_id}/reference", params={"printed_page": "4"}).json()
    assert "2021. p. 4. ISBN" in ref["text"]


def test_confirming_an_empty_field_marks_it_missing(client, book_pdf):
    book_id = upload(client, book_pdf).json()["book"]["id"]
    book = client.put(f"/api/books/{book_id}", json={"title": "Manual", "author": "", "year": ""}).json()
    assert book["author"] is None and book["year"] is None
    assert book["reference"]["text"].startswith("MANUAL. ")
    assert {"author", "year"} <= set(book["reference"]["missing"])


def test_invalid_year_is_rejected(client, book_pdf):
    book_id = upload(client, book_pdf).json()["book"]["id"]
    assert client.put(f"/api/books/{book_id}", json={"year": "21"}).status_code == 422


def test_duplicate_is_refused(client, book_pdf, settings):
    first = upload(client, book_pdf).json()["book"]["id"]
    again = upload(client, book_pdf, "outro-nome.pdf")
    assert again.status_code == 409
    assert again.json()["detail"]["book_id"] == first
    assert len(list(settings.pdf_dir.iterdir())) == 1


def test_upload_validation(client, settings):
    assert upload(client, b"%PDF-1.4 x", "notas.txt", "text/plain").status_code == 415
    assert upload(client, b"MZ\x90\x00 executavel", "falso.pdf").status_code == 415
    assert upload(client, b"%PDF-1.7\n" + b"0" * (3 * 1024 * 1024), "grande.pdf").status_code == 413
    assert upload(client, b"%PDF-1.7\nlixo que nao e pdf", "quebrado.pdf").status_code == 422
    assert upload(client, b"", "vazio.pdf").status_code == 400
    assert list(settings.pdf_dir.iterdir()) == []
    assert client.get("/api/books").json() == []


def test_filename_is_sanitized(client, book_pdf):
    book = upload(client, book_pdf, "../../etc/<livro>:*.pdf").json()["book"]
    assert book["original_filename"] == "_livro_.pdf"


def test_scanned_pdf_is_flagged(client):
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    result = upload(client, doc.tobytes(), "digitalizado.pdf").json()
    assert result["book"]["text_page_count"] == 0
    assert result["book"]["title"] is None
    assert any("OCR" in w for w in result["warnings"])


def test_file_download_and_delete(client, book_pdf, settings):
    book_id = upload(client, book_pdf).json()["book"]["id"]
    served = client.get(f"/api/books/{book_id}/file")
    assert served.status_code == 200 and served.content == book_pdf
    assert served.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/books/{book_id}/pagination").json() == {"impressa": 5, "inferida": 1, "nenhuma": 4}
    assert client.delete(f"/api/books/{book_id}").status_code == 204
    assert client.get(f"/api/books/{book_id}").status_code == 404
    assert list(settings.pdf_dir.iterdir()) == []
    assert client.get("/api/search", params={"q": "prescrição"}).json()["total_pages"] == 0
