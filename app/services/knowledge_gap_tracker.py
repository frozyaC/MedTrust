"""Idempotent PostgreSQL tracking for questions not covered by the local Wiki.

Tracking is best-effort: a tracker outage must never break the registrar's answer.
The table is created lazily so this patch does not require a separate migration step.
"""
from __future__ import annotations

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
                    cur.execute(
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
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO knowledge_gaps (
                            fingerprint, normalized_query, sample_query, reason,
                            last_conversation_id, last_query_id, wiki_candidates
                        ) VALUES (%s, %s, %s, %s, %s::uuid, %s::uuid, %s)
                        ON CONFLICT (fingerprint) DO UPDATE SET
                            sample_query = EXCLUDED.sample_query,
                            reason = EXCLUDED.reason,
                            occurrence_count = knowledge_gaps.occurrence_count + 1,
                            last_seen_at = NOW(),
                            last_conversation_id = EXCLUDED.last_conversation_id,
                            last_query_id = EXCLUDED.last_query_id,
                            wiki_candidates = EXCLUDED.wiki_candidates
                        """,
                        (
                            fingerprint, normalized, query[:2000], reason[:200],
                            conversation_id, query_id, Jsonb(evidence),
                        ),
                    )
            return True
        except Exception:
            logger.exception("Failed to persist MedTrust knowledge gap")
            return False
