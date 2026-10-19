from services.page_numbering import INFERRED, PDF_LABEL, PRINTED, Candidate, candidates_from_lines, resolve_labels


def arabic(*values):
    return {Candidate("arabic", v) for v in values}


def test_candidates_from_headers_and_footers():
    assert candidates_from_lines(["— 45 —"]) == arabic(45)
    assert candidates_from_lines(["Capítulo 3 • Contratos 145"]) == arabic(145)
    assert candidates_from_lines(["xiv"]) == {Candidate("roman", 14)}
    assert candidates_from_lines(["texto corrido sem número"]) == set()


def test_sequence_with_offset_and_distinct_pdf_page():
    pages = [set(), set(), set(), arabic(1), arabic(2), arabic(3), arabic(4)]
    labels = resolve_labels(pages)
    assert labels[:3] == [None, None, None]
    assert [(l.label, l.source) for l in labels[3:]] == [(str(n), PRINTED) for n in range(1, 5)]


def test_isolated_numbers_are_rejected():
    # "Capítulo 3" repetido no cabeçalho e uma nota solta não formam sequência.
    pages = [arabic(3), arabic(3), arabic(3), arabic(17), set()]
    assert resolve_labels(pages) == [None] * 5


def test_noise_does_not_override_real_sequence():
    pages = [arabic(10, 3), arabic(11, 3), arabic(12, 3), arabic(13, 1990)]
    assert [l.label for l in resolve_labels(pages)] == ["10", "11", "12", "13"]


def test_gap_is_inferred_and_marked():
    pages = [arabic(7), arabic(8), set(), arabic(10), arabic(11)]
    labels = resolve_labels(pages)
    assert (labels[2].label, labels[2].source) == ("9", INFERRED)


def test_roman_front_matter_then_arabic():
    pages = [{Candidate("roman", v)} for v in (5, 6, 7)] + [arabic(1), arabic(2), arabic(3)]
    assert [l.label for l in resolve_labels(pages)] == ["v", "vi", "vii", "1", "2", "3"]


def test_pdf_labels_only_fill_blanks():
    labels = resolve_labels([set(), arabic(1), arabic(2), arabic(3)], ["Capa", "x", "y", "z"])
    assert (labels[0].label, labels[0].source) == ("Capa", PDF_LABEL)
    assert labels[1].label == "1"
