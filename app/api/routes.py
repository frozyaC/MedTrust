import logging
from datetime import date

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.db.database import get_connection, init_db
from app.db.repository import ConversationRepository, KnowledgeRepository
from app.schemas.api import (
    CreateConversationRequest,
    FeedbackRequest,
    GapCommentRequest,
    GapGroupConfirmRequest,
    GapClusterDetachRequest,
    GapGroupDetachRequest,
    GapGroupResolveRequest,
    GapStatusRequest,
    ManualWebSearchRequest,
    QueryRequest,
    QualityIssueStatusRequest,
    SearchRequest,
)
from app.services.gap_map_service import GapMapService
from app.services.ingestion import parse_zip
from app.services.knowledge_gap_tracker import GAP_REASON_CODES, KnowledgeGapTracker
from app.services.memory import ConversationMemory
from app.services.rag import RagService
from app.services.manual_web_search import manual_web_answer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _messages_with_feedback(messages: list[dict]) -> list[dict]:
    query_ids = [str(message.get("query_id")) for message in messages if message.get("query_id")]
    feedback = GapMapService().feedback_for_query_ids(query_ids)
    enriched = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "assistant" and item.get("query_id"):
            item["feedback"] = feedback.get(str(item["query_id"]))
        enriched.append(item)
    return enriched


@router.post("/web-search")
def web_search(request: ManualWebSearchRequest) -> dict:
    try:
        # Manual web search remains an external, separately requested operation.
        # This route never writes returned pages into the corporate Wiki.
        return manual_web_answer(
            request.question, request.limit,
            request.patient.model_dump(exclude_none=True) if request.patient else None,
        )
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
        result = RagService().answer(
            request.question,
            request.patient.model_dump() if request.patient else None,
            request.top_k,
            str(request.conversation_id) if request.conversation_id else None,
        )
        # Rewrite/no-conversation responses do not have a new contextualization row
        # and are deliberately excluded from the knowledge-gap lifecycle.
        if result.get("query_context"):
            try:
                result.update(GapMapService().persist_query_result(result, request.question))
            except Exception:
                # Do not discard a valid medical answer because the observability or
                # gap-projection write failed. Return an explicit tracking status.
                logger.exception("Could not persist MedTrust answerability/gap metadata")
                result["tracking_status"] = "failed"
                result["tracking_error"] = "Не удалось сохранить диагностику достаточности БЗ"
        return result
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
    return {**conversation, "messages": _messages_with_feedback(repo.messages(conversation_id))}


@router.get("/conversations/{conversation_id}/messages")
def get_messages(conversation_id: str, limit: int = 100) -> dict:
    repo = ConversationRepository()
    if not repo.get(conversation_id):
        raise HTTPException(status_code=404, detail="Диалог не найден")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=400, detail="limit должен быть от 1 до 500")
    return {"messages": _messages_with_feedback(repo.messages(conversation_id, limit))}


@router.get("/knowledge/{document_id}")
def get_document(document_id: str) -> dict:
    result = KnowledgeRepository().get_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return result

@router.get("/knowledge/{document_id}/content")
def get_document_content(document_id: str) -> dict:
    content = KnowledgeRepository().get_document_content(document_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"document_id": document_id, "content": content}


@router.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    comment = request.comment
    if request.reason_code:
        comment = f"[{request.reason_code}] {comment or ''}".strip()
    try:
        KnowledgeRepository().save_feedback(str(request.query_id), request.rating, comment)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения feedback: {exc}") from exc

    gap_recorded = False
    if (
        request.rating == "negative"
        and request.reason_code in GAP_REASON_CODES
        and request.question
    ):
        gap_recorded = KnowledgeGapTracker().record_gap(
            query=request.question,
            reason=f"user_feedback:{request.reason_code}",
            conversation_id=str(request.conversation_id) if request.conversation_id else None,
            query_id=str(request.query_id),
            wiki_candidates=ConversationRepository().answer_wiki_sources(str(request.query_id)),
            source="user_feedback",
        )
    return {"status": "saved", "gap_recorded": gap_recorded}

