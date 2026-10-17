from __future__ import annotations

import re
import uuid
from typing import Any

from pgvector import Vector

from app.core.config import get_settings
from app.db.database import get_connection
from app.services.embeddings import get_embedding_client
from app.services.ingestion import NAMESPACE, ParsedDocument, build_chunks, path_context


class KnowledgeRepository:
    def reindex(self, documents: list[ParsedDocument]) -> dict[str, int]:
        embedding_client = get_embedding_client()
        prepared = [(doc, build_chunks(doc)) for doc in documents]
        all_texts = [chunk["embedding_text"] for _, chunks in prepared for chunk in chunks]
        vectors = embedding_client.embed(all_texts)
        vector_iter = iter(vectors)

        with get_connection() as conn:
            conn.execute("TRUNCATE knowledge_documents CASCADE")
            document_count = 0
            chunk_count = 0
            for doc, chunks in prepared:
                doc_id = uuid.uuid5(NAMESPACE, doc.source_key)
                conn.execute(
                    """
                    INSERT INTO knowledge_documents
                    (id, source_key, filename, title, wiki_path, path_segments, source_url, content_hash)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (doc_id, doc.source_key, doc.filename, doc.title, doc.wiki_path,
                     doc.path_segments, doc.source_url, doc.content_hash),
                )
                document_count += 1
                normalized_path = path_context(doc.wiki_path)
                for chunk in chunks:
                    embedding = next(vector_iter)
                    chunk_id = uuid.uuid5(NAMESPACE, f"{doc.source_key}:{chunk['chunk_index']}")
                    conn.execute(
                        """
                        INSERT INTO knowledge_chunks
                        (id, document_id, chunk_index, section, content, embedding_text, embedding, search_vector, path_vector)
                        VALUES (
                            %s,%s,%s,%s,%s,%s,%s,
                            setweight(to_tsvector('russian', %s),'A') ||
                            setweight(to_tsvector('russian', %s),'A') ||
                            setweight(to_tsvector('russian', %s),'A') ||
                            setweight(to_tsvector('russian', %s),'B'),
                            to_tsvector('russian', %s)
                        )
                        """,
                        (chunk_id, doc_id, chunk["chunk_index"], chunk["section"], chunk["content"],
                         chunk["embedding_text"], embedding, doc.title, normalized_path,
                         chunk["section"], chunk["content"], normalized_path),
                    )
                    chunk_count += 1
            conn.commit()
        return {"documents": document_count, "chunks": chunk_count}

    @staticmethod
    def _fts_or_query(query: str) -> str:
        tokens = re.findall(r"[а-яёa-z0-9]+", query.lower())
        return " OR ".join(dict.fromkeys(tokens[:24]))

    def hybrid_search(self, query: str, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        query_vector = Vector(embedding)
        lexical_query = self._fts_or_query(query)
        with get_connection() as conn:
            sql = """
            WITH search_queries AS (
                SELECT websearch_to_tsquery('russian', %(lexical_query)s) AS q
            ),
            dense AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(embedding)s) AS rnk
                FROM knowledge_chunks
                WHERE embedding IS NOT NULL
                LIMIT %(candidates)s
            ),
            lexical AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(search_vector, sq.q) DESC) AS rnk
                FROM knowledge_chunks
                CROSS JOIN search_queries sq
                WHERE numnode(sq.q) > 0 AND search_vector @@ sq.q
                ORDER BY ts_rank_cd(search_vector, sq.q) DESC
                LIMIT %(candidates)s
            ),
            path_hits AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(path_vector, sq.q) DESC) AS rnk
                FROM knowledge_chunks
                CROSS JOIN search_queries sq
                WHERE numnode(sq.q) > 0 AND path_vector @@ sq.q
                ORDER BY ts_rank_cd(path_vector, sq.q) DESC
                LIMIT %(candidates)s
            ),
            merged AS (
                SELECT
                    COALESCE(dense.id, lexical.id, path_hits.id) AS id,
                    COALESCE(%(dw)s / (60.0 + dense.rnk), 0) +
                    COALESCE(%(lw)s / (60.0 + lexical.rnk), 0) +
                    COALESCE(%(pw)s / (60.0 + path_hits.rnk), 0) AS rrf_score,
                    dense.rnk AS dense_rank,
                    lexical.rnk AS lexical_rank,
                    path_hits.rnk AS path_rank
                FROM dense
                FULL OUTER JOIN lexical ON dense.id = lexical.id
                FULL OUTER JOIN path_hits ON COALESCE(dense.id, lexical.id) = path_hits.id
            )
            SELECT merged.rrf_score, merged.dense_rank, merged.lexical_rank, merged.path_rank,
                   c.id AS chunk_id, c.document_id, c.section, c.content, c.embedding_text,
                   d.title, d.wiki_path, d.path_segments, d.source_url,
                   1 - (c.embedding <=> %(embedding)s) AS dense_similarity
            FROM merged
            JOIN knowledge_chunks c ON c.id = merged.id
            JOIN knowledge_documents d ON d.id = c.document_id
            ORDER BY merged.rrf_score DESC
            LIMIT %(top_k)s
            """
            cursor = conn.execute(sql, {
                "embedding": query_vector,
                "lexical_query": lexical_query,
                "candidates": max(top_k, get_settings().search_candidates),
                "top_k": top_k,
                "dw": get_settings().dense_rrf_weight,
                "lw": get_settings().lexical_rrf_weight,
                "pw": get_settings().path_rrf_weight,
            })
            rows = cursor.fetchall()
            columns = [d.name for d in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id,title,wiki_path,path_segments,source_url,content_hash,created_at,updated_at FROM knowledge_documents WHERE id=%s",
                (document_id,),
            ).fetchone()
        if not row:
            return None
        keys = ["id", "title", "wiki_path", "path_segments", "source_url", "content_hash", "created_at", "updated_at"]
        result = dict(zip(keys, row))
        result["id"] = str(result["id"])
        return result

    def save_feedback(self, query_id: str, rating: str, comment: str | None) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO query_feedback (id,query_id,rating,comment) VALUES (%s,%s,%s,%s)",
                (uuid.uuid4(), uuid.UUID(query_id), rating, comment),
            )
            conn.commit()

    def document_count(self) -> int:
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()
        return int(row[0]) if row else 0

    def get_index_archive_hash(self) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT archive_hash FROM knowledge_index_state WHERE id = 1"
            ).fetchone()
        return str(row[0]) if row else None

    def save_index_archive_hash(self, archive_hash: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_index_state (id, archive_hash)
                VALUES (1, %s)
                ON CONFLICT (id)
                DO UPDATE SET archive_hash = EXCLUDED.archive_hash, updated_at = NOW()
                """,
                (archive_hash,),
            )
            conn.commit()


