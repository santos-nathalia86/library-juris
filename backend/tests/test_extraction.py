import pymupdf
import pytest

from core.text import clean_page_text
from services.metadata_extractor import suggest_metadata, valid_isbn
from services.pdf_service import PdfError, extract_document
from tests.conftest import build_book_pdf


def extract(tmp_path, **kwargs):
    path = tmp_path / "livro.pdf"
    path.write_bytes(build_book_pdf(**kwargs))
    return extract_document(path)


def test_isbn_checksum():
    assert valid_isbn("9788533302273")
    assert not valid_isbn("9788533302274")
    assert valid_isbn("853330227X") is False


def test_hyphenated_line_break_is_joined():
    assert clean_page_text("deveres de infor-\nmação  às\npartes") == "deveres de informação às partes"


def test_metadata_from_cip(tmp_path):
    doc = extract(tmp_path)
    found = suggest_metadata(doc.front_pages, doc.pdf_metadata)
    values = {k: v.value for k, v in found.items()}
    assert values == {
        "isbn": "978-85-333-0227-3",
        "city": "São Paulo",
        "publisher": "Editora Modelo",
        "year": "2021",
        "edition": "3",
        "author": "Maria Exemplo Teste",
        "title": "Manual de direito fictício",
        "subtitle": "teoria e prática",
    }
    assert found["publisher"].source == "ficha catalográfica" and found["publisher"].pdf_page == 3


def test_without_cip_nothing_is_invented(tmp_path):
    doc = extract(tmp_path, with_cip=False)
    found = suggest_metadata(doc.front_pages, doc.pdf_metadata)
    assert found["title"].value == "MANUAL DE DIREITO FICTÍCIO"
    assert found["author"].value == "Maria Exemplo Teste"
    assert found["edition"].value == "3"
    assert found["publisher"].value == "Editora Modelo"
    assert "year" not in found and "isbn" not in found and "city" not in found


def test_printed_pages_differ_from_pdf_pages(tmp_path):
    doc = extract(tmp_path)
    labels = {p.pdf_page: (p.label.label, p.label.source) if p.label else None for p in doc.pages}
    assert labels[1] is None and labels[4] is None
    assert labels[5] == ("1", "impressa")
    assert labels[7] == ("3", "inferida")
    assert labels[10] == ("6", "impressa")


def test_chapters_follow_headings_not_the_summary(tmp_path):
    doc = extract(tmp_path)
    chapters = {p.pdf_page: p.chapter for p in doc.pages}
    assert chapters[4] is None
    assert chapters[5] == "Capítulo 1 — Responsabilidade civil"
    assert chapters[8] == "Capítulo 2 — Contratos"
    assert chapters[10] == "Capítulo 3 — Prescrição e dano"


def test_no_printed_numbers_means_no_labels(tmp_path):
    doc = extract(tmp_path, with_numbers=False)
    assert all(p.label is None for p in doc.pages)


def test_password_protected_pdf_is_rejected(tmp_path):
    path = tmp_path / "protegido.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "segredo")
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="senha", owner_pw="dono")
    with pytest.raises(PdfError):
        extract_document(path)
