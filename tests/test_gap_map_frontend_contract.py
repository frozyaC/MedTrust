import pytest

pytest.importorskip("psycopg")

from datetime import datetime, timezone

from app.schemas.api import GapClusterDetachRequest
from app.services.gap_map_service import GapMapService


class FakeCursor:
    def __init__(self, *, one=None, all_rows=None):
        self._one = one
        self._all = all_rows or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._all


class FakeConnection:
    def __init__(self, *, one=None, all_rows=None):
        self.one = one
        self.all_rows = all_rows or []
        self.calls = []
        self.commits = 0

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "SELECT suggested_cluster_id,similarity_score,cluster_match_type" in sql:
            return FakeCursor(one=self.one)
        if "SELECT g.id" in sql and "FROM knowledge_gaps g" in sql:
            return FakeCursor(all_rows=self.all_rows)
        return FakeCursor()

    def commit(self):
        self.commits += 1


class FakeConnectionContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


def _patch_db(monkeypatch, conn):
    import app.services.gap_map_service as module

    monkeypatch.setattr(module, "get_connection", lambda: FakeConnectionContext(conn))
    monkeypatch.setattr(GapMapService, "_ensure_schema", staticmethod(lambda _conn: None))


def test_gap_cluster_detach_request_requires_reason():
    request = GapClusterDetachRequest(reason="Это самостоятельная проблема", author="owner")
    assert request.reason == "Это самостоятельная проблема"
    assert request.author == "owner"


def test_backfill_discovers_similar_embeddings_without_legacy_cluster_flags(monkeypatch):
    conn = FakeConnection(all_rows=[(17,), (18,), (19,), (20,)])
    _patch_db(monkeypatch, conn)
    captured = []
    monkeypatch.setattr(
        GapMapService,
        "suggest_groups_for_gap_ids",
        lambda self, ids: captured.extend(ids) or len(ids),
    )

    created = GapMapService()._backfill_candidate_groups()

    assert created == 4
    assert captured == [17, 18, 19, 20]
    sql, params = conn.calls[0]
    assert "1-(neighbour.embedding <=> g.embedding) >= %s" in sql
    assert "cluster_match_type='review_candidate'" not in sql
    assert params[1] == 1000
    assert conn.commits == 1


def test_list_groups_filters_by_gap_id_and_triggers_backfill(monkeypatch):
    conn = FakeConnection(all_rows=[])
    _patch_db(monkeypatch, conn)
    backfill_calls = []
    monkeypatch.setattr(
        GapMapService,
        "_backfill_candidate_groups",
        lambda self: backfill_calls.append(True) or 0,
    )

    result = GapMapService().list_groups(gap_id=18)

    assert result == []
    assert backfill_calls == [True]
    sql, params = conn.calls[0]
    assert "gap_filter.gap_id = %s::bigint" in sql
    assert params == (None, None, 18, 18, 500)


def test_list_gaps_can_load_a_specific_member_outside_the_recent_list(monkeypatch):
    conn = FakeConnection(all_rows=[])
    _patch_db(monkeypatch, conn)
    assert GapMapService().list_gaps(gap_id=5001) == []
    sql, params = conn.calls[0]
    assert "WHERE g.id=%s" in sql
    assert params == [5001, 500]


def test_detach_legacy_cluster_suggestion_is_audited_and_cleared(monkeypatch):
    cluster_id = "c7b1b820-6a56-4f18-bfca-1c15a193b2af"
    conn = FakeConnection(one=(cluster_id, 0.91, "review_candidate"))
    _patch_db(monkeypatch, conn)

    result = GapMapService().detach_cluster_suggestion(
        18, reason="Это другая проблема", author="owner",
    )

    assert result == {
        "gapId": 18,
        "status": "detached",
        "previousSuggestedClusterId": cluster_id,
        "previousSimilarity": 0.91,
    }
    audit = next(call for call in conn.calls if "INSERT INTO knowledge_gap_cluster_suggestion_history" in call[0])
    assert audit[1] == (18, cluster_id, 0.91, "Это другая проблема", "owner")
    update = next(call for call in conn.calls if "UPDATE knowledge_gaps" in call[0])
    assert "suggested_cluster_id=NULL" in update[0]
    assert "cluster_match_type='detached'" in update[0]
    assert conn.commits == 1


@pytest.mark.parametrize("with_feedback", [False, True])
def test_list_gaps_exposes_frontend_cluster_metadata(monkeypatch, with_feedback):
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    row = [None] * 34
    row[0] = 18
    row[1] = "Запрос о подготовке к исследованию"
    row[2] = "запрос о подготовке к исследованию"
    row[3] = "no_knowledge_base_answer"
    row[4] = "open"
    row[5] = "automatic"
    row[6] = now
    row[7] = now
    row[11] = 2
    row[13] = ""
    row[19] = "automatic"
    row[22] = []
    row[24] = 1
    row[25] = "c7b1b820-6a56-4f18-bfca-1c15a193b2af"
    row[26] = "22acb820-6a56-4f18-bfca-1c15a193b2af"
    row[27] = "review_candidate"
    row[28] = 0.91
    row[29] = 3
    if with_feedback:
        row[30] = "feedback-id"
        row[31] = "dislike"
        row[32] = " Missing preparation details "
        row[33] = [{"id": "comment-id", "body": "Needs review"}]
    conn = FakeConnection(all_rows=[tuple(row)])
    _patch_db(monkeypatch, conn)

    result = GapMapService().list_gaps()

    assert result[0]["suggestedMergeCount"] == 3
    assert result[0]["clusterId"] == row[25]
    assert result[0]["suggestedClusterId"] == row[26]
    assert result[0]["clusterMatchType"] == "review_candidate"
    assert result[0]["similarityScore"] == 0.91
    assert result[0]["feedback"] == (
        {"id": "feedback-id", "rating": "dislike", "comment": "Missing preparation details"}
        if with_feedback else None
    )
    assert result[0]["comments"] == (row[33] if with_feedback else [])
    assert result[0]["webSearchUsed"] is False
