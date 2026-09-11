from app.services.quote_verification import normalize_for_matching, verify_quote


def test_exact_matching_quote_is_verified():
    content = "Large language models can produce fluent but incorrect statements."
    quote = "Large language models can produce fluent but incorrect statements."
    assert verify_quote(quote, content) is True


def test_quote_with_whitespace_differences_is_still_verified():
    content = "Retrieval augmented generation   reduces   hallucination rates significantly."
    quote = "Retrieval augmented generation reduces hallucination rates significantly."
    assert verify_quote(quote, content) is True


def test_quote_with_smart_quotes_and_case_differences_is_verified():
    content = 'The paper states: "hallucinations remain an open problem" for LLMs.'
    quote = "Hallucinations remain an open problem"
    assert verify_quote(quote, content) is True


def test_missing_quote_is_not_verified():
    content = "This page discusses something entirely unrelated to the claim."
    quote = "This exact sentence does not appear anywhere in the source."
    assert verify_quote(quote, content) is False


def test_empty_quote_is_never_verified():
    assert verify_quote("", "any content at all") is False
    assert verify_quote("   ", "any content at all") is False


def test_malformed_evidence_missing_source_content():
    assert verify_quote("some quote", "") is False


def test_paraphrased_quote_correctly_fails_verification():
    # A genuine paraphrase (different words) must NOT be treated as verified —
    # this is a literal substring check, not semantic similarity.
    content = "The model achieved 92% accuracy on the benchmark dataset."
    quote = "The system reached ninety-two percent accuracy on the test set."
    assert verify_quote(quote, content) is False


def test_normalize_collapses_whitespace_and_quote_characters():
    assert normalize_for_matching("  Hello   'world'  ") == "hello 'world'"
    assert normalize_for_matching("“Smart quotes”") == '"smart quotes"'
