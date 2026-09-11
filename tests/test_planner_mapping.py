"""Proves search-query -> subquestion mapping is exact (explicit data
relationship), not a positional `index % len(subquestions)` guess — the two
diverge as soon as subquestions carry different numbers of queries."""
from app.agent.researcher import subquestion_for_query
from app.models.schemas import ResearchPlan, SubquestionPlan


def _build_uneven_plan() -> ResearchPlan:
    # Deliberately uneven query counts per subquestion — this is exactly the
    # case where `index % len(subquestions)` positional mapping breaks.
    return ResearchPlan(
        items=[
            SubquestionPlan(subquestion="What are the main approaches?", search_queries=["approach overview"]),
            SubquestionPlan(
                subquestion="What evidence supports each approach?",
                search_queries=["evidence study one", "evidence study two", "evidence study three"],
            ),
            SubquestionPlan(subquestion="What are the open limitations?", search_queries=["known limitations"]),
        ]
    )


def test_each_query_maps_back_to_its_own_subquestion():
    plan = _build_uneven_plan()

    assert subquestion_for_query(plan, "approach overview") == "What are the main approaches?"
    assert subquestion_for_query(plan, "known limitations") == "What are the open limitations?"
    for q in ("evidence study one", "evidence study two", "evidence study three"):
        assert subquestion_for_query(plan, q) == "What evidence supports each approach?"


def test_mapping_survives_uneven_query_distribution_where_positional_logic_would_fail():
    plan = _build_uneven_plan()
    # 5 total queries across 3 subquestions: index % len(subquestions) would
    # wrongly wrap "known limitations" (flat index 4) back onto subquestion
    # index 4 % 3 == 1 ("What evidence supports each approach?") instead of
    # its real owner, subquestion index 2.
    assert subquestion_for_query(plan, "known limitations") != "What evidence supports each approach?"
    assert subquestion_for_query(plan, "known limitations") == "What are the open limitations?"


def test_search_queries_property_flattens_and_dedupes_case_insensitively():
    plan = ResearchPlan(
        items=[
            SubquestionPlan(subquestion="Q1", search_queries=["Foo Bar", "foo bar"]),
            SubquestionPlan(subquestion="Q2", search_queries=["Baz"]),
        ]
    )
    assert plan.search_queries == ["Foo Bar", "Baz"]


def test_unknown_query_falls_back_to_first_subquestion():
    plan = _build_uneven_plan()
    assert subquestion_for_query(plan, "a query that was never generated") == plan.subquestions[0]
