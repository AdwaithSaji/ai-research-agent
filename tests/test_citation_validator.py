from app.services.citation_validator import sanitize_citations, sanitize_many


def test_valid_citation_is_preserved():
    result = sanitize_citations("LLMs can hallucinate facts [1].", {"[1]", "[2]"})
    assert result.text == "LLMs can hallucinate facts [1]."
    assert result.markers_found == 1
    assert result.markers_valid == 1
    assert result.markers_invalid_removed == 0


def test_invalid_citation_is_removed_not_fabricated():
    result = sanitize_citations("The model claims this is true [7].", {"[1]", "[2]"})
    assert "[7]" not in result.text
    assert result.markers_found == 1
    assert result.markers_valid == 0
    assert result.markers_invalid_removed == 1


def test_missing_citation_is_a_noop():
    result = sanitize_citations("A sentence with no citation marker at all.", {"[1]"})
    assert result.markers_found == 0
    assert result.markers_valid == 0
    assert result.markers_invalid_removed == 0
    assert result.text == "A sentence with no citation marker at all."


def test_multiple_citations_mixed_validity():
    text = "Claim A [1] and claim B [9] and claim C [2]."
    result = sanitize_citations(text, {"[1]", "[2]"})
    assert result.markers_found == 3
    assert result.markers_valid == 2
    assert result.markers_invalid_removed == 1
    assert "[1]" in result.text
    assert "[2]" in result.text
    assert "[9]" not in result.text


def test_empty_text_is_handled():
    result = sanitize_citations("", {"[1]"})
    assert result.markers_found == 0
    assert result.text == ""


def test_sanitize_many_aggregates_stats_across_fields():
    texts = ["Finding one [1].", "Finding two [5].", "No citation here."]
    cleaned, stats = sanitize_many(texts, {"[1]"})
    assert len(cleaned) == 3
    assert stats.markers_found == 2
    assert stats.markers_valid == 1
    assert stats.markers_invalid_removed == 1
    assert "[5]" not in cleaned[1]
