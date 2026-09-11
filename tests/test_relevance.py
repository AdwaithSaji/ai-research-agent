from app.services.relevance import relevance_score


def test_relevant_text_scores_higher_than_irrelevant():
    query = "hallucination reduction techniques for language models"
    relevant = "This paper discusses hallucination reduction techniques for large language models."
    irrelevant = "The weather today is sunny with a chance of rain in the evening."
    assert relevance_score(query, relevant) > relevance_score(query, irrelevant)


def test_empty_source_scores_zero():
    assert relevance_score("some query", "") == 0.0


def test_empty_query_scores_zero():
    assert relevance_score("", "some source text") == 0.0


def test_score_is_bounded():
    score = relevance_score("test query words", "test query words test query words")
    assert 0.0 <= score <= 1.0
