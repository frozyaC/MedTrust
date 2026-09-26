import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.db.repository import KnowledgeRepository
from app.db.database import init_db, get_connection
from app.schemas.api import FeedbackRequest, QueryRequest, SearchRequest
from app.services.embeddings import EmbeddingClient
from app.services.ingestion import parse_zip
from app.services.rag import RagService

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    db = "ok"
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:  # pragma: no cover - environment-specific
        db = f"error: {exc}"
    return {"status": "ok" if db == "ok" else "degraded", "database": db}


@router.post("/knowledge/reindex")
def reindex(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается ZIP-архив с Markdown-файлами")

    try:
        data = file.file.read()
        docs = parse_zip(data)
        init_db()
        stats = KnowledgeRepository().reindex(docs)
        return {"status": "completed", **stats}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка индексации: {exc}") from exc


@router.post("/search")
def search(request: SearchRequest) -> dict:
    try:
        service = RagService()
        docs = service.search(
            request.query,
            request.patient.model_dump() if request.patient else None,
            request.top_k,
        )
        return {
            "results": [
                {
                    "chunk_id": str(doc["chunk_id"]),
                    "document_id": str(doc["document_id"]),
                    "title": doc["title"],
                    "section": doc["section"],
                    "path": doc["wiki_path"],
                    "path_segments": doc["path_segments"],
                    "url": doc["source_url"],
                    "content": doc["content"],
                    "rrf_score": float(doc["rrf_score"]),
                    "dense_similarity": float(doc["dense_similarity"]),
                    "dense_rank": doc["dense_rank"],
                    "lexical_rank": doc["lexical_rank"],
                    "path_rank": doc["path_rank"],
                }
                for doc in docs
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {exc}") from exc


@router.post("/query")
def query(request: QueryRequest) -> dict:
    try:
        service = RagService()
        return service.answer(
            request.question,
            request.patient.model_dump() if request.patient else None,
            request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка RAG: {exc}") from exc


@router.get("/knowledge/{document_id}")
def document(document_id: str) -> dict:
    result = KnowledgeRepository().get_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return result


@router.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    try:
        KnowledgeRepository().save_feedback(
            request.query_id,
            request.rating,
            request.comment,
        )
        return {"status": "saved"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения feedback: {exc}") from exc
