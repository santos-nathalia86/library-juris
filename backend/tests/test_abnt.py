from services.abnt import build_call, build_citation, build_reference, catalog_reference, format_author

ALL = ["author", "title", "subtitle", "edition", "city", "publisher", "year", "isbn"]


def book(**overrides):
    base = dict(
        author="Humberto Theodoro Júnior", title="Curso de direito processual civil", subtitle=None, edition="61",
        city="Rio de Janeiro", publisher="Forense", year="2020", isbn=None, confirmed_fields=ALL,
    )
    return {**base, **overrides}


def test_author_inversion():
    assert format_author("Humberto Theodoro Júnior") == "THEODORO JÚNIOR, Humberto"
    assert format_author("Maria Helena Diniz") == "DINIZ, Maria Helena"
    assert format_author("João da Silva") == "SILVA, João da"
    assert format_author("Diniz, Maria Helena") == "DINIZ, Maria Helena"
    assert format_author("FLÁVIO TARTUCE") == "TARTUCE, Flávio"


def test_complete_reference():
    ref = build_reference(book())
    assert ref.text == (
        "THEODORO JÚNIOR, Humberto. Curso de direito processual civil. 61. ed. Rio de Janeiro: Forense, 2020."
    )
    assert ref.emphasis == "Curso de direito processual civil"
    assert ref.missing == [] and ref.unconfirmed == []


def test_subtitle_page_isbn_and_multiple_authors():
    ref = build_reference(
        book(author="Ana Lima; Pedro Souza Filho", subtitle="parte geral", isbn="978-85-333-0227-3"), "45"
    )
    assert ref.text == (
        "LIMA, Ana; SOUZA FILHO, Pedro. Curso de direito processual civil: parte geral. 61. ed. "
        "Rio de Janeiro: Forense, 2020. p. 45. ISBN 978-85-333-0227-3."
    )


def test_missing_data_is_flagged_not_invented():
    ref = build_reference(book(author=None, city=None, publisher=None, year=None, edition=None))
    assert ref.text == "CURSO de direito processual civil. [S. l.: s. n.], [s. d.]."
    assert ref.missing == ["author", "city", "publisher", "year"]


def test_unconfirmed_values_stay_out_of_the_reference():
    ref = build_reference(book(confirmed_fields=["title", "year"]))
    assert ref.text == "CURSO de direito processual civil. [S. l.: s. n.], 2020."
    assert set(ref.unconfirmed) == {"author", "edition", "city", "publisher"}
    assert "Forense" not in ref.text and "THEODORO" not in ref.text


def test_corporate_authors_are_not_inverted():
    assert format_author("Conselho Nacional de Justiça") == "CONSELHO NACIONAL DE JUSTIÇA"
    assert format_author("Brasil. Superior Tribunal de Justiça (STJ)") == "BRASIL. Superior Tribunal de Justiça (STJ)"
    assert format_author("Centro, Maria") == "CENTRO, Maria"


def test_call_author_date_page():
    assert build_call(book(), "45") == ("(Theodoro Júnior, 2020, p. 45)", [])
    assert build_call(book(author="FLÁVIO TARTUCE; Ana Lima"), "7")[0] == "(Tartuce; Lima, 2020, p. 7)"
    assert build_call(book(author="A B; C D; E F; G H"), "7")[0] == "(B et al., 2020, p. 7)"
    assert build_call(book(author="Brasil. Superior Tribunal de Justiça"), "3")[0] == "(Brasil, 2020, p. 3)"


def test_call_flags_what_is_missing_instead_of_inventing():
    call, warnings = build_call(book(author=None, year=None))
    assert call == "(Curso [...], [s. d.])"
    assert len(warnings) == 3 and "página impressa não identificada" in warnings[2]
    call, warnings = build_call(book(confirmed_fields=[]), "9")
    assert call == "([autoria não identificada], [s. d.], p. 9)"


def test_short_citation_is_quoted_and_long_is_not():
    short = build_citation(book(), 'a chamada "boa-fé" impõe deveres', "45", truncated_start=True, truncated_end=True)
    assert short.text == "\"[...] a chamada 'boa-fé' impõe deveres [...]\" (Theodoro Júnior, 2020, p. 45)."
    assert not short.long
    long = build_citation(book(), "palavra " * 40, "45")
    assert long.long and long.text == ("palavra " * 40).strip() + " (Theodoro Júnior, 2020, p. 45)."


def test_catalog_reference():
    ref = catalog_reference("A força normativa: estudo", ["JOÃO HORA NETO"], "2024", "Editora Thoth", "9786559596881")
    assert ref.text == "HORA NETO, João. A força normativa: estudo. [S. l.]: Editora Thoth, 2024. ISBN 9786559596881."
    assert ref.emphasis == "A força normativa" and ref.missing == ["city"]
