"""Persist exact and semantically grouped MedTrust knowledge gaps.

Exact duplicates continue to use a SHA-256 fingerprint. Distinct questions are
embedded and assigned to a semantic cluster only when cosine similarity reaches
the configured automatic-merge threshold. Borderline matches are stored as
review suggestions instead of being merged automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import uuid
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# PostgreSQL advisory lock shared by all workers modifying the cluster index.
_CLUSTER_LOCK_KEY = 741_092_611


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


def _fingerprint(normalized_query: str) -> str:
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()


def _similarity_action(
    similarity: float,
    *,
    auto_threshold: float = 0.90,
    review_threshold: float = 0.80,
) -> str:
    """Return 'merge', 'review', or 'new' for a cosine similarity value."""
    if similarity >= auto_threshold:
        return "merge"
    if similarity >= review_threshold:
        return "review"
    return "new"


def _updated_centroid(
    old_embedding: Iterable[float],
    new_embedding: Iterable[float],
    old_weight: int,
    new_weight: int = 1,
) -> list[float]:
    """Incremental weighted mean of cluster centroids."""
    old = [float(value) for value in old_embedding]
    new = [float(value) for value in new_embedding]
    if not old or len(old) != len(new):
        raise ValueError("Embedding dimensions do not match")
    if old_weight < 1:
        return new
    if new_weight < 1:
        raise ValueError("new_weight must be positive")
    denominator = old_weight + new_weight
    return [((left * old_weight) + (right * new_weight)) / denominator for left, right in zip(old, new)]


_ENSURE_SQL = (
    "CREATE EXTENSION IF NOT EXISTS vector",
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
)

GAP_STATUSES = {"open", "in_review", "resolved", "dismissed"}
GAP_REASON_CODES = {"no_knowledge_base_answer", "knowledge_incomplete", "knowledge_outdated"}


def _ensure_schema(cur: Any) -> None:
    """Idempotent, lazy migration so existing installations are upgraded safely."""
    for statement in _ENSURE_SQL:
        cur.execute(statement)

    from app.core.config import get_settings

    dimension = int(get_settings().embedding_dimension)
    if dimension <= 0:
        raise ValueError("embedding_dimension must be positive")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS knowledge_gap_clusters (
            id UUID PRIMARY KEY,
            canonical_question TEXT NOT NULL,
            normalized_question TEXT NOT NULL,
            embedding VECTOR({dimension}),
            occurrence_count INTEGER NOT NULL DEFAULT 1,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cur.execute(
        f"ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS embedding VECTOR({dimension})"
    )
    cur.execute("ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS cluster_id UUID NULL")
    cur.execute("ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS suggested_cluster_id UUID NULL")
    cur.execute("ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS similarity_score DOUBLE PRECISION NULL")
    cur.execute(
        "ALTER TABLE knowledge_gaps ADD COLUMN IF NOT EXISTS cluster_match_type TEXT NOT NULL DEFAULT 'unassigned'"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_gaps_cluster_id_idx ON knowledge_gaps(cluster_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS knowledge_gaps_suggested_cluster_idx ON knowledge_gaps(suggested_cluster_id)"
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS knowledge_gaps_embedding_hnsw
        ON knowledge_gaps USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL AND cluster_id IS NOT NULL
        """
    )


def _reason_code(reason: str) -> str:
    code = (reason or "").removeprefix("user_feedback:")
    return code if code in GAP_REASON_CODES else "no_knowledge_base_answer"


