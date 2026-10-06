from typing import Any
import uuid
from pgvector import Vector
from app.db.database import get_connection
from app.services.embeddings import EmbeddingClient
from app.services.ingestion import NAMESPACE, ParsedDocument, build_chunks, path_context


class KnowledgeRepository:
    def reindex(self, documents: list[ParsedDocument]) -> dict[str, int]:
        embedding_client = EmbeddingClient()
        prepared: list[tuple[ParsedDocument, list[dict]]] = [
            (doc, build_chunks(doc)) for doc in documents
        ]
        all_chunk_texts = [chunk["embedding_text"] for _, chunks in prepared for chunk in chunks]
        vectors = embedding_client.embed(all_chunk_texts)

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
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        doc_id,
                        doc.source_key,
                        doc.filename,
                        doc.title,
                        doc.wiki_path,
                        doc.path_segments,
                        doc.source_url,
                        doc.content_hash,
                    ),
                )
                document_count += 1

                for chunk in chunks:
                    embedding = next(vector_iter)
                    chunk_id = uuid.uuid5(NAMESPACE, f"{doc.source_key}:{chunk['chunk_index']}")
                    normalized_path = path_context(doc.wiki_path)
                    conn.execute(
                        """
                        INSERT INTO knowledge_chunks
                            (id, document_id, chunk_index, section, content, embedding_text, embedding, search_vector, path_vector)
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s,
                            setweight(to_tsvector('russian', %s), 'A') ||
                            setweight(to_tsvector('russian', %s), 'A') ||
                            setweight(to_tsvector('russian', %s), 'A') ||
                            setweight(to_tsvector('russian', %s), 'B'),
                            to_tsvector('russian', %s)
                        )
                        """,
                        (
                            chunk_id,
                            doc_id,
                            chunk["chunk_index"],
                            chunk["section"],
                            chunk["content"],
                            chunk["embedding_text"],
                            embedding,
                            doc.title,
                            normalized_path,
                            chunk["section"],
                            chunk["content"],
                            normalized_path,
                        ),
                    )
                    chunk_count += 1

            conn.commit()

        return {"documents": document_count, "chunks": chunk_count}

    def hybrid_search(self, query: str, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        query_vector = Vector(embedding)
        with get_connection() as conn:
            sql = """
            WITH dense AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(embedding)s) AS rnk
                FROM knowledge_chunks
                WHERE embedding IS NOT NULL
                LIMIT %(candidates)s
            ),
            lexical AS (
                SELECT id, ROW_NUMBER() OVER (
                    ORDER BY ts_rank_cd(search_vector, plainto_tsquery('russian', %(query)s)) DESC
                ) AS rnk
                FROM knowledge_chunks
                WHERE search_vector @@ plainto_tsquery('russian', %(query)s)
                ORDER BY ts_rank_cd(search_vector, plainto_tsquery('russian', %(query)s)) DESC
                LIMIT %(candidates)s
            ),
            path_hits AS (
                SELECT id, ROW_NUMBER() OVER (
                    ORDER BY ts_rank_cd(path_vector, plainto_tsquery('russian', %(query)s)) DESC
                ) AS rnk
                FROM knowledge_chunks
                WHERE path_vector @@ plainto_tsquery('russian', %(query)s)
                ORDER BY ts_rank_cd(path_vector, plainto_tsquery('russian', %(query)s)) DESC
                LIMIT %(candidates)s
            ),
            merged AS (
                SELECT
                    COALESCE(dense.id, lexical.id, path_hits.id) AS id,
                    COALESCE(%(dense_weight)s / (60.0 + dense.rnk), 0) +
                    COALESCE(%(lexical_weight)s / (60.0 + lexical.rnk), 0) +
                    COALESCE(%(path_weight)s / (60.0 + path_hits.rnk), 0) AS rrf_score,
                    dense.rnk AS dense_rank,
                    lexical.rnk AS lexical_rank,
                    path_hits.rnk AS path_rank
                FROM dense
                FULL OUTER JOIN lexical ON dense.id = lexical.id
                FULL OUTER JOIN path_hits ON COALESCE(dense.id, lexical.id) = path_hits.id
            )
            SELECT
                merged.rrf_score,
                merged.dense_rank,
                merged.lexical_rank,
                merged.path_rank,
                c.id AS chunk_id,
                c.document_id,
                c.section,
                c.content,
                c.embedding_text,
                d.title,
                d.wiki_path,
                d.path_segments,
                d.source_url,
                1 - (c.embedding <=> %(embedding)s) AS dense_similarity
            FROM merged
            JOIN knowledge_chunks c ON c.id = merged.id
            JOIN knowledge_documents d ON d.id = c.document_id
            ORDER BY merged.rrf_score DESC
            LIMIT %(top_k)s
            """
            params = {
                "embedding": query_vector,
                "query": query,
                "candidates": max(top_k, 20),
                "top_k": top_k,
                "dense_weight": self._weight("dense"),
                "lexical_weight": self._weight("lexical"),
                "path_weight": self._weight("path"),
            }
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            columns = [desc.name for desc in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    @staticmethod
    def _weight(kind: str) -> float:
        from app.core.config import get_settings
        settings = get_settings()
        return {
            "dense": settings.dense_rrf_weight,
            "lexical": settings.lexical_rrf_weight,
            "path": settings.path_rrf_weight,
        }[kind]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, title, wiki_path, path_segments, source_url, content_hash, created_at, updated_at
                FROM knowledge_documents
                WHERE id = %s
                """,
                (document_id,),
            ).fetchone()
            if not row:
                return None
            columns = [
                "id", "title", "wiki_path", "path_segments", "source_url", "content_hash", "created_at", "updated_at"
            ]
            result = dict(zip(columns, row))
            result["id"] = str(result["id"])
            return result

    def save_feedback(self, query_id: str, rating: str, comment: str | None) -> None:
        # MVP: keep feedback in a small table created lazily.
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_feedback (
                    id UUID PRIMARY KEY,
                    query_id UUID NOT NULL,
                    rating TEXT NOT NULL,
                    comment TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "INSERT INTO query_feedback (id, query_id, rating, comment) VALUES (%s, %s, %s, %s)",
                (uuid.uuid4(), uuid.UUID(query_id), rating, comment),
            )
            conn.commit()
