from fastapi import APIRouter, File, HTTPException, UploadFile

from app.db.database import get_connection, init_db
from app.db.repository import ConversationRepository, KnowledgeRepository
from app.schemas.api import (
    CreateConversationRequest,
    FeedbackRequest,
    QueryRequest,
    SearchRequest,
)
from app.services.ingestion import parse_zip
from app.services.rag import RagService
from app.services.memory import ConversationMemory
from app.services.safety import QueryScopeValidator

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
        scope = QueryScopeValidator().validate(request.query)
        if not scope.allowed:
            raise HTTPException(status_code=400, detail="Запрос не относится к медицинской тематике MedTrust")
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
            str(request.conversation_id) if request.conversation_id else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка RAG: {exc}") from exc


@router.post("/conversations")
def create_conversation(request: CreateConversationRequest) -> dict:
    conversation_id = ConversationMemory().create_conversation(request.title)
    conversation = ConversationRepository().get_conversation(conversation_id)
    return conversation or {"id": conversation_id, "title": request.title}


@router.get("/conversations")
def list_conversations(limit: int = 50) -> dict:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit должен быть от 1 до 100")
    return {"conversations": ConversationRepository().list_conversations(limit)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    conversation = ConversationRepository().get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    messages = ConversationRepository().list_messages(conversation_id)
    return {**conversation, "messages": messages}


@router.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(conversation_id: str, limit: int = 100) -> dict:
    if not ConversationRepository().get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit должен быть от 1 до 500")
    return {"messages": ConversationRepository().list_messages(conversation_id, limit)}


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
