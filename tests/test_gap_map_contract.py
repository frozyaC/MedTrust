import pytest

pytest.importorskip("psycopg")

from app.services.gap_map_service import (
    FEEDBACK_CODES,
    GAP_FEEDBACK_CODES,
    _group_status,
    _reason_code,
)


def test_feedback_reason_codes_route_to_gap_or_quality_issue():
    assert GAP_FEEDBACK_CODES == {
        "no_knowledge_base_answer", "knowledge_incomplete", "knowledge_outdated"
    }
    assert GAP_FEEDBACK_CODES.issubset(FEEDBACK_CODES)
    assert "answer_incorrect" in FEEDBACK_CODES
    assert "technical_error" in FEEDBACK_CODES


def test_answerability_reason_codes_capture_conflict_freshness_and_partial_coverage():
    assert _reason_code({"a": "document_conflict_detected"}, []) == "knowledge_conflict"
    assert _reason_code({"a": "fresh_clinical_guidance_not_verified_externally"}, [True]) == "knowledge_outdated"
    assert _reason_code({"a": "wiki_evidence_does_not_cover_request"}, [True, False]) == "knowledge_incomplete"
    assert _reason_code({"a": "no_topic_specific_wiki_evidence"}, [False]) == "no_knowledge_base_answer"


def test_group_lifecycle_aggregates_member_statuses_without_overwriting_members():
    assert _group_status(["open", "resolved"]) == "open"
    assert _group_status(["in_review", "resolved"]) == "in_review"
    assert _group_status(["resolved", "dismissed"]) == "resolved"
    assert _group_status(["dismissed", "dismissed"]) == "dismissed"
    assert _group_status([]) == "dismissed"
