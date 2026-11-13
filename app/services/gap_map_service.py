"""Event-oriented knowledge-gap map, feedback routing and owner-controlled groups.

The existing knowledge_gaps table remains the normalized/frequency projection for
backward compatibility.  This module adds immutable per-query events and explicit
owner-confirmed groups without rewriting chat history or RAG/prompt-security code.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any

from psycopg.types.json import Jsonb

from app.db.database import get_connection
from app.services.knowledge_gap_tracker import KnowledgeGapTracker, _privacy_safe_query

logger = logging.getLogger(__name__)

GAP_FEEDBACK_CODES = {"no_knowledge_base_answer", "knowledge_incomplete", "knowledge_outdated"}
FEEDBACK_CODES = GAP_FEEDBACK_CODES | {
    "answer_irrelevant", "answer_incorrect", "answer_formatting", "wrong_context",
    "wrong_source", "technical_error", "other",
}
GAP_STATUSES = {"open", "in_review", "resolved", "dismissed"}


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, (dict, list)) else default
        except Exception:
            return default
    return default


def _reason_code(reasons: dict[str, Any], sufficient_facets: list[bool]) -> str:
    joined = " ".join(str(v) for v in reasons.values()).casefold()
    if any(x in joined for x in ("contradict", "conflict", "противореч")):
        return "knowledge_conflict"
    if any(x in joined for x in ("outdated", "stale", "fresh_clinical_guidance")):
        return "knowledge_outdated"
    if sufficient_facets and any(sufficient_facets):
        return "knowledge_incomplete"
    return "no_knowledge_base_answer"


def _group_status(statuses: list[str]) -> str:
    if not statuses:
        return "dismissed"
    if "open" in statuses:
        return "open"
    if "in_review" in statuses:
        return "in_review"
    if all(status == "dismissed" for status in statuses):
        return "dismissed"
    if all(status in {"resolved", "dismissed"} for status in statuses):
        return "resolved"
    return "open"


class GapMapService:
    """Persistence for query answerability, feedback events and gap groups."""

    def ensure_schema(self) -> None:
        with get_connection() as conn:
            self._ensure_schema(conn)
            conn.commit()

    @staticmethod
    def _ensure_schema(conn: Any) -> None:
        # Ensure the legacy gap projection exists before creating FK-dependent tables.
        # This is additive and leaves all existing gap rows intact.
        from app.services.knowledge_gap_tracker import _ensure_schema as ensure_gap_schema
        with conn.cursor() as cur:
            ensure_gap_schema(cur)

        # Existing tables are extended additively. No existing feedback or gap row is
        # deleted; event records are append-only.
        statements = [
            "ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS reason_code TEXT",
            "ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS idempotency_key TEXT",
            "ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS routing TEXT",
            "CREATE UNIQUE INDEX IF NOT EXISTS query_feedback_idempotency_idx ON query_feedback(idempotency_key) WHERE idempotency_key IS NOT NULL",
            """
            CREATE TABLE IF NOT EXISTS query_answerability (
                query_id UUID PRIMARY KEY,
                conversation_id UUID,
                corporate_kb_sufficient BOOLEAN,
                reason TEXT,
                source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                web_search_used BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_events (
                id UUID PRIMARY KEY,
                query_id UUID NOT NULL,
                conversation_id UUID,
                source TEXT NOT NULL CHECK (source IN ('automatic','user_feedback')),
                feedback_id UUID NULL,
                reason_code TEXT NOT NULL,
                answerability_reason TEXT,
                comment TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "ALTER TABLE knowledge_gap_events ADD COLUMN IF NOT EXISTS feedback_id UUID NULL",
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='knowledge_gap_events_query_id_source_key' AND conrelid='knowledge_gap_events'::regclass) THEN ALTER TABLE knowledge_gap_events DROP CONSTRAINT knowledge_gap_events_query_id_source_key; END IF; END $$",
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='knowledge_gap_events_feedback_fk' AND conrelid='knowledge_gap_events'::regclass) THEN ALTER TABLE knowledge_gap_events ADD CONSTRAINT knowledge_gap_events_feedback_fk FOREIGN KEY (feedback_id) REFERENCES query_feedback(id) ON DELETE RESTRICT; END IF; END $$",
            "CREATE UNIQUE INDEX IF NOT EXISTS knowledge_gap_events_automatic_query_idx ON knowledge_gap_events(query_id) WHERE source='automatic'",
            "CREATE UNIQUE INDEX IF NOT EXISTS knowledge_gap_events_feedback_idx ON knowledge_gap_events(feedback_id) WHERE feedback_id IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS knowledge_gap_events_query_idx ON knowledge_gap_events(query_id, created_at DESC)",
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_event_items (
                event_id UUID NOT NULL REFERENCES knowledge_gap_events(id) ON DELETE RESTRICT,
                gap_id BIGINT NOT NULL REFERENCES knowledge_gaps(id) ON DELETE RESTRICT,
                resolved_query TEXT,
                source_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                similarity REAL,
                PRIMARY KEY(event_id, gap_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS quality_issues (
                id UUID PRIMARY KEY,
                feedback_id UUID NOT NULL UNIQUE REFERENCES query_feedback(id) ON DELETE RESTRICT,
                query_id UUID NOT NULL,
                issue_code TEXT NOT NULL,
                comment TEXT,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','in_review','resolved','dismissed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS quality_issues_status_created_idx ON quality_issues(status, created_at DESC)",
            "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS resolved_by TEXT",
            "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS owner_comment TEXT",
            "ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS resolved_by TEXT",
            "ALTER TABLE quality_issues ADD COLUMN IF NOT EXISTS owner_comment TEXT",
            """
            CREATE TABLE IF NOT EXISTS quality_issue_status_history (
                id BIGSERIAL PRIMARY KEY,
                issue_id UUID NOT NULL REFERENCES quality_issues(id) ON DELETE RESTRICT,
                old_status TEXT,
                new_status TEXT NOT NULL,
                author TEXT,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_status_history (
                id BIGSERIAL PRIMARY KEY,
                gap_id BIGINT NOT NULL REFERENCES knowledge_gaps(id) ON DELETE RESTRICT,
                old_status TEXT,
                new_status TEXT NOT NULL,
                author TEXT,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_groups (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                representative_query TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'candidate'
                    CHECK (status IN ('candidate','open','in_review','resolved','dismissed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                resolved_at TIMESTAMPTZ NULL
            )
            """,
            "ALTER TABLE knowledge_gap_groups ADD COLUMN IF NOT EXISTS confirmed_by TEXT",
            "ALTER TABLE knowledge_gap_groups ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ NULL",
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_group_members (
                group_id BIGINT NOT NULL REFERENCES knowledge_gap_groups(id) ON DELETE RESTRICT,
                gap_id BIGINT NOT NULL REFERENCES knowledge_gaps(id) ON DELETE RESTRICT,
                similarity REAL NOT NULL,
                assignment_source TEXT NOT NULL CHECK (assignment_source IN ('candidate','owner_confirmed')),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                removed_at TIMESTAMPTZ NULL,
                removed_by TEXT NULL,
                removal_reason TEXT NULL,
                PRIMARY KEY(group_id, gap_id)
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS knowledge_gap_group_members_active_gap_idx ON knowledge_gap_group_members(gap_id) WHERE removed_at IS NULL",
            "CREATE INDEX IF NOT EXISTS knowledge_gap_group_status_idx ON knowledge_gap_groups(status, updated_at DESC)",
            "CREATE TABLE IF NOT EXISTS knowledge_gap_cluster_suggestion_history (id BIGSERIAL PRIMARY KEY, gap_id BIGINT NOT NULL REFERENCES knowledge_gaps(id) ON DELETE RESTRICT, suggested_cluster_id UUID NOT NULL, similarity_score DOUBLE PRECISION, reason TEXT NOT NULL, author TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
            """
            CREATE TABLE IF NOT EXISTS knowledge_gap_group_operations (
                idempotency_key TEXT PRIMARY KEY,
                group_id BIGINT NOT NULL REFERENCES knowledge_gap_groups(id) ON DELETE RESTRICT,
                payload_hash TEXT NOT NULL,
                result JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
        ]
        for statement in statements:
            conn.execute(statement)

    def _query_context(self, conn: Any, query_id: str) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT q.conversation_id, q.raw_question, q.resolved_query, q.intent,
                   q.resolved_entities, q.confidence, q.depends_on_message_id,
                   u.id, u.content, a.sources
            FROM conversation_query_context q
            LEFT JOIN LATERAL (
                SELECT id, content FROM chat_messages
                WHERE query_id=q.query_id AND role='user'
                ORDER BY created_at DESC, id DESC LIMIT 1
            ) u ON TRUE
            LEFT JOIN LATERAL (
                SELECT sources FROM chat_messages
                WHERE query_id=q.query_id AND role='assistant'
                ORDER BY created_at DESC, id DESC LIMIT 1
            ) a ON TRUE
            WHERE q.query_id=%s
            """,
            (query_id,),
        ).fetchone()
        if row:
            if row[9] is None:
                raise ValueError("query_id найден, но сохранённый ответ ассистента отсутствует")
            return {
                "conversation_id": str(row[0]) if row[0] else None,
                "raw_question": str(row[1] or row[8] or ""),
                "resolved_query": str(row[2] or ""),
                "intent": str(row[3] or ""),
                "entities": _json(row[4], {}),
                "confidence": float(row[5] or 0.0),
                "previous_message_id": str(row[6]) if row[6] else None,
                "source_message_id": str(row[7]) if row[7] else None,
                "sources": _json(row[9], []),
            }
        # Older/edited conversations may have chat messages without a context row.
        row = conn.execute(
            """
            SELECT u.conversation_id, u.content, u.id, a.sources
            FROM chat_messages a JOIN chat_messages u
              ON u.query_id=a.query_id AND u.conversation_id=a.conversation_id AND u.role='user'
            WHERE a.query_id=%s AND a.role='assistant'
            ORDER BY a.created_at DESC LIMIT 1
            """,
            (query_id,),
        ).fetchone()
        if not row:
            raise ValueError("query_id не найден или у него нет сохранённого ответа")
        return {
            "conversation_id": str(row[0]), "raw_question": str(row[1] or ""),
            "resolved_query": str(row[1] or ""), "intent": "legacy",
            "entities": {}, "confidence": None, "previous_message_id": None,
            "source_message_id": str(row[2]), "sources": _json(row[3], []),
        }

    def persist_query_result(self, result: dict[str, Any], raw_question: str) -> dict[str, Any]:
        """Persist answerability and one automatic event per insufficient query_id."""
        query_id = str(result.get("query_id") or "")
        conversation_id = str(result.get("conversation_id") or "") or None
        if not query_id or not result.get("query_context"):
            return {
                "query": {}, "answerability": {"status": "not_applicable"},
                "gap": {"created": False, "source": None},
                "tracking_status": "skipped",
            }

        review = result.get("answer_review_diagnostics") or {}
        evidence = review.get("source_evidence_check") or {}
        context = result.get("query_context") or {}
        is_clarification = bool(context.get("clarification_required")) or result.get("status") == "clarification_required"
        sufficient_value = evidence.get("wiki_strong_match")
        facet_coverage = evidence.get("facet_coverage") or []
        facet_flags = [bool(item.get("wiki_sufficient")) for item in facet_coverage if isinstance(item, dict)]
        reasons = result.get("web_search_decision_reasons") or evidence.get("web_search_decision_reasons") or {}
        reason_text = " ".join(str(value) for value in reasons.values()).casefold()
        fresh_guidance_gap = "fresh_clinical_guidance" in reason_text or "not_verified_externally" in reason_text
        if is_clarification:
            sufficient = None
        elif facet_flags:
            sufficient = all(facet_flags) and not fresh_guidance_gap
        elif sufficient_value is not None:
            sufficient = bool(sufficient_value) and not fresh_guidance_gap
        else:
            sufficient = None
        answerability_reason = "; ".join(f"{key}: {value}" for key, value in reasons.items())[:2000]
        if not answerability_reason:
            answerability_reason = str(
                evidence.get("reason")
                or evidence.get("note")
                or ("clarification_required" if is_clarification else "answerability_not_reported")
            )
        response_sources = result.get("sources") or []
        source_ids = [
            str(item.get("source_id")) for item in response_sources
            if isinstance(item, dict) and item.get("source_id")
            and item.get("source_type", "wiki") == "wiki"
        ]
        web_search_used = bool(result.get("web_search_used"))

        with get_connection() as conn:
            self._ensure_schema(conn)
            ctx = self._query_context(conn, query_id)
            conn.execute(
                """
                INSERT INTO query_answerability
                    (query_id, conversation_id, corporate_kb_sufficient, reason, source_ids, web_search_used)
                VALUES (%s,%s::uuid,%s,%s,%s,%s)
                ON CONFLICT(query_id) DO UPDATE SET
                    corporate_kb_sufficient=EXCLUDED.corporate_kb_sufficient,
                    reason=EXCLUDED.reason, source_ids=EXCLUDED.source_ids,
                    web_search_used=EXCLUDED.web_search_used, updated_at=NOW()
                """,
                (query_id, conversation_id, sufficient, answerability_reason, Jsonb(source_ids), web_search_used),
            )
            gap_ids: list[int] = []
            event_id: str | None = None
            if sufficient is False and not is_clarification:
                rows = conn.execute(
                    "SELECT id FROM knowledge_gaps WHERE last_query_id=%s::uuid ORDER BY id",
                    (query_id,),
                ).fetchall()
                gap_ids = [int(row[0]) for row in rows]
                if not gap_ids:
                    # Retry the tracker once if RAG's primary write failed. This path is
                    # only used after a completed Answerability Check, never on DB/LLM errors.
                    try:
                        KnowledgeGapTracker().record_gap(
                            query=ctx["resolved_query"] or raw_question,
                            reason=answerability_reason[:200],
                            conversation_id=conversation_id, query_id=query_id,
                            wiki_candidates=[], source="automatic",
                        )
                    except Exception:
                        logger.exception("Retrying automatic knowledge-gap persistence failed")
                    rows = conn.execute(
                        "SELECT id FROM knowledge_gaps WHERE last_query_id=%s::uuid ORDER BY id",
                        (query_id,),
                    ).fetchall()
                    gap_ids = [int(row[0]) for row in rows]
                if gap_ids:
                    reason_code = _reason_code(reasons, facet_flags)
                    event_id = self._upsert_gap_event(
                        conn, query_id=query_id, conversation_id=conversation_id,
                        source="automatic", reason_code=reason_code,
                        answerability_reason=answerability_reason,
                        comment=None, gap_ids=gap_ids,
                        resolved_query=ctx["resolved_query"] or raw_question,
                        source_ids=source_ids,
                    )
            conn.commit()

        if sufficient is False and gap_ids:
            try:
                self.suggest_groups_for_gap_ids(gap_ids)
            except Exception:
                # A suggestion failure must never roll back or hide the underlying gap.
                logger.exception("Knowledge-gap group suggestion failed")
        return {
            "query": {
                "raw_question": ctx["raw_question"] or raw_question,
                "resolved_query": ctx["resolved_query"] or result.get("resolved_query"),
                "confidence": ctx["confidence"],
                "source_message_id": ctx["source_message_id"],
                "previous_message_id": ctx["previous_message_id"],
                "entities": ctx["entities"],
                "intent": ctx["intent"],
            },
            "answerability": {
                "corporate_kb_sufficient": sufficient,
                "reason": answerability_reason,
                "source_ids": source_ids,
                "web_search_used": web_search_used,
            },
            "gap": {
                "registered": bool(event_id), "created": bool(event_id), "id": event_id,
                "gap_ids": gap_ids, "source": "automatic" if event_id else None,
            },
            "tracking_status": (
                "failed" if sufficient is False and not event_id else "persisted"
            ),
        }

    def _upsert_gap_event(
        self, conn: Any, *, query_id: str, conversation_id: str | None,
        source: str, reason_code: str, answerability_reason: str | None,
        comment: str | None, gap_ids: list[int], resolved_query: str,
        source_ids: list[str], feedback_id: str | None = None,
    ) -> str:
        event_id = uuid.uuid4()
        if source == "automatic":
            conn.execute(
                """
                INSERT INTO knowledge_gap_events
                    (id, query_id, conversation_id, source, reason_code, answerability_reason, comment)
                VALUES (%s,%s::uuid,%s::uuid,'automatic',%s,%s,%s)
                ON CONFLICT (query_id) WHERE source='automatic' DO NOTHING
                """,
                (event_id, query_id, conversation_id, reason_code, answerability_reason, comment),
            )
            row = conn.execute(
                "SELECT id FROM knowledge_gap_events WHERE query_id=%s::uuid AND source='automatic' FOR UPDATE",
                (query_id,),
            ).fetchone()
        else:
            if not feedback_id:
                raise ValueError("feedback_id обязателен для события user_feedback")
            conn.execute(
                """
                INSERT INTO knowledge_gap_events
                    (id, query_id, conversation_id, source, feedback_id, reason_code, answerability_reason, comment)
                VALUES (%s,%s::uuid,%s::uuid,'user_feedback',%s::uuid,%s,%s,%s)
                ON CONFLICT (feedback_id) WHERE feedback_id IS NOT NULL DO NOTHING
                """,
                (event_id, query_id, conversation_id, feedback_id, reason_code, answerability_reason, comment),
            )
            row = conn.execute(
                "SELECT id FROM knowledge_gap_events WHERE feedback_id=%s::uuid FOR UPDATE",
                (feedback_id,),
            ).fetchone()
        if not row:
            raise RuntimeError("Не удалось сохранить событие пробела БЗ")
        event_id = str(row[0])
        for gap_id in gap_ids:
            conn.execute(
                """
                INSERT INTO knowledge_gap_event_items(event_id, gap_id, resolved_query, source_ids)
                VALUES (%s::uuid,%s,%s,%s)
                ON CONFLICT(event_id,gap_id) DO NOTHING
                """,
                (event_id, gap_id, resolved_query[:2000], Jsonb(source_ids)),
            )
        return event_id

    def submit_feedback(
        self, *, query_id: str, rating: str, reason_code: str | None,
        comment: str | None, idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if rating not in {"positive", "negative"}:
            raise ValueError("rating должен быть positive или negative")
        if rating == "negative" and reason_code not in FEEDBACK_CODES:
            raise ValueError("Для отрицательной оценки требуется допустимый reason_code")
        if rating == "positive" and reason_code is not None:
            raise ValueError("Положительная оценка не должна содержать reason_code")
        try:
            query_uuid = str(uuid.UUID(query_id))
        except ValueError as exc:
            raise ValueError("Некорректный query_id") from exc

        # Feedback comments can contain identifiers copied from a patient record.
        # Keep the operational note useful while applying the same minimisation used
        # before embedding and indexing a gap question.
        safe_comment = _privacy_safe_query(comment) if comment else None
        payload = json.dumps(
            {"query_id": query_uuid, "rating": rating, "reason_code": reason_code, "comment": safe_comment},
            ensure_ascii=False, sort_keys=True,
        )
        if idempotency_key and len(idempotency_key) > 200:
            raise ValueError("idempotency_key не должен превышать 200 символов")
        idem = idempotency_key or ("auto:" + hashlib.sha256(payload.encode("utf-8")).hexdigest())
        routing = (
            "knowledge_gap" if reason_code in GAP_FEEDBACK_CODES
            else "quality_issue" if rating == "negative" else "none"
        )

        with get_connection() as conn:
            self._ensure_schema(conn)
            ctx = self._query_context(conn, query_uuid)  # server-side query_id validation
            new_feedback_id = uuid.uuid4()
            conn.execute(
                """
                INSERT INTO query_feedback(id, query_id, rating, comment, reason_code, idempotency_key, routing)
                VALUES (%s,%s::uuid,%s,%s,%s,%s,%s)
                ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
                """,
                (new_feedback_id, query_uuid, rating, safe_comment, reason_code, idem, routing),
            )
            row = conn.execute(
                "SELECT id, rating, reason_code, comment, routing FROM query_feedback WHERE idempotency_key=%s",
                (idem,),
            ).fetchone()
            if not row:
                raise RuntimeError("Не удалось сохранить feedback")
            if row[1] != rating or row[2] != reason_code or row[3] != safe_comment or row[4] != routing:
                raise ValueError("Этот idempotency_key уже использован с другим содержимым")
            feedback_id = str(row[0])
            issue_id = None
            if routing == "quality_issue":
                new_issue_id = uuid.uuid4()
                conn.execute(
                    """
                    INSERT INTO quality_issues(id, feedback_id, query_id, issue_code, comment)
                    VALUES (%s,%s::uuid,%s::uuid,%s,%s)
                    ON CONFLICT(feedback_id) DO NOTHING
                    """,
                    (new_issue_id, feedback_id, query_uuid, reason_code, safe_comment),
                )
                issue = conn.execute(
                    "SELECT id FROM quality_issues WHERE feedback_id=%s::uuid", (feedback_id,)
                ).fetchone()
                issue_id = str(issue[0]) if issue else None
            conn.commit()

        feedback_event_id = None
        gap_ids: list[int] = []
        if routing == "knowledge_gap":
            with get_connection() as conn:
                self._ensure_schema(conn)
                existing = conn.execute(
                    """
                    SELECT DISTINCT gi.gap_id
                    FROM knowledge_gap_event_items gi
                    JOIN knowledge_gap_events e ON e.id=gi.event_id
                    WHERE e.query_id=%s::uuid AND e.source='automatic'
                    ORDER BY gi.gap_id
                    """, (query_uuid,),
                ).fetchall()
                gap_ids = [int(r[0]) for r in existing]
                if not gap_ids:
                    # Reuse an already recorded automatic gap even if its event
                    # projection was not persisted; do not mutate its source.
                    existing = conn.execute(
                        "SELECT id FROM knowledge_gaps WHERE last_query_id=%s::uuid ORDER BY id",
                        (query_uuid,),
                    ).fetchall()
                    gap_ids = [int(r[0]) for r in existing]
                conn.commit()
            if not gap_ids:
                ok = KnowledgeGapTracker().record_gap(
                    query=ctx["resolved_query"] or ctx["raw_question"],
                    reason=f"user_feedback:{reason_code}",
                    conversation_id=ctx["conversation_id"], query_id=query_uuid,
                    wiki_candidates=ctx["sources"], source="user_feedback",
                )
                if not ok:
                    raise RuntimeError("Feedback сохранён, но пробел БЗ не удалось зарегистрировать")
                with get_connection() as conn:
                    rows = conn.execute(
                        "SELECT id FROM knowledge_gaps WHERE last_query_id=%s::uuid ORDER BY id",
                        (query_uuid,),
                    ).fetchall()
                    gap_ids = [int(r[0]) for r in rows]
            if not gap_ids:
                raise RuntimeError("Feedback сохранён, но связанный пробел БЗ не найден")
            with get_connection() as conn:
                self._ensure_schema(conn)
                feedback_event_id = self._upsert_gap_event(
                    conn, query_id=query_uuid, conversation_id=ctx["conversation_id"],
                    source="user_feedback", feedback_id=feedback_id,
                    reason_code=reason_code or "no_knowledge_base_answer",
                    answerability_reason=f"user_feedback:{reason_code}", comment=safe_comment,
                    gap_ids=gap_ids, resolved_query=ctx["resolved_query"] or ctx["raw_question"],
                    source_ids=[str(s.get("source_id")) for s in ctx["sources"]
                                if isinstance(s, dict) and s.get("source_id")],
                )
                conn.commit()
            try:
                self.suggest_groups_for_gap_ids(gap_ids)
            except Exception:
                logger.exception("Knowledge-gap group suggestion after feedback failed")
        return {
            "status": "saved", "feedback_id": feedback_id,
            "feedback_event_id": feedback_event_id, "gap_ids": gap_ids,
            "quality_issue_id": issue_id, "routing": routing,
            "idempotency_key": idem,
        }

    def list_gaps(
        self, *, status: str | None = None, source: str | None = None,
        reason_code: str | None = None, date_from: date | None = None,
        date_to: date | None = None, sort: str = "recent", limit: int = 500,
    ) -> list[dict[str, Any]]:
        if status and status not in GAP_STATUSES:
            raise ValueError("Недопустимый status")
        if source and source not in {"automatic", "user_feedback"}:
            raise ValueError("Недопустимый source")
        if sort not in {"recent", "frequent", "oldest"}:
            raise ValueError("Недопустимый sort")
        limit = max(1, min(1000, int(limit)))
        where, params = [], []
        if status:
            where.append("g.status=%s"); params.append(status)
        if source:
            where.append("EXISTS (SELECT 1 FROM knowledge_gap_event_items ei JOIN knowledge_gap_events e ON e.id=ei.event_id WHERE ei.gap_id=g.id AND e.source=%s)"); params.append(source)
        if reason_code:
            where.append("EXISTS (SELECT 1 FROM knowledge_gap_event_items ei JOIN knowledge_gap_events e ON e.id=ei.event_id WHERE ei.gap_id=g.id AND e.reason_code=%s)"); params.append(reason_code)
        if date_from:
            where.append("g.first_seen_at >= %s"); params.append(date_from)
        if date_to:
            where.append("g.first_seen_at < (%s::date + INTERVAL '1 day')"); params.append(date_to)
        order = {"recent": "g.last_seen_at DESC", "frequent": "g.occurrence_count DESC, g.last_seen_at DESC", "oldest": "g.first_seen_at ASC"}[sort]
        sql = f"""
            SELECT g.id, g.sample_query, g.normalized_query, g.reason, g.status, g.source,
                   g.first_seen_at, g.updated_at, g.resolved_at, g.last_conversation_id,
                   g.last_query_id, g.occurrence_count, g.resolved_by, g.owner_comment,
                   q.raw_question, q.resolved_query, q.confidence, q.depends_on_message_id,
                   latest.reason_code, latest.source, latest.answerability_reason,
                   latest.id, latest.source_ids,
                   user_message.id,
                   (SELECT COUNT(DISTINCT ei.event_id) FROM knowledge_gap_event_items ei WHERE ei.gap_id=g.id),
                   g.cluster_id, g.suggested_cluster_id, g.cluster_match_type, g.similarity_score,
                   (SELECT COUNT(DISTINCT related.id) FROM knowledge_gaps related
                    WHERE related.id<>g.id AND (
                        related.suggested_cluster_id=g.cluster_id
                        OR (g.suggested_cluster_id IS NOT NULL AND related.suggested_cluster_id=g.suggested_cluster_id)
                        OR related.cluster_id=g.suggested_cluster_id
                    )) AS suggested_merge_count,
                   f.id, f.rating, f.comment,
                   (SELECT json_agg(json_build_object('id', c.id, 'author', c.author, 'body', c.body, 'createdAt', c.created_at) ORDER BY c.created_at, c.id)
                      FROM knowledge_gap_comments c WHERE c.gap_id = g.id)
            FROM knowledge_gaps g
            LEFT JOIN conversation_query_context q ON q.query_id=g.last_query_id
            LEFT JOIN LATERAL (
                SELECT e.id, e.reason_code, e.source, e.answerability_reason, ei.source_ids
                FROM knowledge_gap_event_items ei JOIN knowledge_gap_events e ON e.id=ei.event_id
                WHERE ei.gap_id=g.id ORDER BY e.created_at DESC LIMIT 1
            ) latest ON TRUE
            LEFT JOIN LATERAL (
                SELECT id FROM chat_messages
                WHERE query_id=g.last_query_id AND role='user'
                ORDER BY created_at DESC, id DESC LIMIT 1
            ) user_message ON TRUE
            LEFT JOIN LATERAL (
                SELECT id, rating, comment
                FROM query_feedback
                WHERE query_id = g.last_query_id
                ORDER BY created_at DESC
                LIMIT 1
            ) f ON TRUE
            {('WHERE ' + ' AND '.join(where)) if where else ''}
            ORDER BY {order} LIMIT %s
        """
        params.append(limit)
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(sql, params).fetchall()
        output = []
        for r in rows:
            output.append({
                "id": int(r[0]), "queryId": str(r[10]) if r[10] else "",
                "conversationId": str(r[9]) if r[9] else "",
                "sourceMessageId": str(r[23]) if r[23] else "", "source": r[19] or r[5],
                "status": r[4], "rawQuestion": r[14] or r[1],
                "resolvedQuery": r[15] or r[2],
                "reason": r[18] or "no_knowledge_base_answer",
                "answerabilityReason": r[20] or r[3], "confidence": r[16],
                "previousMessageId": str(r[17]) if r[17] else None,
                "sourceIds": _json(r[22], []), "occurrenceCount": int(r[11]),
                "eventCount": int(r[24] or 0), "ownerComment": r[13] or "",
                "clusterId": str(r[25]) if r[25] else None,
                "suggestedClusterId": str(r[26]) if r[26] else None,
                "clusterMatchType": str(r[27] or "unassigned"),
                "similarityScore": float(r[28]) if r[28] is not None else None,
                "suggestedMergeCount": int(r[29] or 0),
                "feedback": (
                    {
                        "id": str(r[30]),
                        "rating": r[31],
                        "comment": (r[32] or "").strip(),
                    }
                    if r[30] is not None
                    else None
                ),
                "comments": r[33] if isinstance(r[33], list) else [],
                "webSearchUsed": False,
                "resolvedBy": r[12], "createdAt": r[6].isoformat(),
                "updatedAt": r[7].isoformat(),
                **({"resolvedAt": r[8].isoformat()} if r[8] else {}),
            })
        return output

    def list_gap_events(self, gap_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT e.id, e.query_id, e.conversation_id, e.source, e.feedback_id, e.reason_code,
                       e.answerability_reason, e.comment, e.created_at,
                       i.resolved_query, i.source_ids
                FROM knowledge_gap_event_items i JOIN knowledge_gap_events e ON e.id=i.event_id
                WHERE i.gap_id=%s ORDER BY e.created_at DESC
                """, (gap_id,),
            ).fetchall()
        return [{
            "id": str(r[0]), "queryId": str(r[1]), "conversationId": str(r[2]) if r[2] else None,
            "source": r[3], "feedbackId": str(r[4]) if r[4] else None,
            "reasonCode": r[5], "answerabilityReason": r[6],
            "comment": r[7], "createdAt": r[8].isoformat(),
            "resolvedQuery": r[9], "sourceIds": _json(r[10], []),
        } for r in rows]

    def list_gap_status_history(self, gap_id: int) -> list[dict[str, Any]]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT old_status,new_status,author,note,created_at
                FROM knowledge_gap_status_history WHERE gap_id=%s
                ORDER BY created_at,id
                """, (gap_id,),
            ).fetchall()
        return [{
            "oldStatus": r[0], "newStatus": r[1], "author": r[2],
            "note": r[3], "createdAt": r[4].isoformat(),
        } for r in rows]

    def update_gap_status(self, gap_id: int, status: str, *, note: str | None, author: str | None) -> bool:
        if status not in GAP_STATUSES:
            raise ValueError("Недопустимый статус пробела")
        with get_connection() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT status FROM knowledge_gaps WHERE id=%s FOR UPDATE", (gap_id,)).fetchone()
            if not row:
                return False
            old_status = str(row[0])
            conn.execute(
                """
                UPDATE knowledge_gaps SET status=%s, updated_at=NOW(),
                    resolved_at=CASE WHEN %s IN ('resolved','dismissed') THEN NOW() ELSE NULL END,
                    resolved_by=CASE WHEN %s IN ('resolved','dismissed') THEN %s ELSE NULL END,
                    owner_comment=COALESCE(%s, owner_comment)
                WHERE id=%s
                """, (status, status, status, author, note, gap_id),
            )
            conn.execute(
                "INSERT INTO knowledge_gap_status_history(gap_id,old_status,new_status,author,note) VALUES (%s,%s,%s,%s,%s)",
                (gap_id, old_status, status, author, note),
            )
            self._refresh_groups_for_gap(conn, gap_id)
            conn.commit()
        return True

    def suggest_groups_for_gap_ids(self, gap_ids: list[int]) -> int:
        """Create candidate group suggestions only; never auto-confirm a membership."""
        if not gap_ids:
            return 0
        from app.core.config import get_settings
        threshold = float(getattr(get_settings(), "knowledge_gap_review_threshold", 0.80))
        if not 0.0 <= threshold <= 1.0:
            threshold = 0.90
        from pgvector import Vector
        created = 0
        with get_connection() as conn:
            self._ensure_schema(conn)
            for gap_id in gap_ids:
                current = conn.execute(
                    "SELECT sample_query, embedding, status FROM knowledge_gaps WHERE id=%s",
                    (gap_id,),
                ).fetchone()
                if not current or current[1] is None or current[2] in {"resolved", "dismissed"}:
                    continue
                already = conn.execute(
                    "SELECT 1 FROM knowledge_gap_group_members WHERE gap_id=%s AND removed_at IS NULL LIMIT 1",
                    (gap_id,),
                ).fetchone()
                if already:
                    continue
                nearest = conn.execute(
                    """
                    SELECT g.id, g.sample_query, 1-(g.embedding <=> %s) AS similarity,
                           gm.group_id, gg.status
                    FROM knowledge_gaps g
                    LEFT JOIN knowledge_gap_group_members gm ON gm.gap_id=g.id AND gm.removed_at IS NULL
                    LEFT JOIN knowledge_gap_groups gg ON gg.id=gm.group_id
                    WHERE g.id<>%s AND g.embedding IS NOT NULL
                      AND g.status IN ('open','in_review')
                      AND (gm.group_id IS NULL OR gg.status='candidate')
                      AND NOT EXISTS (
                        SELECT 1 FROM knowledge_gap_group_members rejected_neighbour
                        WHERE rejected_neighbour.gap_id=g.id
                          AND rejected_neighbour.removed_at IS NOT NULL
                          AND rejected_neighbour.assignment_source='candidate'
                      )
                      AND NOT EXISTS (
                        SELECT 1
                        FROM knowledge_gap_group_members a
                        JOIN knowledge_gap_group_members b ON a.group_id=b.group_id
                        WHERE a.gap_id=%s AND b.gap_id=g.id
                          AND (a.removed_at IS NOT NULL OR b.removed_at IS NOT NULL)
                      )
                    ORDER BY g.embedding <=> %s LIMIT 1
                    """,
                    (Vector(current[1]), gap_id, gap_id, Vector(current[1])),
                ).fetchone()
                if not nearest or float(nearest[2]) < threshold:
                    continue
                other_id, other_query, similarity, other_group, other_group_status = nearest
                if other_group is not None:
                    if other_group_status != "candidate":
                        continue
                    # Prefer the highest-similarity candidate group; attach only as a
                    # proposal, preserving owner approval as the only confirmation.
                    conn.execute(
                        "INSERT INTO knowledge_gap_group_members(group_id,gap_id,similarity,assignment_source) VALUES (%s,%s,%s,'candidate') ON CONFLICT(group_id,gap_id) DO NOTHING",
                        (other_group, gap_id, float(similarity)),
                    )
                else:
                    cur = conn.execute(
                        "INSERT INTO knowledge_gap_groups(title,representative_query,status) VALUES (%s,%s,'candidate') RETURNING id",
                        (str(other_query)[:250], str(other_query)[:2000]),
                    )
                    group_id = int(cur.fetchone()[0])
                    conn.execute(
                        "INSERT INTO knowledge_gap_group_members(group_id,gap_id,similarity,assignment_source) VALUES (%s,%s,1.0,'candidate'),(%s,%s,%s,'candidate')",
                        (group_id, int(other_id), group_id, gap_id, float(similarity)),
                    )
                created += 1
            conn.commit()
        return created

    def _backfill_candidate_groups(self, limit: int = 1000) -> int:
        """Materialize owner-review groups for any sufficiently similar stored gaps.

        Do not depend on legacy cluster flags: older gaps can have good embeddings
        without ever having received ``review_candidate`` metadata. Only pairs that
        meet the configured cosine-similarity threshold are selected. Previously
        detached pairs remain excluded by the membership-history check below and
        by ``suggest_groups_for_gap_ids``.
        """
        from app.core.config import get_settings

        limit = max(1, min(5000, int(limit)))
        threshold = float(getattr(get_settings(), "knowledge_gap_review_threshold", 0.80))
        if not 0.0 <= threshold <= 1.0:
            threshold = 0.90
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT g.id
                FROM knowledge_gaps g
                WHERE g.embedding IS NOT NULL
                  AND g.status IN ('open','in_review')
                  AND NOT EXISTS (
                    SELECT 1 FROM knowledge_gap_group_members active_member
                    WHERE active_member.gap_id=g.id AND active_member.removed_at IS NULL
                  )
                  AND EXISTS (
                    SELECT 1
                    FROM knowledge_gaps neighbour
                    LEFT JOIN knowledge_gap_group_members neighbour_member
                      ON neighbour_member.gap_id=neighbour.id
                     AND neighbour_member.removed_at IS NULL
                    LEFT JOIN knowledge_gap_groups neighbour_group
                      ON neighbour_group.id=neighbour_member.group_id
                    WHERE neighbour.id<>g.id
                      AND neighbour.embedding IS NOT NULL
                      AND neighbour.status IN ('open','in_review')
                      AND (neighbour_member.group_id IS NULL OR neighbour_group.status='candidate')
                      AND 1-(neighbour.embedding <=> g.embedding) >= %s
                      AND NOT EXISTS (
                        SELECT 1
                        FROM knowledge_gap_group_members old_a
                        JOIN knowledge_gap_group_members old_b
                          ON old_a.group_id=old_b.group_id
                        WHERE old_a.gap_id=g.id
                          AND old_b.gap_id=neighbour.id
                          AND (old_a.removed_at IS NOT NULL OR old_b.removed_at IS NOT NULL)
                      )
                  )
                ORDER BY g.id
                LIMIT %s
                """,
                (threshold, limit),
            ).fetchall()
            gap_ids = [int(row[0]) for row in rows]
            conn.commit()
        return self.suggest_groups_for_gap_ids(gap_ids) if gap_ids else 0

    def list_groups(
        self, *, status: str | None = None, limit: int = 500, gap_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if status and status not in {"candidate", "open", "in_review", "resolved", "dismissed"}:
            raise ValueError("Недопустимый статус группы")
        limit = max(1, min(1000, int(limit)))
        if gap_id is not None and gap_id < 1:
            raise ValueError("gap_id должен быть положительным")
        self._backfill_candidate_groups()
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT
                    g.id,
                    g.title,
                    g.representative_query,
                    g.status,
                    g.created_at,
                    g.updated_at,
                    g.resolved_at,
                    COUNT(m.gap_id) FILTER (
                        WHERE m.removed_at IS NULL
                    ) AS active_members,
                    g.confirmed_by,
                    g.confirmed_at
                FROM knowledge_gap_groups g
                LEFT JOIN knowledge_gap_group_members m
                    ON m.group_id = g.id
                WHERE (%s::text IS NULL OR g.status = %s::text)
                  AND (
                    %s::bigint IS NULL
                    OR EXISTS (
                        SELECT 1
                        FROM knowledge_gap_group_members AS gap_filter
                        WHERE gap_filter.group_id = g.id
                          AND gap_filter.gap_id = %s::bigint
                          AND gap_filter.removed_at IS NULL
                    )
                  )
                GROUP BY g.id
                ORDER BY
                    CASE WHEN g.status = 'candidate' THEN 1 ELSE 0 END,
                    g.updated_at DESC
                LIMIT %s
                """,
                (status, status, gap_id, gap_id, limit),
            ).fetchall()
            result = []
            for r in rows:
                members = self._group_members(conn, int(r[0]))
                if len(members) < 2:
                    continue
                result.append({
                    "id": int(r[0]), "title": r[1], "representativeQuery": r[2],
                    "status": r[3], "activeMemberCount": int(r[7]),
                    "createdAt": r[4].isoformat(), "updatedAt": r[5].isoformat(),
                    "resolvedAt": r[6].isoformat() if r[6] else None,
                    "confirmedBy": r[8], "confirmedAt": r[9].isoformat() if r[9] else None,
                    "members": members,
                })
        return result

    @staticmethod
    def _group_members(conn: Any, group_id: int) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT m.gap_id,g.sample_query,g.status,g.occurrence_count,g.first_seen_at,g.last_seen_at,
                   m.similarity,m.assignment_source,m.removed_at,m.removed_by,m.removal_reason
            FROM knowledge_gap_group_members m JOIN knowledge_gaps g ON g.id=m.gap_id
            WHERE m.group_id=%s ORDER BY m.removed_at NULLS FIRST,g.occurrence_count DESC
            """, (group_id,),
        ).fetchall()
        return [{
            "gapId": int(r[0]), "question": r[1], "status": r[2],
            "occurrenceCount": int(r[3]), "firstSeenAt": r[4].isoformat(),
            "lastSeenAt": r[5].isoformat(), "similarity": float(r[6]),
            "assignmentSource": r[7], "removedAt": r[8].isoformat() if r[8] else None,
            "removedBy": r[9], "removalReason": r[10],
        } for r in rows]

    def get_group(self, group_id: int) -> dict[str, Any] | None:
        groups = self.list_groups(limit=1000)
        return next((group for group in groups if group["id"] == group_id), None)

    def confirm_group(self, group_id: int, *, member_ids: list[int] | None, author: str | None) -> dict[str, Any]:
        with get_connection() as conn:
            self._ensure_schema(conn)
            group = conn.execute("SELECT status FROM knowledge_gap_groups WHERE id=%s FOR UPDATE", (group_id,)).fetchone()
            if not group:
                raise ValueError("Группа не найдена")
            if group[0] != "candidate":
                raise ValueError("Подтверждать можно только группу-кандидат")
            candidates = conn.execute(
                "SELECT gap_id FROM knowledge_gap_group_members WHERE group_id=%s AND removed_at IS NULL ORDER BY gap_id FOR UPDATE",
                (group_id,),
            ).fetchall()
            all_ids = [int(r[0]) for r in candidates]
            selected = sorted(set(member_ids if member_ids is not None else all_ids))
            if len(selected) < 2 or not set(selected).issubset(set(all_ids)):
                raise ValueError("Для подтверждения выберите минимум два участника из предложения")
            for gap_id in all_ids:
                if gap_id not in selected:
                    conn.execute(
                        "UPDATE knowledge_gap_group_members SET removed_at=NOW(),removed_by=%s,removal_reason='not_selected_on_confirmation' WHERE group_id=%s AND gap_id=%s AND removed_at IS NULL",
                        (author, group_id, gap_id),
                    )
            conn.execute(
                "UPDATE knowledge_gap_group_members SET assignment_source='owner_confirmed' WHERE group_id=%s AND gap_id=ANY(%s) AND removed_at IS NULL",
                (group_id, selected),
            )
            conn.execute(
                "UPDATE knowledge_gap_groups SET status='open',confirmed_by=%s,confirmed_at=NOW(),updated_at=NOW() WHERE id=%s",
                (author, group_id),
            )
            conn.commit()
        return self.get_group(group_id) or {"id": group_id, "status": "open"}

    def detach_member(self, group_id: int, gap_id: int, *, reason: str, author: str | None) -> dict[str, Any]:
        if not reason.strip():
            raise ValueError("Укажите причину отвязки")
        with get_connection() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                "UPDATE knowledge_gap_group_members SET removed_at=NOW(),removed_by=%s,removal_reason=%s WHERE group_id=%s AND gap_id=%s AND removed_at IS NULL",
                (author, reason[:1000], group_id, gap_id),
            )
            if cur.rowcount == 0:
                raise ValueError("Активная связь участника с группой не найдена")
            remaining = conn.execute(
                "SELECT COUNT(*) FROM knowledge_gap_group_members WHERE group_id=%s AND removed_at IS NULL",
                (group_id,),
            ).fetchone()[0]
            if remaining < 2:
                conn.execute("UPDATE knowledge_gap_groups SET status='dismissed',updated_at=NOW() WHERE id=%s", (group_id,))
            else:
                self._refresh_group(conn, group_id)
            conn.commit()
        return self.get_group(group_id) or {"id": group_id, "activeMemberCount": remaining}

    def detach_cluster_suggestion(
        self, gap_id: int, *, reason: str, author: str | None,
    ) -> dict[str, Any]:
        """Reject a legacy review_candidate link without deleting the gap or cluster."""
        if not reason or not reason.strip():
            raise ValueError("Для отвязки от кластера укажите причину")
        with get_connection() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT suggested_cluster_id,similarity_score,cluster_match_type "
                "FROM knowledge_gaps WHERE id=%s FOR UPDATE",
                (gap_id,),
            ).fetchone()
            if not row:
                raise ValueError("Пробел не найден")
            suggested_cluster_id, similarity, match_type = row
            if suggested_cluster_id is None or match_type != "review_candidate":
                conn.commit()
                return {"gapId": gap_id, "status": "not_attached"}
            conn.execute(
                """
                INSERT INTO knowledge_gap_cluster_suggestion_history
                    (gap_id,suggested_cluster_id,similarity_score,reason,author)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (gap_id, suggested_cluster_id, similarity, reason.strip()[:1000], author),
            )
            conn.execute(
                """
                UPDATE knowledge_gaps
                SET suggested_cluster_id=NULL, similarity_score=NULL,
                    cluster_match_type='detached', updated_at=NOW()
                WHERE id=%s
                """,
                (gap_id,),
            )
            conn.commit()
        return {
            "gapId": gap_id,
            "status": "detached",
            "previousSuggestedClusterId": str(suggested_cluster_id),
            "previousSimilarity": float(similarity) if similarity is not None else None,
        }

    def resolve_group(
        self, group_id: int, *, member_ids: list[int] | None,
        note: str, author: str | None, idempotency_key: str,
    ) -> dict[str, Any]:
        if not note.strip():
            raise ValueError("Для массового закрытия обязателен комментарий")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key обязателен")
        payload = json.dumps({"group_id": group_id, "member_ids": member_ids, "note": note, "author": author}, ensure_ascii=False, sort_keys=True)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with get_connection() as conn:
            self._ensure_schema(conn)
            existing = conn.execute(
                "SELECT group_id,payload_hash,result FROM knowledge_gap_group_operations WHERE idempotency_key=%s FOR UPDATE",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if int(existing[0]) != group_id or existing[1] != payload_hash:
                    raise ValueError("idempotency_key уже использован для другой операции")
                return _json(existing[2], {})
            group = conn.execute("SELECT status FROM knowledge_gap_groups WHERE id=%s FOR UPDATE", (group_id,)).fetchone()
            if not group or group[0] not in {"open", "in_review"}:
                raise ValueError("Закрывать можно только подтвержденную активную группу")
            active = conn.execute(
                "SELECT gap_id FROM knowledge_gap_group_members WHERE group_id=%s AND removed_at IS NULL ORDER BY gap_id FOR UPDATE",
                (group_id,),
            ).fetchall()
            all_ids = [int(r[0]) for r in active]
            selected = sorted(set(member_ids if member_ids is not None else all_ids))
            if not selected or not set(selected).issubset(set(all_ids)):
                raise ValueError("Выберите активных участников этой группы")
            for gap_id in selected:
                old = conn.execute("SELECT status FROM knowledge_gaps WHERE id=%s FOR UPDATE", (gap_id,)).fetchone()
                if not old:
                    continue
                conn.execute(
                    "UPDATE knowledge_gaps SET status='resolved',updated_at=NOW(),resolved_at=NOW(),resolved_by=%s,owner_comment=%s WHERE id=%s",
                    (author, note[:2000], gap_id),
                )
                conn.execute(
                    "INSERT INTO knowledge_gap_status_history(gap_id,old_status,new_status,author,note) VALUES (%s,%s,'resolved',%s,%s)",
                    (gap_id, old[0], author, note[:2000]),
                )
            self._refresh_group(conn, group_id)
            result = {"status": "completed", "group_id": group_id, "resolved_count": len(selected), "resolved_gap_ids": selected}
            conn.execute(
                "INSERT INTO knowledge_gap_group_operations(idempotency_key,group_id,payload_hash,result) VALUES (%s,%s,%s,%s)",
                (idempotency_key, group_id, payload_hash, Jsonb(result)),
            )
            conn.commit()
        return result

    def _refresh_groups_for_gap(self, conn: Any, gap_id: int) -> None:
        rows = conn.execute(
            "SELECT group_id FROM knowledge_gap_group_members WHERE gap_id=%s AND removed_at IS NULL",
            (gap_id,),
        ).fetchall()
        for row in rows:
            self._refresh_group(conn, int(row[0]))

    def _refresh_group(self, conn: Any, group_id: int) -> None:
        rows = conn.execute(
            "SELECT g.status FROM knowledge_gap_group_members m JOIN knowledge_gaps g ON g.id=m.gap_id WHERE m.group_id=%s AND m.removed_at IS NULL",
            (group_id,),
        ).fetchall()
        statuses = [str(r[0]) for r in rows]
        status = _group_status(statuses)
        resolved_at = "NOW()" if status in {"resolved", "dismissed"} else "NULL"
        conn.execute(
            f"UPDATE knowledge_gap_groups SET status=%s,updated_at=NOW(),resolved_at={resolved_at} WHERE id=%s",
            (status, group_id),
        )

    def list_quality_issues(
        self, *, status: str | None = None, issue_code: str | None = None, limit: int = 500,
    ) -> list[dict[str, Any]]:
        allowed = {"open", "in_review", "resolved", "dismissed"}
        if status and status not in allowed:
            raise ValueError("Недопустимый статус quality issue")
        limit = max(1, min(1000, int(limit)))
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """
                SELECT i.id,i.query_id,i.issue_code,i.comment,i.status,i.created_at,i.updated_at,
                       i.resolved_by,i.owner_comment,q.raw_question,q.resolved_query
                FROM quality_issues i
                LEFT JOIN conversation_query_context q ON q.query_id=i.query_id
                WHERE (%s IS NULL OR i.status=%s) AND (%s IS NULL OR i.issue_code=%s)
                ORDER BY i.created_at DESC LIMIT %s
                """, (status, status, issue_code, issue_code, limit),
            ).fetchall()
        return [{
            "id": str(r[0]), "queryId": str(r[1]), "issueCode": r[2], "comment": r[3],
            "status": r[4], "createdAt": r[5].isoformat(), "updatedAt": r[6].isoformat(),
            "resolvedBy": r[7], "ownerComment": r[8],
            "rawQuestion": r[9], "resolvedQuery": r[10],
        } for r in rows]

    def update_quality_issue(
        self, issue_id: str, status: str, *, note: str | None, author: str | None,
    ) -> bool:
        if status not in {"open", "in_review", "resolved", "dismissed"}:
            raise ValueError("Недопустимый статус quality issue")
        try:
            issue_uuid = str(uuid.UUID(issue_id))
        except ValueError as exc:
            raise ValueError("Некорректный issue_id") from exc
        with get_connection() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT status FROM quality_issues WHERE id=%s::uuid FOR UPDATE", (issue_uuid,)
            ).fetchone()
            if not row:
                return False
            conn.execute(
                """
                UPDATE quality_issues SET status=%s,updated_at=NOW(),
                    resolved_by=CASE WHEN %s IN ('resolved','dismissed') THEN %s ELSE NULL END,
                    owner_comment=COALESCE(%s,owner_comment)
                WHERE id=%s::uuid
                """, (status, status, author, note, issue_uuid),
            )
            conn.execute(
                "INSERT INTO quality_issue_status_history(issue_id,old_status,new_status,author,note) VALUES (%s::uuid,%s,%s,%s,%s)",
                (issue_uuid, row[0], status, author, note),
            )
            conn.commit()
        return True

    def metrics(self, *, date_from: date | None = None, date_to: date | None = None) -> dict[str, Any]:
        where, params = [], []
        if date_from:
            where.append("created_at >= %s"); params.append(date_from)
        if date_to:
            where.append("created_at < (%s::date + INTERVAL '1 day')"); params.append(date_to)
        clause = "WHERE " + " AND ".join(where) if where else ""
        with get_connection() as conn:
            self._ensure_schema(conn)
            total = conn.execute(
                f"SELECT COUNT(*) FROM conversation_query_context {clause}", params
            ).fetchone()[0]
            insufficient = conn.execute(
                f"SELECT COUNT(*) FROM query_answerability {clause} AND corporate_kb_sufficient=FALSE" if clause else "SELECT COUNT(*) FROM query_answerability WHERE corporate_kb_sufficient=FALSE",
                params,
            ).fetchone()[0]
            gaps = conn.execute(
                f"SELECT source,reason_code,COUNT(*) FROM knowledge_gap_events {clause} GROUP BY source,reason_code",
                params,
            ).fetchall()
            feedback = conn.execute(
                f"SELECT COALESCE(reason_code,'none'),COUNT(*) FROM query_feedback {clause} GROUP BY reason_code",
                params,
            ).fetchall()
            negatives = conn.execute(
                f"SELECT COUNT(*) FROM query_feedback {clause} AND rating='negative'" if clause else "SELECT COUNT(*) FROM query_feedback WHERE rating='negative'",
                params,
            ).fetchone()[0]
            quality = conn.execute(
                f"SELECT COUNT(*) FROM quality_issues {clause}" if clause else "SELECT COUNT(*) FROM quality_issues",
                params,
            ).fetchone()[0]
            avg_close = conn.execute(
                "SELECT AVG(EXTRACT(EPOCH FROM (resolved_at-first_seen_at))/3600.0) FROM knowledge_gaps WHERE resolved_at IS NOT NULL"
            ).fetchone()[0]
            repeat = conn.execute("SELECT COUNT(*) FROM knowledge_gaps WHERE occurrence_count>1").fetchone()[0]
            web = conn.execute(
                f"SELECT COUNT(*) FROM query_answerability {clause} AND web_search_used=TRUE" if clause else "SELECT COUNT(*) FROM query_answerability WHERE web_search_used=TRUE",
                params,
            ).fetchone()[0]
        return {
            "query_count": int(total), "insufficient_kb_count": int(insufficient),
            "insufficient_kb_rate": (float(insufficient) / total) if total else 0.0,
            "gap_events": [{"source": r[0], "reason_code": r[1], "count": int(r[2])} for r in gaps],
            "negative_feedback_count": int(negatives), "quality_issue_count": int(quality),
            "feedback_reasons": [{"reason_code": r[0], "count": int(r[1])} for r in feedback],
            "average_hours_to_close": float(avg_close) if avg_close is not None else None,
            "repeat_gap_count": int(repeat), "web_search_used_count": int(web),
        }

    def feedback_for_query_ids(self, query_ids: list[str]) -> dict[str, dict[str, Any]]:
        values = [str(value) for value in query_ids if value]
        if not values:
            return {}
        with get_connection() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                "SELECT DISTINCT ON (query_id) query_id,rating,reason_code,comment,created_at FROM query_feedback WHERE query_id=ANY(%s::uuid[]) ORDER BY query_id,created_at DESC",
                (values,),
            ).fetchall()
        return {str(r[0]): {"rating": r[1], "reason_code": r[2], "comment": r[3], "created_at": r[4].isoformat()} for r in rows}
