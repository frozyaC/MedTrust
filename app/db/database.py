from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from app.core.config import get_settings


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id UUID PRIMARY KEY,
    source_key TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    wiki_path TEXT NOT NULL,
    path_segments TEXT[] NOT NULL,
    source_url TEXT,
    content_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    embedding_text TEXT NOT NULL,
    embedding VECTOR(1024),
    search_vector TSVECTOR NOT NULL,
    path_vector TSVECTOR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS knowledge_chunks_search_gin
    ON knowledge_chunks USING gin (search_vector);

CREATE INDEX IF NOT EXISTS knowledge_chunks_path_gin
    ON knowledge_chunks USING gin (path_vector);

CREATE INDEX IF NOT EXISTS knowledge_chunks_document_idx
    ON knowledge_chunks (document_id);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    query_id UUID,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_messages_conversation_idx
    ON chat_messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS conversation_memory (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@contextmanager
def get_connection():
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        register_vector(conn)
        yield conn


def init_db() -> None:
    settings = get_settings()
    with psycopg.connect(settings.postgres_dsn) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        register_vector(conn)
        sql = SCHEMA_SQL.replace("VECTOR(1024)", f"VECTOR({settings.embedding_dimension})")
        conn.execute(sql)
        conn.commit()