@router.get("/knowledge-gaps")
def list_knowledge_gaps(
    status: str | None = None,
    source: str | None = None,
    reason_code: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "recent",
    limit: int = 500,
    gap_id: int | None = None,
) -> list[dict]:
    try:
        return GapMapService().list_gaps(
            status=status, source=source, reason_code=reason_code,
            date_from=date_from, date_to=date_to, sort=sort, limit=limit,
            gap_id=gap_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not list knowledge gaps")
        raise HTTPException(status_code=500, detail="Ошибка загрузки пробелов БЗ") from exc


@router.get("/knowledge-gaps/metrics")
def knowledge_gap_metrics(date_from: date | None = None, date_to: date | None = None) -> dict:
    try:
        return GapMapService().metrics(date_from=date_from, date_to=date_to)
    except Exception as exc:
        logger.exception("Could not load knowledge-gap metrics")
        raise HTTPException(status_code=500, detail="Ошибка загрузки метрик карты пробелов") from exc


@router.get("/knowledge-gaps/{gap_id}/events")
def knowledge_gap_events(gap_id: int) -> list[dict]:
    try:
        return GapMapService().list_gap_events(gap_id)
    except Exception as exc:
        logger.exception("Could not load knowledge-gap events")
        raise HTTPException(status_code=500, detail="Ошибка загрузки истории пробела") from exc


@router.get("/knowledge-gaps/{gap_id}/history")
def knowledge_gap_status_history(gap_id: int) -> list[dict]:
    try:
        return GapMapService().list_gap_status_history(gap_id)
    except Exception as exc:
        logger.exception("Could not load knowledge-gap status history")
        raise HTTPException(status_code=500, detail="Ошибка загрузки истории статусов пробела") from exc


@router.post("/knowledge-gaps/{gap_id}/detach-cluster")
def detach_knowledge_gap_cluster_suggestion(
    gap_id: int, request: GapClusterDetachRequest,
) -> dict:
    try:
        return GapMapService().detach_cluster_suggestion(
            gap_id, reason=request.reason, author=request.author,
        )
    except ValueError as exc:
        code = 404 if "не найден" in str(exc).casefold() else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not detach legacy cluster suggestion")
        raise HTTPException(status_code=500, detail="Ошибка отвязки пробела от кластера-кандидата") from exc


@router.get("/knowledge-gaps/clusters")
def list_knowledge_gap_clusters(limit: int = 500) -> list[dict]:
    # Legacy projection retained for existing clients. New owner-managed groups are
    # exposed by /knowledge-gap-groups and never auto-confirmed by similarity.
    try:
        return KnowledgeGapTracker().list_clusters(limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки групп пробелов: {exc}") from exc


@router.patch("/knowledge-gaps/{gap_id}")
def update_knowledge_gap(gap_id: int, request: GapStatusRequest) -> dict:
    try:
        updated = GapMapService().update_gap_status(
            gap_id, request.status, note=request.note, author=request.author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not update knowledge gap")
        raise HTTPException(status_code=500, detail="Ошибка обновления пробела") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Пробел не найден")
    return {"status": request.status, "gap_id": gap_id}


@router.post("/knowledge-gaps/{gap_id}/comments")
def add_knowledge_gap_comment(gap_id: int, request: GapCommentRequest) -> dict:
    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Комментарий пуст")
    try:
        comment = KnowledgeGapTracker().add_comment(gap_id, request.author.strip(), body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения комментария: {exc}") from exc
    if not comment:
        raise HTTPException(status_code=404, detail="Пробел не найден")
    return comment


@router.get("/knowledge-gap-groups")
def list_knowledge_gap_groups(
    status: str | None = None, limit: int = 500, gap_id: int | None = None,
) -> list[dict]:
    try:
        return GapMapService().list_groups(status=status, limit=limit, gap_id=gap_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not list knowledge-gap groups")
        raise HTTPException(status_code=500, detail="Ошибка загрузки групп пробелов") from exc


@router.get("/knowledge-gap-groups/{group_id}")
def get_knowledge_gap_group(group_id: int) -> dict:
    try:
        result = GapMapService().get_group(group_id)
    except Exception as exc:
        logger.exception("Could not load knowledge-gap group")
        raise HTTPException(status_code=500, detail="Ошибка загрузки группы пробелов") from exc
    if not result:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return result


@router.post("/knowledge-gap-groups/{group_id}/confirm")
def confirm_knowledge_gap_group(group_id: int, request: GapGroupConfirmRequest) -> dict:
    try:
        return GapMapService().confirm_group(
            group_id, member_ids=request.member_ids, author=request.author,
        )
    except ValueError as exc:
        code = 404 if "не найдена" in str(exc).casefold() else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not confirm knowledge-gap group")
        raise HTTPException(status_code=500, detail="Ошибка подтверждения группы") from exc


@router.post("/knowledge-gap-groups/{group_id}/resolve")
def resolve_knowledge_gap_group(group_id: int, request: GapGroupResolveRequest) -> dict:
    try:
        return GapMapService().resolve_group(
            group_id, member_ids=request.member_ids, note=request.note,
            author=request.author, idempotency_key=request.idempotency_key,
        )
    except ValueError as exc:
        code = 404 if "не найдена" in str(exc).casefold() else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not resolve knowledge-gap group")
        raise HTTPException(status_code=500, detail="Ошибка закрытия группы пробелов") from exc


@router.post("/knowledge-gap-groups/{group_id}/members/{gap_id}/detach")
def detach_knowledge_gap_group_member(
    group_id: int, gap_id: int, request: GapGroupDetachRequest,
) -> dict:
    try:
        return GapMapService().detach_member(
            group_id, gap_id, reason=request.reason, author=request.author,
        )
    except ValueError as exc:
        code = 404 if "не найдена" in str(exc).casefold() else 409
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not detach knowledge-gap group member")
        raise HTTPException(status_code=500, detail="Ошибка отвязки элемента от группы") from exc


@router.get("/quality-issues")
def list_quality_issues(
    status: str | None = None, issue_code: str | None = None, limit: int = 500,
) -> list[dict]:
    try:
        return GapMapService().list_quality_issues(status=status, issue_code=issue_code, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not list quality issues")
        raise HTTPException(status_code=500, detail="Ошибка загрузки проблем качества") from exc


@router.patch("/quality-issues/{issue_id}")
def update_quality_issue(issue_id: str, request: QualityIssueStatusRequest) -> dict:
    try:
        updated = GapMapService().update_quality_issue(
            issue_id, request.status, note=request.note, author=request.author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not update quality issue")
        raise HTTPException(status_code=500, detail="Ошибка обновления проблемы качества") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Проблема качества не найдена")
    return {"status": request.status, "issue_id": issue_id}
