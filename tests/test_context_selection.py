from app.services.context_selection import select_relevant_context, split_into_paragraphs


def test_short_content_returned_unchanged():
    content = "A short paragraph."
    assert select_relevant_context(content, "some query", max_chars=1000) == content


def test_relevant_paragraph_is_prioritized_over_irrelevant_one():
    irrelevant = "Unrelated paragraph about cooking recipes and kitchen tools. " * 3
    relevant = "Retrieval augmented generation reduces hallucination in language models."
    content = "\n".join([irrelevant, relevant])

    # Budget too small to fit both paragraphs, forcing a choice.
    selected = select_relevant_context(content, "hallucination language models", max_chars=len(relevant) + 5)
    assert "hallucination" in selected
    assert "cooking recipes" not in selected


def test_original_document_order_is_preserved_among_selected_paragraphs():
    p1 = "Paragraph one discusses language models and hallucination risks."
    p2 = "Paragraph two is about hallucination in language models as well."
    p3 = "Paragraph three also covers language models and hallucination topics."
    content = "\n".join([p1, p2, p3])

    selected = select_relevant_context(content, "language models hallucination", max_chars=10_000)
    assert selected.index(p1) < selected.index(p2) < selected.index(p3)


def test_result_never_exceeds_max_chars():
    content = "\n".join(f"Paragraph {i} about various unrelated topics and filler text." for i in range(50))
    selected = select_relevant_context(content, "various topics", max_chars=200)
    assert len(selected) <= 200


def test_falls_back_to_prefix_slice_when_no_paragraph_structure():
    content = "one long blob of text with no newlines at all " * 20
    selected = select_relevant_context(content, "some query", max_chars=50)
    assert selected == content[:50]


def test_split_into_paragraphs_filters_blank_lines():
    content = "para one\n\n  \npara two\n"
    assert split_into_paragraphs(content) == ["para one", "para two"]