class ConversationRepository:
    def create(self, title: str | None = None) -> str:
        conversation_id = uuid.uuid4()
        with get_connection() as conn:
            conn.execute("INSERT INTO conversations (id,title) VALUES (%s,%s)", (conversation_id, title))
            conn.commit()
        return str(conversation_id)

    def get(self, conversation_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute("SELECT id,title,created_at,updated_at FROM conversations WHERE id=%s", (conversation_id,)).fetchone()
        if not row:
            return None
        return {"id": str(row[0]), "title": row[1], "created_at": row[2].isoformat(), "updated_at": row[3].isoformat()}

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute("SELECT id,title,created_at,updated_at FROM conversations ORDER BY updated_at DESC LIMIT %s", (limit,)).fetchall()
        return [{"id": str(r[0]), "title": r[1], "created_at": r[2].isoformat(), "updated_at": r[3].isoformat()} for r in rows]

    def update_title(self, conversation_id: str, title: str) -> None:
        with get_connection() as conn:
            conn.execute("UPDATE conversations SET title=%s,updated_at=NOW() WHERE id=%s", (title[:120], conversation_id))
            conn.commit()

    def messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with get_connection() as conn:
            # Select the newest messages first so a long-running chat does not get
            # stuck with its initial topic when the configured history limit is reached.
            rows = conn.execute(
                "SELECT id,role,content,query_id,sources,created_at FROM chat_messages "
                "WHERE conversation_id=%s ORDER BY created_at DESC, id DESC LIMIT %s",
                (conversation_id, limit),
            ).fetchall()
        # The newest window is sent to callers in chronological order.
        rows = list(reversed(rows))
        return [{
            "id": str(r[0]), "role": r[1], "content": r[2],
            "query_id": str(r[3]) if r[3] else None,
            "sources": r[4] if isinstance(r[4], list) else [],
            "created_at": r[5].isoformat(),
        } for r in rows]
