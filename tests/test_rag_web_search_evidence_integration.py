from app.services.rag import RagService
from app.services.web_search import (
    WebSearchResult,
    has_answerable_web_evidence,
    has_procedure_specific_preparation_evidence,
    is_relevant_web_result,
)


def test_english_upper_endoscopy_leaflet_is_eligible_for_russian_gastroscopy_query():
    question = "Как подготовиться к проведению гастроскопия?"
    result = WebSearchResult(
        title="Upper Endoscopy preparation instructions",
        url="https://www.nhs.uk/example",
        snippet=(
            "Nothing by mouth for 6 hours before your procedure. "
            "Please contact the endoscopy unit if you take regular medication."
        ),
        rank=1,
        domain="www.nhs.uk",
    )

    assert has_procedure_specific_preparation_evidence(
        question, title=result.title, content=result.snippet
    )
    assert is_relevant_web_result(question, result)
    assert has_answerable_web_evidence(question, result)


def test_procedure_mismatch_and_title_only_page_remain_rejected():
    question = "Как подготовиться к проведению гастроскопия?"
    assert not has_procedure_specific_preparation_evidence(
        question,
        title="Colonoscopy preparation instructions",
        content="Nothing by mouth for 6 hours before your procedure.",
    )
    assert not has_procedure_specific_preparation_evidence(
        question,
        title="Upper Endoscopy overview",
        content="Upper endoscopy is a procedure to inspect the upper digestive tract.",
    )


def test_russian_claim_can_be_attributed_to_english_preparation_evidence():
    russian_claim = "Не ешьте ничего за 6 часов до гастроскопии."
    english_evidence = "Upper Endoscopy: do not eat anything for 6 hours before the procedure."

    claim_terms = RagService._claim_terms(russian_claim)
    evidence_terms = RagService._claim_terms(english_evidence)
    assert {"gastroscopy", "eat", "hour"}.issubset(claim_terms & evidence_terms)


def test_facet_coverage_accepts_explicit_english_preparation_wording():
    question = "Как подготовиться к проведению гастроскопия?"
    sources = [{
        "source_id": "WEB1",
        "source_type": "web",
        "title": "Upper Endoscopy patient instructions",
        "snippet": "Nothing by mouth for 6 hours before your procedure.",
        "matched_query_aspects": [question],
        "_internal_evidence_text": "Nothing by mouth for 6 hours before your procedure.",
    }]
    claim_audit = [{
        "claim": "Не ешьте ничего за 6 часов до гастроскопии.",
        "source_ids": ["WEB1"],
        "supported": True,
        "suppressed": False,
    }]

    coverage = RagService._facet_coverage([question], sources, claim_audit)
    assert coverage[0]["covered"] is True
    assert coverage[0]["supporting_source_ids"] == ["WEB1"]


def test_main_rag_query_planner_uses_grounded_english_variant_without_unrelated_terms():
    question = "Как подготовиться к проведению гастроскопия?"
    variants = RagService._web_search_query_variants(question)

    assert question in variants
    assert any("gastroscopy" in query.casefold() for query in variants)
    assert all("dosage" not in query.casefold() for query in variants)
