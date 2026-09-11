from app.models.schemas import SourceType
from app.services.quality import classify_source_type, score_source_quality


def test_classifies_academic_domain():
    assert classify_source_type("arxiv.org") == SourceType.academic
    assert classify_source_type("mit.edu") == SourceType.academic


def test_classifies_government_domain():
    assert classify_source_type("nist.gov") == SourceType.government


def test_classifies_news_domain():
    assert classify_source_type("reuters.com") == SourceType.news


def test_classifies_blog_as_low_trust():
    assert classify_source_type("someone.medium.com") == SourceType.blog


def test_unknown_domain_defaults_to_other():
    assert classify_source_type("randomsite.xyz") == SourceType.other


def test_academic_scores_higher_than_blog():
    academic_score = score_source_quality("arxiv.org", "some text about the topic")
    blog_score = score_source_quality("someone.medium.com", "some text about the topic")
    assert academic_score > blog_score


def test_recency_boosts_score():
    old = score_source_quality("example.org", "published in 2010", current_year=2026)
    new = score_source_quality("example.org", "published in 2026", current_year=2026)
    assert new >= old


def test_score_bounded_between_zero_and_one():
    score = score_source_quality("arxiv.org", "2026 2026 2026")
    assert 0.0 <= score <= 1.0
