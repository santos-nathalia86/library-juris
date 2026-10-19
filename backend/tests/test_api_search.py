import pytest

from tests.conftest import upload


@pytest.fixture
def book_id(client, book_pdf):
    return upload(client, book_pdf).json()["book"]["id"]


def search(client, **params):
    response = client.get("/api/search", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def highlighted(occurrence):
    return [occurrence["excerpt"][h["start"]:h["end"]] for h in occurrence["highlights"]]


def test_phrase_search_returns_traceable_occurrence(client, book_id):
    result = search(client, q="nexo de causalidade")
    assert result["total_pages"] == 1
    hit = result["occurrences"][0]
    # Página curta: o trecho é a página inteira, sem o número de página do rodapé.
    assert hit["excerpt"] == (
        "Capítulo 1 Responsabilidade civil A responsabilidade civil pressupõe conduta, dano e nexo de "
        "causalidade. Sem a prova do dano não há dever de indenizar."
    )
    assert not hit["truncated_start"] and not hit["truncated_end"]
    assert highlighted(hit) == ["nexo de causalidade"]
    assert (hit["pdf_page"], hit["printed_page"], hit["printed_page_source"]) == (5, "1", "impressa")
    assert hit["chapter"] == "Capítulo 1 — Responsabilidade civil"
    assert hit["book_id"] == book_id and hit["original_filename"] == "manual.pdf"
    assert hit["author"] == "Maria Exemplo Teste" and "author" in hit["unconfirmed"]
    # Nada confirmado ainda: a chamada não usa as sugestões.
    assert hit["citation"]["call"] == "([autoria não identificada], [s. d.], p. 1)"


def test_citation_in_abnt_format_after_confirming_data(client, book_id):
    client.put(f"/api/books/{book_id}", json={"author": "Maria Exemplo Teste", "title": "Manual", "year": "2021"})
    hit = search(client, q="direito potestativo")["occurrences"][0]
    assert hit["citation"] == {
        "text": "\"A prescrição extingue a pretensão; a decadência extingue o próprio direito potestativo.\" "
                "(Teste, 2021, p. 4).",
        "call": "(Teste, 2021, p. 4)", "long": False, "warnings": [],
    }
    inferred = search(client, q="função social do contrato")["occurrences"][0]
    assert inferred["citation"]["call"] == "(Teste, 2021)"
    assert "página impressa não identificada" in inferred["citation"]["warnings"][0]


def test_search_ignores_accents_case_and_line_hyphenation(client, book_id):
    hit = search(client, q="BOA-FE OBJETIVA impoe")["occurrences"][0]
    assert highlighted(hit) == ["boa-fé objetiva impõe"]
    assert search(client, q="lealdade e informação")["total_pages"] == 1


def test_inferred_page_is_shown_but_not_cited(client, book_id):
    client.put(f"/api/books/{book_id}", json={"title": "Manual", "year": "2021"})
    inferred = search(client, q="função social do contrato")["occurrences"][0]
    assert (inferred["pdf_page"], inferred["printed_page"], inferred["printed_page_source"]) == (7, "3", "inferida")
    assert "p. 3" not in inferred["reference"]["text"]
    printed = search(client, q="direito potestativo")["occurrences"][0]
    assert printed["reference"]["text"] == "MANUAL. [S. l.: s. n.], 2021. p. 4."


def test_modes(client, book_id):
    assert search(client, q="dano prescrição", mode="frase")["total_pages"] == 0
    assert search(client, q="dano decadência", mode="todas")["total_pages"] == 0
    assert search(client, q="dano conduta", mode="todas")["total_pages"] == 1
    any_mode = search(client, q="dano prescrição", mode="qualquer")
    assert {o["pdf_page"] for o in any_mode["occurrences"]} == {4, 5, 8, 9}


def test_absent_text_returns_nothing(client, book_id):
    result = search(client, q="usucapião extrajudicial")
    assert result["total_pages"] == 0 and result["occurrences"] == []


def test_missing_metadata_is_labelled(client):
    from tests.conftest import build_book_pdf

    upload(client, build_book_pdf(with_cip=False, with_numbers=False))
    hit = search(client, q="reparação integral")["occurrences"][0]
    assert hit["year"] == "Não identificado"
    assert hit["printed_page"] is None and hit["pdf_page"] == 10


def test_book_filter_pagination_and_history(client, book_id):
    assert search(client, q="dano", book_id=book_id + 1)["total_pages"] == 0
    page = search(client, q="dano", mode="qualquer", limit=1, offset=1)
    assert page["total_pages"] == 2 and len({o["pdf_page"] for o in page["occurrences"]}) == 1
    history = client.get("/api/search/history").json()
    assert history[0]["query"] == "dano" and history[0]["kind"] == "citacoes"
    assert len(history) == 1  # a segunda página da mesma busca não é registrada de novo
    assert client.delete("/api/search/history").status_code == 204
    assert client.get("/api/search/history").json() == []


def test_query_validation(client):
    assert client.get("/api/search", params={"q": "a"}).status_code == 422
    assert client.get("/api/search", params={"q": "?!..."}).status_code == 422
    assert client.get("/api/search", params={"q": '" OR 1 NEAR('}).status_code == 200


def test_long_page_is_cut_at_sentence_or_word_and_marked():
    from services.citation_search import build_queries, excerpts

    pattern = build_queries("termo procurado", "frase")[1]
    filler = "palavra " * 80

    text = f"{filler}Primeira frase. O termo procurado aparece aqui no meio. {filler}"
    item = excerpts(text, pattern)[0]
    assert text[item.start:item.end] == "O termo procurado aparece aqui no meio."
    assert not item.truncated_start and not item.truncated_end

    text = f"{filler}o termo procurado sem pontuação por perto {filler}"
    item = excerpts(text, pattern)[0]
    excerpt = text[item.start:item.end]
    assert item.truncated_start and item.truncated_end
    assert excerpt.startswith("palavra ") and excerpt.endswith(" palavra") and len(excerpt) < 520
    assert text[item.spans[0][0]:item.spans[0][1]] == "termo procurado"
