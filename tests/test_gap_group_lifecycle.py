"""Exercise group state transitions against an isolated in-memory database.

The adapter translates PostgreSQL placeholders, row locks and ANY for SQLite.
Production PostgreSQL locking itself is not exercised by these tests.
"""
import json
import re
import sqlite3
from datetime import datetime, timezone

import pytest

pytest.importorskip("psycopg")

from app.services.gap_map_service import GapMapService


NOW = datetime(2026, 11, 13, tzinfo=timezone.utc).isoformat()


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    @staticmethod
    def convert(row):
        if row is None:
            return None
        return tuple(
            datetime.fromisoformat(value)
            if isinstance(value, str) and re.match(r"^\d{4}-\d\d-\d\dT", value)
            else value
            for value in row
        )

    def fetchone(self):
        return self.convert(self.cursor.fetchone())

    def fetchall(self):
        return [self.convert(row) for row in self.cursor.fetchall()]


class Connection:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.create_function("NOW", 0, lambda: NOW)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.db.rollback()

    def commit(self):
        self.db.commit()

    def execute(self, sql, params=None):
        sql = " ".join(sql.split())
        self.calls.append((sql, params))
        if "pg_advisory_xact_lock" in sql:
            return Cursor(self.db.execute("SELECT 1"))
        sql = sql.replace(" FOR UPDATE OF m, g", "").replace(" FOR UPDATE", "")
        params = list(params or [])
        if "gap_id=ANY(%s)" in sql:
            ids = params.pop()
            sql = sql.replace("gap_id=ANY(%s)", f"gap_id IN ({','.join(['%s'] * len(ids))})")
            params.extend(ids)
        params = [json.dumps(value.obj) if hasattr(value, "obj") else value for value in params]
        return Cursor(self.db.execute(sql.replace("%s", "?"), params))


@pytest.fixture
def store(monkeypatch):
    conn = Connection()
    conn.db.executescript("""
        CREATE TABLE knowledge_gap_groups (
            id INTEGER PRIMARY KEY, title TEXT, representative_query TEXT,
            status TEXT, created_at TEXT, updated_at TEXT, resolved_at TEXT,
            confirmed_by TEXT, confirmed_at TEXT
        );
        CREATE TABLE knowledge_gaps (
            id INTEGER PRIMARY KEY, sample_query TEXT, status TEXT,
            occurrence_count INTEGER DEFAULT 1, first_seen_at TEXT, last_seen_at TEXT,
            updated_at TEXT, resolved_at TEXT, resolved_by TEXT, owner_comment TEXT
        );
        CREATE TABLE knowledge_gap_group_members (
            group_id INTEGER, gap_id INTEGER, similarity REAL, assignment_source TEXT,
            removed_at TEXT, removed_by TEXT, removal_reason TEXT
        );
        CREATE TABLE knowledge_gap_status_history (
            gap_id INTEGER, old_status TEXT, new_status TEXT, author TEXT, note TEXT
        );
        CREATE TABLE knowledge_gap_group_operations (
            idempotency_key TEXT PRIMARY KEY, group_id INTEGER, payload_hash TEXT, result TEXT
        );
    """)
    conn.execute("INSERT INTO knowledge_gap_groups VALUES (%s,%s,%s,%s,%s,%s,NULL,NULL,NULL)",
                 (5001, "Подготовка к биохимии", "Можно ли есть?", "candidate", NOW, NOW))
    for gap_id in (1, 2, 3):
        conn.execute("INSERT INTO knowledge_gaps(id,sample_query,status,first_seen_at,last_seen_at) VALUES (%s,%s,'open',%s,%s)",
                     (gap_id, f"Вопрос {gap_id}", NOW, NOW))
        conn.execute("INSERT INTO knowledge_gap_group_members(group_id,gap_id,similarity,assignment_source) VALUES (5001,%s,0.9,'candidate')", (gap_id,))
    conn.commit()
    monkeypatch.setattr("app.services.gap_map_service.get_connection", lambda: conn)
    monkeypatch.setattr(GapMapService, "_ensure_schema", staticmethod(lambda _: None))
    yield conn, GapMapService()
    conn.db.close()


def test_candidate_survives_individual_status_change(store):
    conn, service = store
    service.update_gap_status(1, "in_review", note=None, author="owner")
    assert service.get_group(5001)["status"] == "candidate"
    assert conn.execute("SELECT status FROM knowledge_gaps WHERE id=1").fetchone() == ("in_review",)


def test_candidate_survives_detach_and_keeps_history(store):
    _, service = store
    group = service.detach_member(5001, 3, reason="Другой вопрос", author="owner")
    assert group["status"] == "candidate"
    assert group["activeMemberCount"] == 2
    removed = next(member for member in group["members"] if member["gapId"] == 3)
    assert removed["removedAt"] is not None
    assert removed["removalReason"] == "Другой вопрос"
    assert removed["removedBy"] == "owner"


