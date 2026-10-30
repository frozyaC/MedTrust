import hashlib
import logging
import os
import re
from typing import Any



logger = logging.getLogger(__name__)


def _database_url() -> str | None:
    from app.core.config import get_settings

    settings = get_settings()
    for name in ("database_url", "database_dsn", "postgres_dsn", "db_url"):
        value = getattr(settings, name, None)
        if value:
            return str(value)
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_DSN")


def _normalise(value: str) -> str:
    value = (value or "").casefold().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_ENSURE_SQL = (
    """
    CREATE TABLE IF NOT EXISTS knowledge_gaps (
        id BIGSERIAL PRIMARY KEY,
        fingerprint CHAR(64) NOT NULL UNIQUE,
        normalized_query TEXT NOT NULL,
        sample_query TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        occurrence_count INTEGER NOT NULL DEFAULT 1,
        first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_conversation_id UUID NULL,
        last_query_id UUID NULL,
        wiki_candidates JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
    "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'automatic'",
    "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ NULL",
    """
    CREATE TABLE IF NOT EXISTS knowledge_gap_comments (
        id BIGSERIAL PRIMARY KEY,
        gap_id BIGINT NOT NULL REFERENCES knowledge_gaps(id) ON DELETE CASCADE,
        author TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS knowledge_gap_comments_gap_idx ON knowledge_gap_comments (gap_id, created_at)",
    # Отзывы пишет /feedback; таблица может ещё не существовать, если отзывов не было
    """
    CREATE TABLE IF NOT EXISTS query_feedback (
        id UUID PRIMARY KEY,
        query_id UUID NOT NULL,
        rating TEXT NOT NULL CHECK (rating IN ('positive', 'negative')),
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
)

# save_feedback хранит комментарий как "[reason_code] текст"
_FEEDBACK_COMMENT_RE = re.compile(r"^\[([a-z_]+)\]\s*(.*)$", re.DOTALL)

GAP_STATUSES = {"open", "in_review", "resolved", "dismissed"}
# Причины, создающие пробел; совпадает с createsGap в frontend/src/data/feedbackReasons.ts
GAP_REASON_CODES = {"no_knowledge_base_answer", "knowledge_incomplete", "knowledge_outdated"}


def _ensure_schema(cur: Any) -> None:
    for statement in _ENSURE_SQL:
        cur.execute(statement)


def _reason_code(reason: str) -> str:
    code = (reason or "").removeprefix("user_feedback:")
    return code if code in GAP_REASON_CODES else "no_knowledge_base_answer"


def _feedback_view(feedback_id: Any, rating: str, raw_comment: str | None) -> dict[str, Any]:
    comment = raw_comment or ""
    reason_code = None
    match = _FEEDBACK_COMMENT_RE.match(comment)
    if match:
        reason_code, comment = match.group(1), match.group(2)
    return {
        "id": str(feedback_id),
        "rating": rating,
        "comment": comment.strip(),
        **({"reasonCode": reason_code} if reason_code in GAP_REASON_CODES else {}),
    }


def _comment_view(row: tuple) -> dict[str, Any]:
    return {
        "id": str(row[0]),
        "author": row[1],
        "body": row[2],
        "createdAt": row[3].isoformat(),
    }


def _insert_comment(cur: Any, gap_id: int, author: str, body: str) -> dict[str, Any]:
    cur.execute(
        """
        INSERT INTO knowledge_gap_comments (gap_id, author, body)
        VALUES (%s, %s, %s)
        RETURNING id, author, body, created_at
        """,
        (gap_id, author[:200], body[:2000]),
    )
    return _comment_view(cur.fetchone())


class KnowledgeGapTracker:
    """Store a compact, deduplicated record for each uncovered query facet."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url if database_url is not None else _database_url()

    def record_gap(
        self,
        *,
        query: str,
        reason: str,
        conversation_id: str | None = None,
        query_id: str | None = None,
        wiki_candidates: list[dict[str, Any]] | None = None,
        source: str = "automatic",
    ) -> bool:
        normalized = _normalise(query)
        if not normalized or not self.database_url:
            return False
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        evidence = [
            {
                "title": str(item.get("title") or "")[:250],
                "path": str(item.get("wiki_path") or item.get("path") or "")[:500],
                "section": str(item.get("section") or "")[:250],
            }
            for item in (wiki_candidates or [])[:5]
        ]
        try:
            import psycopg
            from psycopg.types.json import Jsonb

            with psycopg.connect(self.database_url, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    _ensure_schema(cur)
                    cur.execute(
                        """
                        INSERT INTO knowledge_gaps (
                            fingerprint, normalized_query, sample_query, reason,
                            last_conversation_id, last_query_id, wiki_candidates, source
                        ) VALUES (%s, %s, %s, %s, %s::uuid, %s::uuid, %s, %s)
                        ON CONFLICT (fingerprint) DO UPDATE SET
                            sample_query = EXCLUDED.sample_query,
                            reason = EXCLUDED.reason,
                            occurrence_count = knowledge_gaps.occurrence_count + 1,
                            last_seen_at = NOW(),
                            updated_at = NOW(),
                            status = CASE WHEN EXCLUDED.source = 'user_feedback'
                                               AND knowledge_gaps.status IN ('resolved', 'dismissed')
                                          THEN 'open' ELSE knowledge_gaps.status END,
                            resolved_at = CASE WHEN EXCLUDED.source = 'user_feedback'
                                                    AND knowledge_gaps.status IN ('resolved', 'dismissed')
                                               THEN NULL ELSE knowledge_gaps.resolved_at END,
                            source = CASE WHEN EXCLUDED.source = 'user_feedback'
                                          THEN 'user_feedback' ELSE knowledge_gaps.source END,
                            last_conversation_id = EXCLUDED.last_conversation_id,
                            last_query_id = EXCLUDED.last_query_id,
                            wiki_candidates = CASE
                                WHEN EXCLUDED.wiki_candidates = '[]'::jsonb
                                THEN knowledge_gaps.wiki_candidates
                                ELSE EXCLUDED.wiki_candidates END
                        """,
                        (
                            fingerprint, normalized, query[:2000], reason[:200],
                            conversation_id, query_id, Jsonb(evidence), source,
                        ),
                    )
            return True
        except Exception:
            logger.exception("Failed to persist MedTrust knowledge gap")
            return False

    def list_gaps(self) -> list[dict[str, Any]]:
        """Return gaps in the camelCase shape expected by the admin frontend."""
        if not self.database_url:
            return []
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    """
                    SELECT g.id, g.sample_query, g.normalized_query, g.reason, g.status, g.source,
                           g.first_seen_at, g.updated_at, g.resolved_at,
                           g.last_conversation_id, g.last_query_id, g.wiki_candidates,
                           f.id, f.rating, f.comment
                    FROM knowledge_gaps g
                    LEFT JOIN LATERAL (
                        SELECT id, rating, comment
                        FROM query_feedback
                        WHERE query_id = g.last_query_id
                        ORDER BY created_at DESC
                        LIMIT 1
                    ) f ON TRUE
                    ORDER BY g.first_seen_at DESC
                    LIMIT 1000
                    """
                )
                rows = cur.fetchall()
                comments: dict[int, list[dict[str, Any]]] = {}
                if rows:
                    cur.execute(
                        """
                        SELECT id, author, body, created_at, gap_id
                        FROM knowledge_gap_comments
                        WHERE gap_id = ANY(%s)
                        ORDER BY created_at, id
                        """,
                        ([r[0] for r in rows],),
                    )
                    for c in cur.fetchall():
                        comments.setdefault(c[4], []).append(_comment_view(c))
        gaps = []
        for r in rows:
            candidates = r[11] if isinstance(r[11], list) else []
            gaps.append({
                "id": str(r[0]),
                "queryId": str(r[10]) if r[10] else "",
                "conversationId": str(r[9]) if r[9] else "",
                "sourceMessageId": "",
                "source": r[5] if r[5] in ("automatic", "user_feedback") else "automatic",
                "status": r[4] if r[4] in GAP_STATUSES else "open",
                "rawQuestion": r[1],
                "resolvedQuery": r[2],
                "reason": _reason_code(r[3]),
                "answerabilityReason": r[3],
                "sourceIds": [
                    {"id": c.get("path") or str(i), "title": c.get("title") or c.get("path") or ""}
                    for i, c in enumerate(candidates)
                ],
                **({"feedback": _feedback_view(r[12], r[13], r[14])} if r[12] else {}),
                "comments": comments.get(r[0], []),
                "webSearchUsed": False,
                "createdAt": r[6].isoformat(),
                "updatedAt": r[7].isoformat(),
                **({"resolvedAt": r[8].isoformat()} if r[8] else {}),
            })
        return gaps

    def update_status(
        self, gap_id: int, status: str, note: str | None = None, author: str | None = None
    ) -> dict[str, Any] | None:
        """Change the status; a non-empty note is stored as a comment. Returns None if not found."""
        if status not in GAP_STATUSES or not self.database_url:
            return None
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    """
                    UPDATE knowledge_gaps
                    SET status = %s, updated_at = NOW(),
                        resolved_at = CASE WHEN %s IN ('resolved', 'dismissed') THEN NOW() ELSE NULL END
                    WHERE id = %s
                    """,
                    (status, status, gap_id),
                )
                if cur.rowcount == 0:
                    return None
                note = (note or "").strip()
                comment = _insert_comment(cur, gap_id, author or "Неизвестный автор", note) if note else None
                return {"status": status, **({"comment": comment} if comment else {})}

    def add_comment(self, gap_id: int, author: str, body: str) -> dict[str, Any] | None:
        """Append an owner comment to the gap. Returns None if the gap does not exist."""
        if not self.database_url:
            return None
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute("UPDATE knowledge_gaps SET updated_at = NOW() WHERE id = %s", (gap_id,))
                if cur.rowcount == 0:
                    return None
                return _insert_comment(cur, gap_id, author, body)
