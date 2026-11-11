from types import SimpleNamespace

import pytest

from app.services.knowledge_gap_tracker import (
    KnowledgeGapTracker,
    _fingerprint,
    _normalise,
    _privacy_safe_query,
    _similarity_action,
    _updated_centroid,
)


def test_sha256_fingerprint_is_preserved_for_exact_normalized_duplicates():
    first = _normalise("Когда готов ОАК?")
    second = _normalise("  КОГДА   ГОТОВ ОАК!!! ")
    assert first == second
    assert _fingerprint(first) == _fingerprint(second)
    assert _fingerprint(first) != _fingerprint(_normalise("Как подготовиться к ОАК?"))


def test_normalization_handles_yo_case_and_punctuation():
    assert _normalise("Ёмкость, ОАК!!!") == _normalise("емкость оак")


@pytest.mark.parametrize(
    ("similarity", "expected"),
    [
        (0.95, "review"),
        (0.90, "review"),
        (0.8999, "review"),
        (0.80, "review"),
        (0.7999, "new"),
        (0.20, "new"),
    ],
)
def test_similarity_thresholds(similarity, expected):
    assert _similarity_action(similarity) == expected


def test_centroid_update_uses_occurrence_weight():
    result = _updated_centroid([1.0, 0.0], [0.0, 1.0], old_weight=3, new_weight=1)
    assert result == pytest.approx([0.75, 0.25])


def test_centroid_update_supports_backfilling_multiple_occurrences():
    result = _updated_centroid([1.0, 0.0], [0.0, 1.0], old_weight=2, new_weight=2)
    assert result == pytest.approx([0.5, 0.5])


def test_centroid_dimension_mismatch_is_rejected():
    with pytest.raises(ValueError, match="dimensions"):
        _updated_centroid([1.0, 0.0], [1.0], old_weight=1)


def test_thresholds_are_loaded_from_settings_and_validated(monkeypatch):
    monkeypatch.setattr(
        KnowledgeGapTracker,
        "_settings",
        staticmethod(lambda: SimpleNamespace(
            knowledge_gap_similarity_threshold=0.92,
            knowledge_gap_review_threshold=0.78,
        )),
    )
    assert KnowledgeGapTracker._thresholds() == (0.92, 0.78)

    monkeypatch.setattr(
        KnowledgeGapTracker,
        "_settings",
        staticmethod(lambda: SimpleNamespace(
            knowledge_gap_similarity_threshold=0.75,
            knowledge_gap_review_threshold=0.80,
        )),
    )
    with pytest.raises(ValueError, match="thresholds"):
        KnowledgeGapTracker._thresholds()


def test_evidence_is_compact_and_ignores_non_dict_values():
    evidence = KnowledgeGapTracker._evidence([
        {"title": "ОАК", "wiki_path": "Регистратура/ОАК", "section": "Подготовка"},
        "invalid",
    ])
    assert evidence == [{
        "title": "ОАК",
        "path": "Регистратура/ОАК",
        "section": "Подготовка",
    }]


def test_high_confidence_match_creates_review_candidate_without_auto_merge(monkeypatch):
    import sys
    from unittest.mock import Mock

    monkeypatch.setitem(sys.modules, "pgvector", SimpleNamespace(Vector=lambda values: values))
    monkeypatch.setattr(
        KnowledgeGapTracker,
        "_thresholds",
        staticmethod(lambda: (0.90, 0.80)),
    )
    tracker = KnowledgeGapTracker(database_url="unused")
    cluster_id = "cluster-1"
    tracker._find_cluster = Mock(return_value={
        "id": cluster_id,
        "canonical_question": "Состав ОАК",
        "embedding": [1.0, 0.0],
        "occurrence_count": 4,
        "similarity": 0.95,
    })
    cursor = Mock()

    assigned, suggested, score, match_type = tracker._assign_cluster(
        cursor,
        query="Какие показатели входят в общий анализ крови?",
        normalized="какие показатели входят в общий анализ крови",
        embedding=[0.0, 1.0],
    )

    assert assigned is not None
    assert assigned != cluster_id
    assert suggested == cluster_id
    assert score == 0.95
    assert match_type == "review_candidate"
    assert "INSERT INTO knowledge_gap_clusters" in cursor.execute.call_args.args[0]
    assert not any("UPDATE knowledge_gap_clusters" in str(call.args[0]) for call in cursor.execute.call_args_list)


