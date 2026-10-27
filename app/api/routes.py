from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.db.database import get_connection, init_db
from app.db.repository import ConversationRepository, KnowledgeRepository
from app.schemas.api import CreateConversationRequest, FeedbackRequest, QueryRequest, SearchRequest
from app.services.ingestion import parse_zip
from app.services.memory import ConversationMemory
from app.services.rag import RagService
from app.services.manual_web_search import manual_web_answer

router = APIRouter(prefix="/api/v1")


class ManualWebSearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=3000)
    limit: int = Field(default=5, ge=1, le=8)


@router.post("/web-search")
def web_search(request: ManualWebSearchRequest) -> dict:
    try:
        return manual_web_answer(request.question, request.limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ошибка веб-поиска: {exc}") from exc


@router.get("/health")
def health() -> dict:
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "database": "ok"}
    except Exception as exc:
        return {"status": "degraded", "database": f"error: {exc}"}


@router.post("/knowledge/reindex")
def reindex(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается ZIP-архив с Markdown-файлами")
    try:
        stats = KnowledgeRepository().reindex(parse_zip(file.file.read()))
        return {"status": "completed", **stats}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка индексации: {exc}") from exc


@router.post("/search")
def search(request: SearchRequest) -> dict:
    try:
        service = RagService()
        docs = service.search(request.query, request.patient.model_dump() if request.patient else None, request.top_k)
        return {"results": service._retrieval_view(docs)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {exc}") from exc


@router.post("/query")
def query(request: QueryRequest) -> dict:
    try:
        return RagService().answer(
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
    return ConversationRepository().get(conversation_id) or {
        "id": conversation_id,
        "title": request.title,
    }


@router.get("/conversations")
def list_conversations(limit: int = 50) -> dict:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit должен быть от 1 до 100")
    return {"conversations": ConversationRepository().list(limit)}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    repo = ConversationRepository()
    conversation = repo.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return {**conversation, "messages": repo.messages(conversation_id)}


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, limit: int = 100) -> dict:
    repo = ConversationRepository()
    if not repo.get(conversation_id):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=400, detail="limit должен быть от 1 до 500")
    return {"messages": repo.messages(conversation_id, limit)}


@router.get("/knowledge/{document_id}")
def get_document(document_id: str) -> dict:
    result = KnowledgeRepository().get_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return result


@router.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    try:
        KnowledgeRepository().save_feedback(str(request.query_id), request.rating, request.comment)
        return {"status": "saved"}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения feedback: {exc}") from exc