def test_group_with_one_remaining_member_is_dismissed(store):
    _, service = store
    service.detach_member(5001, 3, reason="Не относится", author="owner")
    group = service.detach_member(5001, 2, reason="Не относится", author="owner")
    assert group["status"] == "dismissed"
    assert group["activeMemberCount"] == 1
    assert len(group["members"]) == 3


def test_confirm_selected_members_and_record_exclusions(store):
    _, service = store
    group = service.confirm_group(5001, member_ids=[1, 2], author="owner")
    assert group["status"] == "open"
    assert group["confirmedBy"] == "owner"
    assert group["confirmedAt"] is not None
    assert group["activeMemberCount"] == 2
    assert [member["assignmentSource"] for member in group["members"] if not member["removedAt"]] == ["owner_confirmed"] * 2
    assert next(member for member in group["members"] if member["gapId"] == 3)["removalReason"] == "not_selected_on_confirmation"


@pytest.mark.parametrize("selected", [[1], [1, 99], [1, 3]])
def test_confirm_rejects_invalid_or_stale_members(store, selected):
    conn, service = store
    conn.execute("UPDATE knowledge_gaps SET status='resolved' WHERE id=3")
    conn.commit()
    with pytest.raises(ValueError):
        service.confirm_group(5001, member_ids=selected, author="owner")
    assert service.get_group(5001)["status"] == "candidate"


@pytest.mark.parametrize("status", ["candidate", "open", "in_review"])
def test_resolve_requires_explicit_confirmation(store, status):
    conn, service = store
    conn.execute("UPDATE knowledge_gap_groups SET status=%s", (status,))
    conn.commit()
    with pytest.raises(ValueError, match="подтвержденную"):
        service.resolve_group(5001, member_ids=[1, 2], note="Дополнена БЗ", author="owner", idempotency_key="operation")
    assert conn.execute("SELECT COUNT(*) FROM knowledge_gaps WHERE status='resolved'").fetchone() == (0,)


def test_partial_close_and_retry_do_not_duplicate_history(store):
    conn, service = store
    service.confirm_group(5001, member_ids=[1, 2, 3], author="owner")
    request = dict(member_ids=[1, 2], note="Дополнены правила", author="owner", idempotency_key="operation")
    first = service.resolve_group(5001, **request)
    second = service.resolve_group(5001, **request)
    assert first == second
    assert first["resolved_gap_ids"] == [1, 2]
    assert conn.execute("SELECT COUNT(*) FROM knowledge_gap_status_history").fetchone() == (2,)
    assert service.get_group(5001)["status"] == "open"
    assert conn.execute("SELECT status FROM knowledge_gaps WHERE id=3").fetchone() == ("open",)
    with pytest.raises(ValueError, match="другой операции"):
        service.resolve_group(5001, **{**request, "member_ids": [3]})


def test_close_all_selected_members_resolves_group(store):
    _, service = store
    service.confirm_group(5001, member_ids=[1, 2], author="owner")
    service.resolve_group(5001, member_ids=[1, 2], note="Дополнена БЗ", author="owner", idempotency_key="operation")
    assert service.get_group(5001)["status"] == "resolved"


def test_direct_lookup_does_not_use_limited_list_or_create_suggestions(store, monkeypatch):
    _, service = store
    def unexpected(*_, **__):
        pytest.fail("Direct lookup must not enumerate groups or generate suggestions")
    monkeypatch.setattr(service, "list_groups", unexpected)
    monkeypatch.setattr(service, "_backfill_candidate_groups", unexpected)
    assert service.get_group(5001)["id"] == 5001
    assert len(service.get_group(5001)["members"]) == 3
    assert service.get_group(9999) is None


def test_close_remaining_skips_previously_closed_members(store):
    conn, service = store
    service.confirm_group(5001, member_ids=[1, 2, 3], author="owner")
    service.resolve_group(5001, member_ids=[1], note="Первая правка", author="owner", idempotency_key="first")
    result = service.resolve_group(5001, member_ids=None, note="Остальные правки", author="owner", idempotency_key="remaining")
    assert result["resolved_gap_ids"] == [2, 3]
    assert service.get_group(5001)["status"] == "resolved"
    assert conn.execute("SELECT COUNT(*) FROM knowledge_gap_status_history WHERE gap_id=1").fetchone() == (1,)


def test_stale_selected_member_rolls_back_partial_updates(store):
    conn, service = store
    service.confirm_group(5001, member_ids=[1, 2, 3], author="owner")
    service.update_gap_status(2, "dismissed", note="Не пробел", author="other")
    with pytest.raises(ValueError, match="Статус пробела изменился"):
        service.resolve_group(5001, member_ids=[1, 2], note="Закрыть", author="owner", idempotency_key="operation")
    assert conn.execute("SELECT status FROM knowledge_gaps WHERE id=1").fetchone() == ("open",)
    assert conn.execute("SELECT COUNT(*) FROM knowledge_gap_group_operations").fetchone() == (0,)