def test_borderline_match_creates_review_candidate_instead_of_auto_merge(monkeypatch):
    import sys
    from unittest.mock import Mock

    monkeypatch.setitem(sys.modules, "pgvector", SimpleNamespace(Vector=lambda values: values))
    monkeypatch.setattr(
        KnowledgeGapTracker,
        "_thresholds",
        staticmethod(lambda: (0.90, 0.80)),
    )
    tracker = KnowledgeGapTracker(database_url="unused")
    candidate_id = "candidate-cluster"
    tracker._find_cluster = Mock(return_value={
        "id": candidate_id,
        "canonical_question": "Состав ОАК",
        "embedding": [1.0, 0.0],
        "occurrence_count": 3,
        "similarity": 0.85,
    })
    cursor = Mock()

    assigned, suggested, score, match_type = tracker._assign_cluster(
        cursor,
        query="Какой общий анализ крови включает показатели?",
        normalized="какой общий анализ крови включает показатели",
        embedding=[0.9, 0.1],
    )

    assert assigned is not None
    assert assigned != candidate_id
    assert suggested == candidate_id
    assert score == 0.85
    assert match_type == "review_candidate"
    assert "INSERT INTO knowledge_gap_clusters" in cursor.execute.call_args.args[0]


def test_list_clusters_reports_lifecycle_statuses_separately(monkeypatch):
    from datetime import datetime, timezone

    timestamp = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    aggregate_row = (
        "cluster-1",
        "стоимость гастроскопии",
        4,
        timestamp,
        timestamp,
        2,  # distinct questions
        1,  # open
        1,  # in_review
        0,  # resolved
        0,  # dismissed
        1,  # suggested merges
    )
    member_rows = [
        (2, "стоимость гастроскопии", "wiki_evidence_does_not_cover_request", "in_review", 3, 0.5, "new"),
        (11, "цена гастроскопии", "wiki_evidence_does_not_cover_request", "open", 1, 0.947, "semantic"),
    ]

    class FakeCursor:
        def __init__(self):
            self.rows = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            if "SELECT c.id, c.canonical_question" in query:
                self.rows = [aggregate_row]
            elif "SELECT id, sample_query, reason, status" in query:
                self.rows = member_rows
            else:
                self.rows = []

        def fetchall(self):
            return self.rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return FakeCursor()

    tracker = KnowledgeGapTracker(database_url="unused")
    monkeypatch.setattr(tracker, "_connection", lambda _: FakeConnection())
    monkeypatch.setattr(
        "app.services.knowledge_gap_tracker._ensure_schema",
        lambda cursor: None,
    )

    clusters = tracker.list_clusters()

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["distinctQuestions"] == 2
    assert cluster["openQuestions"] == 1
    assert cluster["inReviewQuestions"] == 1
    assert cluster["resolvedQuestions"] == 0
    assert cluster["dismissedQuestions"] == 0
    assert cluster["unresolvedQuestions"] == 2
    assert cluster["suggestedMergeCount"] == 1
    assert [member["status"] for member in cluster["members"]] == ["in_review", "open"]


def test_phi_like_identifiers_are_redacted_before_embedding_and_gap_indexing():
    safe = _privacy_safe_query(
        "Пациент Иванов Иван Иванович, дата рождения 01.02.1980, "
        "телефон +7 999 123-45-67, почта test@example.org: подготовка к гастроскопии"
    )
    assert "Иванов" not in safe
    assert "01.02.1980" not in safe
    assert "+7 999 123-45-67" not in safe
    assert "test@example.org" not in safe
    assert "подготовка к гастроскопии" in safe