class KnowledgeGapTracker:
    """Store exact gaps and group semantically similar questions."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url if database_url is not None else _database_url()

    @staticmethod
    def _settings() -> Any:
        from app.core.config import get_settings

        return get_settings()

    @staticmethod
    def _connection(database_url: str) -> Any:
        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(database_url, connect_timeout=3)
        register_vector(conn)
        return conn

    @staticmethod
    def _embed_many(texts: list[str]) -> list[list[float]]:
        from app.services.embeddings import get_embedding_client

        vectors = get_embedding_client().embed(texts)
        if len(vectors) != len(texts):
            raise ValueError("Embedding provider returned an unexpected vector count")
        dimension = int(KnowledgeGapTracker._settings().embedding_dimension)
        normalized: list[list[float]] = []
        for vector in vectors:
            values = [float(value) for value in vector]
            if len(values) != dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {dimension}, got {len(values)}"
                )
            normalized.append(values)
        return normalized

    @staticmethod
    def _thresholds() -> tuple[float, float]:
        settings = KnowledgeGapTracker._settings()
        auto_threshold = float(getattr(settings, "knowledge_gap_similarity_threshold", 0.90))
        review_threshold = float(getattr(settings, "knowledge_gap_review_threshold", 0.80))
        if not (0.0 <= review_threshold <= auto_threshold <= 1.0):
            raise ValueError(
                "knowledge gap thresholds must satisfy 0 <= review <= auto <= 1"
            )
        return auto_threshold, review_threshold

    @staticmethod
    def _evidence(wiki_candidates: list[dict[str, Any]] | None) -> list[dict[str, str]]:
        return [
            {
                "title": str(item.get("title") or "")[:250],
                "path": str(item.get("wiki_path") or item.get("path") or "")[:500],
                "section": str(item.get("section") or "")[:250],
            }
            for item in (wiki_candidates or [])[:5]
            if isinstance(item, dict)
        ]

    def _find_cluster(self, cur: Any, embedding: list[float]) -> dict[str, Any] | None:
        from pgvector import Vector

        cur.execute(
            """
            SELECT c.id, c.canonical_question, c.embedding, c.occurrence_count,
                   1 - (g.embedding <=> %s) AS similarity
            FROM knowledge_gaps g
            JOIN knowledge_gap_clusters c ON c.id=g.cluster_id
            WHERE g.embedding IS NOT NULL AND g.cluster_id IS NOT NULL
            ORDER BY g.embedding <=> %s
            LIMIT 1
            """,
            (Vector(embedding), Vector(embedding)),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "canonical_question": row[1],
            "embedding": row[2],
            "occurrence_count": int(row[3]),
            "similarity": float(row[4]),
        }

    def _assign_cluster(
        self,
        cur: Any,
        *,
        query: str,
        normalized: str,
        embedding: list[float] | None,
        existing_occurrences: int = 1,
        first_seen_at: Any | None = None,
        last_seen_at: Any | None = None,
    ) -> tuple[uuid.UUID | None, uuid.UUID | None, float | None, str]:
        """Assign a query to a cluster or create a review suggestion/new cluster."""
        if embedding is None:
            return None, None, None, "unassigned"

        from pgvector import Vector
        nearest = self._find_cluster(cur, embedding)

        auto_threshold, review_threshold = self._thresholds()
        similarity = nearest["similarity"] if nearest else None
        action = _similarity_action(
            similarity if similarity is not None else -1.0,
            auto_threshold=auto_threshold,
            review_threshold=review_threshold,
        )

        if action == "merge" and nearest and embedding is not None:
            cluster_id = nearest["id"]
            old_count = nearest["occurrence_count"]
            centroid = _updated_centroid(
                nearest["embedding"], embedding, old_count, existing_occurrences
            )
            cur.execute(
                """
                UPDATE knowledge_gap_clusters
                SET embedding=%s, occurrence_count=occurrence_count + %s,
                    first_seen_at=LEAST(first_seen_at, COALESCE(%s, NOW())),
                    last_seen_at=GREATEST(last_seen_at, COALESCE(%s, NOW()))
                WHERE id=%s
                """,
                (Vector(centroid), existing_occurrences, first_seen_at, last_seen_at, cluster_id),
            )
            return cluster_id, None, similarity, "semantic"

        cluster_id = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO knowledge_gap_clusters (
                id, canonical_question, normalized_question, embedding, occurrence_count,
                first_seen_at, last_seen_at
            ) VALUES (%s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
            """,
            (cluster_id, query[:2000], normalized, Vector(embedding) if embedding is not None else None,
             existing_occurrences, first_seen_at, last_seen_at),
        )
        if action == "review" and nearest:
            return cluster_id, nearest["id"], similarity, "review_candidate"
        return cluster_id, None, similarity, "new"

    def _touch_existing(
        self,
        cur: Any,
        *,
        fingerprint: str,
        query: str,
        reason: str,
        conversation_id: str | None,
        query_id: str | None,
        evidence: list[dict[str, str]],
        source: str,
    ) -> bool:
        from psycopg.types.json import Jsonb

        cur.execute(
            """
            UPDATE knowledge_gaps SET
                sample_query=%s,
                reason=%s,
                occurrence_count=occurrence_count + 1,
                last_seen_at=NOW(), updated_at=NOW(),
                status=CASE WHEN %s='user_feedback' AND status IN ('resolved','dismissed')
                            THEN 'open' ELSE status END,
                resolved_at=CASE WHEN %s='user_feedback' AND status IN ('resolved','dismissed')
                                 THEN NULL ELSE resolved_at END,
                source=CASE WHEN %s='user_feedback' THEN 'user_feedback' ELSE source END,
                last_conversation_id=%s::uuid,
                last_query_id=%s::uuid,
                wiki_candidates=CASE WHEN %s='[]'::jsonb THEN wiki_candidates ELSE %s END
            WHERE fingerprint=%s
            RETURNING cluster_id
            """,
            (
                query[:2000], reason[:200], source, source, source,
                conversation_id, query_id, Jsonb(evidence), Jsonb(evidence), fingerprint,
            ),
        )
        row = cur.fetchone()
        if row and row[0]:
            cur.execute(
                "UPDATE knowledge_gap_clusters SET occurrence_count=occurrence_count + 1, last_seen_at=NOW() WHERE id=%s",
                (row[0],),
            )
        return row is not None

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
        fingerprint = _fingerprint(normalized)
        evidence = self._evidence(wiki_candidates)

        try:
            # Fast path: exact duplicates retain SHA-256 deduplication and do not
            # need another embedding-provider call.
            with self._connection(self.database_url) as conn:
                with conn.cursor() as cur:
                    _ensure_schema(cur)
                    cur.execute(
                        "SELECT cluster_id FROM knowledge_gaps WHERE fingerprint=%s",
                        (fingerprint,),
                    )
                    exact = cur.fetchone()
                    if exact and exact[0]:
                        self._touch_existing(
                            cur, fingerprint=fingerprint, query=query, reason=reason,
                            conversation_id=conversation_id, query_id=query_id,
                            evidence=evidence, source=source,
                        )
                        return True

            embedding: list[float] | None = None
            if bool(getattr(self._settings(), "knowledge_gap_semantic_enabled", True)):
                try:
                    embedding = self._embed_many([normalized])[0]
                except Exception:
                    # Semantic grouping is an enhancement; exact SHA-256 tracking
                    # must continue working when the embedding provider is down.
                    logger.exception("Knowledge-gap embedding failed; using exact deduplication only")

            from pgvector import Vector
            from psycopg.types.json import Jsonb

            with self._connection(self.database_url) as conn:
                with conn.cursor() as cur:
                    _ensure_schema(cur)
                    # Serialize nearest-cluster selection + centroid update to avoid
                    # two workers creating parallel clusters for the same question.
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (_CLUSTER_LOCK_KEY,))
                    cur.execute(
                        "SELECT id, cluster_id, occurrence_count, first_seen_at, last_seen_at FROM knowledge_gaps WHERE fingerprint=%s FOR UPDATE",
                        (fingerprint,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        if existing[1]:
                            self._touch_existing(
                                cur, fingerprint=fingerprint, query=query, reason=reason,
                                conversation_id=conversation_id, query_id=query_id,
                                evidence=evidence, source=source,
                            )
                            return True
                        cluster_id, suggested_id, similarity, match_type = self._assign_cluster(
                            cur, query=query, normalized=normalized, embedding=embedding,
                            existing_occurrences=int(existing[2]),
                            first_seen_at=existing[3],
                            last_seen_at=existing[4],
                        )
                        cur.execute(
                            """
                            UPDATE knowledge_gaps SET embedding=%s, cluster_id=%s,
                                suggested_cluster_id=%s, similarity_score=%s, cluster_match_type=%s
                            WHERE fingerprint=%s
                            """,
                            (Vector(embedding) if embedding is not None else None, cluster_id,
                             suggested_id, similarity, match_type, fingerprint),
                        )
                        self._touch_existing(
                            cur, fingerprint=fingerprint, query=query, reason=reason,
                            conversation_id=conversation_id, query_id=query_id,
                            evidence=evidence, source=source,
                        )
                        return True

                    cluster_id, suggested_id, similarity, match_type = self._assign_cluster(
                        cur, query=query, normalized=normalized, embedding=embedding,
                    )
                    cur.execute(
                        """
                        INSERT INTO knowledge_gaps (
                            fingerprint, normalized_query, sample_query, reason,
                            last_conversation_id, last_query_id, wiki_candidates, source,
                            embedding, cluster_id, suggested_cluster_id, similarity_score,
                            cluster_match_type
                        ) VALUES (%s,%s,%s,%s,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            fingerprint, normalized, query[:2000], reason[:200],
                            conversation_id, query_id, Jsonb(evidence), source,
                            Vector(embedding) if embedding is not None else None,
                            cluster_id, suggested_id, similarity, match_type,
                        ),
                    )
            return True
        except Exception:
            logger.exception("Failed to persist MedTrust knowledge gap")
            return False

    def rebuild_semantic_index(self, batch_size: int = 100) -> dict[str, int]:
        """Embed and cluster legacy exact-gap rows missing semantic metadata.

        Run repeatedly until ``processed`` is smaller than ``batch_size``. This
        avoids a startup-time embedding burst on existing installations.
        """
        if not self.database_url:
            return {"processed": 0, "clustered": 0, "failed": 0}
        if not 1 <= batch_size <= 500:
            raise ValueError("batch_size must be between 1 and 500")

        try:
            with self._connection(self.database_url) as conn:
                with conn.cursor() as cur:
                    _ensure_schema(cur)
                    cur.execute(
                        """
                        SELECT id, normalized_query, sample_query, occurrence_count,
                               first_seen_at, last_seen_at
                        FROM knowledge_gaps
                        WHERE cluster_id IS NULL
                        ORDER BY first_seen_at, id
                        LIMIT %s
                        """,
                        (batch_size,),
                    )
                    rows = cur.fetchall()
            if not rows:
                return {"processed": 0, "clustered": 0, "failed": 0}

            texts = [str(row[1]) for row in rows]
            vectors = self._embed_many(texts)
            from pgvector import Vector

            clustered = 0
            with self._connection(self.database_url) as conn:
                with conn.cursor() as cur:
                    _ensure_schema(cur)
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (_CLUSTER_LOCK_KEY,))
                    for row, embedding in zip(rows, vectors):
                        gap_id, normalized, sample_query, occurrences, first_seen_at, last_seen_at = row
                        cur.execute(
                            "SELECT cluster_id FROM knowledge_gaps WHERE id=%s FOR UPDATE",
                            (gap_id,),
                        )
                        current = cur.fetchone()
                        if not current or current[0]:
                            continue
                        cluster_id, suggested_id, similarity, match_type = self._assign_cluster(
                            cur,
                            query=str(sample_query),
                            normalized=str(normalized),
                            embedding=embedding,
                            existing_occurrences=int(occurrences),
                            first_seen_at=first_seen_at,
                            last_seen_at=last_seen_at,
                        )
                        cur.execute(
                            """
                            UPDATE knowledge_gaps SET embedding=%s, cluster_id=%s,
                                suggested_cluster_id=%s, similarity_score=%s,
                                cluster_match_type=%s
                            WHERE id=%s
                            """,
                            (Vector(embedding), cluster_id, suggested_id, similarity, match_type, gap_id),
                        )
                        clustered += 1
            return {"processed": len(rows), "clustered": clustered, "failed": 0}
        except Exception:
            logger.exception("Failed to rebuild knowledge-gap semantic index")
            return {"processed": 0, "clustered": 0, "failed": batch_size}

    def list_gaps(self) -> list[dict[str, Any]]:
        """Return existing frontend fields plus semantic-cluster metadata."""
        if not self.database_url:
            return []
        with self._connection(self.database_url) as conn:
            with conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    """
                    SELECT g.id, g.sample_query, g.normalized_query, g.reason, g.status, g.source,
                           g.first_seen_at, g.updated_at, g.resolved_at,
                           g.last_conversation_id, g.last_query_id, g.wiki_candidates,
                           g.cluster_id, c.canonical_question, c.occurrence_count,
                           g.similarity_score, g.cluster_match_type,
                           g.suggested_cluster_id, sc.canonical_question
                    FROM knowledge_gaps g
                    LEFT JOIN knowledge_gap_clusters c ON c.id=g.cluster_id
                    LEFT JOIN knowledge_gap_clusters sc ON sc.id=g.suggested_cluster_id
                    ORDER BY g.first_seen_at DESC
                    LIMIT 1000
                    """
                )
                rows = cur.fetchall()

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
                "ownerComment": "",
                "webSearchUsed": False,
                "createdAt": r[6].isoformat(),
                "updatedAt": r[7].isoformat(),
                "clusterId": str(r[12]) if r[12] else None,
                "canonicalQuestion": r[13],
                "clusterOccurrenceCount": int(r[14]) if r[14] is not None else None,
                "similarityScore": float(r[15]) if r[15] is not None else None,
                "clusterMatchType": r[16] or "unassigned",
                "suggestedClusterId": str(r[17]) if r[17] else None,
                "suggestedCanonicalQuestion": r[18],
                **({"resolvedAt": r[8].isoformat()} if r[8] else {}),
            })
        return gaps

    def list_clusters(self, limit: int = 500) -> list[dict[str, Any]]:
        if not self.database_url:
            return []
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connection(self.database_url) as conn:
            with conn.cursor() as cur:
                _ensure_schema(cur)
                cur.execute(
                    """
                    SELECT c.id, c.canonical_question, c.occurrence_count,
                           c.first_seen_at, c.last_seen_at,
                           COUNT(g.id) AS distinct_questions,
                           COUNT(g.id) FILTER (WHERE g.status='open') AS open_questions,
                           COUNT(g.id) FILTER (WHERE g.status='in_review') AS in_review_questions,
                           COUNT(g.id) FILTER (WHERE g.status='resolved') AS resolved_questions,
                           COUNT(g.id) FILTER (WHERE g.status='dismissed') AS dismissed_questions,
                           (SELECT COUNT(*) FROM knowledge_gaps sg
                            WHERE sg.suggested_cluster_id=c.id) AS suggested_merges
                    FROM knowledge_gap_clusters c
                    LEFT JOIN knowledge_gaps g ON g.cluster_id=c.id
                    GROUP BY c.id
                    ORDER BY c.occurrence_count DESC, c.last_seen_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
                clusters = []
                for row in rows:
                    cur.execute(
                        """
                        SELECT id, sample_query, reason, status, occurrence_count,
                               similarity_score, cluster_match_type
                        FROM knowledge_gaps WHERE cluster_id=%s
                        ORDER BY occurrence_count DESC, last_seen_at DESC
                        LIMIT 100
                        """,
                        (row[0],),
                    )
                    members = cur.fetchall()
                    clusters.append({
                        "clusterId": str(row[0]),
                        "canonicalQuestion": row[1],
                        "occurrenceCount": int(row[2]),
                        "firstSeenAt": row[3].isoformat(),
                        "lastSeenAt": row[4].isoformat(),
                        "distinctQuestions": int(row[5]),
                        # Keep lifecycle states separate. `in_review` is unresolved,
                        # but it is not an `open` record and must not inflate that count.
                        "openQuestions": int(row[6]),
                        "inReviewQuestions": int(row[7]),
                        "resolvedQuestions": int(row[8]),
                        "dismissedQuestions": int(row[9]),
                        "unresolvedQuestions": int(row[6]) + int(row[7]),
                        "suggestedMergeCount": int(row[10]),
                        "members": [
                            {
                                "id": str(m[0]), "question": m[1], "reason": m[2],
                                "status": m[3], "occurrenceCount": int(m[4]),
                                "similarityScore": float(m[5]) if m[5] is not None else None,
                                "matchType": m[6],
                            }
                            for m in members
                        ],
                    })
        return clusters

    def update_status(self, gap_id: int, status: str) -> bool:
        if status not in GAP_STATUSES or not self.database_url:
            return False
        with self._connection(self.database_url) as conn:
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
                return cur.rowcount > 0


def _run_backfill() -> None:
    parser = argparse.ArgumentParser(description="Build semantic clusters for existing MedTrust knowledge gaps")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    tracker = KnowledgeGapTracker()
    total = 0
    while True:
        result = tracker.rebuild_semantic_index(args.batch_size)
        total += result["clustered"]
        print(result)
        if result["processed"] < args.batch_size or result["failed"]:
            break
    print({"total_clustered": total})


if __name__ == "__main__":
    _run_backfill()
