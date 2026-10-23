from app.services.knowledge_gap_tracker import KnowledgeGapTracker, _normalise


def test_normalise_collapses_case_punctuation_and_yo():
    assert _normalise("  СКОЛЬКО стоит гастроскопия? ") == "сколько стоит гастроскопия"
    assert _normalise("Ёмкость") == _normalise("емкость")


def test_tracker_skips_when_database_url_is_missing():
    tracker = KnowledgeGapTracker(database_url="")
    tracker.database_url = None
    assert tracker.record_gap(query="Стоимость гастроскопии", reason="wiki_evidence_does_not_cover_request") is False


def test_tracker_skips_empty_query():
    tracker = KnowledgeGapTracker(database_url="postgresql://unused")
    assert tracker.record_gap(query="   ", reason="wiki_evidence_does_not_cover_request") is False
