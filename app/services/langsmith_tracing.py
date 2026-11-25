"""Opt-in, privacy-aware tracing helpers for LangSmith.

Tracing is disabled by default. When enabled, medical question/context text is
still omitted unless LANGSMITH_TRACE_CONTENT=true. Patient-context JSON and
conversation history are always redacted from prompt traces.
"""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Callable
from types import SimpleNamespace

from app.core.config import get_settings

logger = logging.getLogger(__name__)
try:
    _settings = get_settings()
except Exception as exc:  # Do not make optional tracing break imports in unit-test/tooling contexts.
    logger.debug("LangSmith settings are unavailable during module import: %s", exc)
    _settings = SimpleNamespace(
        langsmith_tracing=False, langsmith_api_key="",
        langsmith_endpoint="https://api.smith.langchain.com",
        langsmith_project="MedTrust", langsmith_trace_content=False,
        gigachat_model="GigaChat-2",
    )
_TRACE_ENABLED = bool(_settings.langsmith_tracing and _settings.langsmith_api_key.strip())
_TRACE_CONTENT = bool(_settings.langsmith_trace_content)

# pydantic-settings reads .env but does not export values into os.environ.
# LangSmith's SDK reads standard environment variables, so bridge the settings.
if _settings.langsmith_api_key:
    os.environ["LANGSMITH_API_KEY"] = _settings.langsmith_api_key
if _settings.langsmith_endpoint:
    os.environ["LANGSMITH_ENDPOINT"] = _settings.langsmith_endpoint
if _settings.langsmith_project:
    os.environ["LANGSMITH_PROJECT"] = _settings.langsmith_project
os.environ["LANGSMITH_TRACING"] = "true" if _TRACE_ENABLED else "false"

try:
    from langsmith import traceable as _langsmith_traceable
except ImportError:  # Keep MedTrust usable when the optional SDK is not installed.
    _langsmith_traceable = None
    if _settings.langsmith_tracing:
        logger.warning(
            "LangSmith tracing requested, but package 'langsmith' is not installed. "
            "Install it with: pip install -r requirements.txt"
        )

if _settings.langsmith_tracing and not _settings.langsmith_api_key.strip():
    logger.warning("LangSmith tracing is enabled but LANGSMITH_API_KEY is empty; tracing is disabled")


def tracing_enabled() -> bool:
    """Return whether LangSmith tracing is actually configured and available."""
    return bool(_TRACE_ENABLED and _langsmith_traceable is not None)


def trace_content_enabled() -> bool:
    """Return whether query, answer, prompt and chunk text may be traced."""
    return bool(tracing_enabled() and _TRACE_CONTENT)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _text_summary(value: Any, *, allow_content: bool | None = None, limit: int = 4000) -> dict[str, Any]:
    text = str(value or "")
    allow = trace_content_enabled() if allow_content is None else bool(allow_content)
    result: dict[str, Any] = {"chars": len(text), "sha256": _sha256(text)}
    if allow and text:
        result["text"] = text[:limit]
        if len(text) > limit:
            result["truncated"] = True
    return result


def _arg(inputs: Any, name: str, position: int | None = None, default: Any = None) -> Any:
    """Read a named/positional argument across LangSmith SDK input shapes."""
    if isinstance(inputs, dict):
        if name in inputs:
            return inputs[name]
        kwargs = inputs.get("kwargs")
        if isinstance(kwargs, dict) and name in kwargs:
            return kwargs[name]
        args = inputs.get("args")
        if isinstance(args, (list, tuple)) and position is not None:
            # LangSmith may serialize bound-method args either with or without `self`.
            # Detect an instance-like first arg instead of assuming an offset.
            first = args[0] if args else None
            self_offset = int(
                first is not None
                and not isinstance(first, (str, int, float, bool, dict, list, tuple, set))
            )
            index = position + self_offset
            if len(args) > index:
                return args[index]
    elif isinstance(inputs, (list, tuple)) and position is not None:
        first = inputs[0] if inputs else None
        self_offset = int(
            first is not None
            and not isinstance(first, (str, int, float, bool, dict, list, tuple, set))
        )
        index = position + self_offset
        if len(inputs) > index:
            return inputs[index]
    return default


def _doc_trace_item(doc: Any, rank: int) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {"rank": rank, "value_type": type(doc).__name__}
    item: dict[str, Any] = {
        "rank": rank,
        "chunk_id": doc.get("chunk_id"),
        "title": doc.get("title"),
        "path": doc.get("wiki_path") or doc.get("path"),
        "section": doc.get("section"),
        "rrf_score": doc.get("rrf_score"),
        "dense_similarity": doc.get("dense_similarity"),
        "dense_rank": doc.get("dense_rank"),
        "lexical_rank": doc.get("lexical_rank"),
        "path_rank": doc.get("path_rank"),
        "eligible_for_answer": doc.get("eligible_for_answer"),
        "matched_query_aspects": doc.get("_matched_query_aspects") or doc.get("matched_query_aspects") or [],
        "answerability_score": doc.get("answerability_score"),
        "source_relevance": doc.get("source_relevance"),
    }
    if trace_content_enabled():
        item["content"] = str(doc.get("content") or "")[:1200]
    else:
        item["content"] = _text_summary(doc.get("content") or "")
    return item


def _docs_from_output(outputs: Any) -> list[dict[str, Any]]:
    if isinstance(outputs, tuple) and outputs:
        outputs = outputs[0]
    if isinstance(outputs, dict):
        maybe_docs = outputs.get("retrieval") or outputs.get("docs") or outputs.get("results")
        outputs = maybe_docs
    if not isinstance(outputs, list):
        return []
    return [item for item in outputs if isinstance(item, dict)]


def _trace_answer_inputs(inputs: Any) -> dict[str, Any]:
    question = _arg(inputs, "question", 0, "")
    patient = _arg(inputs, "patient", 1)
    top_k = _arg(inputs, "top_k", 2)
    conversation_id = _arg(inputs, "conversation_id", 3)
    return {
        "question": _text_summary(question),
        "patient_context_provided": bool(patient),
        "top_k": top_k,
        "conversation_id_provided": bool(conversation_id),
    }


def _trace_answer_outputs(outputs: Any) -> dict[str, Any]:
    if not isinstance(outputs, dict):
        return {"output_type": type(outputs).__name__}
    retrieval = outputs.get("retrieval") or []
    sources = outputs.get("sources") or []
    diagnostics = outputs.get("answer_review_diagnostics") or {}
    return {
        "query_id": outputs.get("query_id"),
        "answer": _text_summary(outputs.get("answer")),
        "answer_reviewed": outputs.get("answer_reviewed"),
        "source_checks_passed": outputs.get("source_checks_passed"),
        "retrieved_chunk_count": len(retrieval) if isinstance(retrieval, list) else 0,
        "retrieved_chunks": [_doc_trace_item(item, i) for i, item in enumerate(retrieval, 1) if isinstance(item, dict)],
        "answer_sources": [
            {
                "source_id": item.get("source_id"),
                "source_type": item.get("source_type"),
                "path": item.get("path") or item.get("source_path"),
                "used_in_answer": bool(item.get("used_in_answer")),
            }
            for item in sources if isinstance(item, dict)
        ],
        "used_source_ids": diagnostics.get("used_source_ids") or [],
        "search_backend": outputs.get("search_backend"),
        "web_search_policy": outputs.get("web_search_policy"),
        "web_search_attempted": outputs.get("web_search_attempted"),
        "web_search_status": outputs.get("web_search_status"),
        "web_search_used": outputs.get("web_search_used"),
        "resource_usage": outputs.get("resource_usage") or {},
    }


def _trace_retrieval_inputs(inputs: Any) -> dict[str, Any]:
    question = _arg(inputs, "question", 0, "")
    top_k = _arg(inputs, "top_k", 2)
    patient = _arg(inputs, "patient", 1)
    return {
        "question": _text_summary(question),
        "top_k": top_k,
        "patient_context_provided": bool(patient),
    }


def _trace_retrieval_outputs(outputs: Any) -> dict[str, Any]:
    docs = _docs_from_output(outputs)
    aspects: list[str] = []
    if isinstance(outputs, tuple) and len(outputs) > 1 and isinstance(outputs[1], list):
        aspects = [str(item) for item in outputs[1]]
    return {
        "candidate_count": len(docs),
        "query_aspects": [_text_summary(item) for item in aspects],
        "chunks": [_doc_trace_item(doc, index) for index, doc in enumerate(docs, 1)],
    }


def _trace_prompt_inputs(inputs: Any) -> dict[str, Any]:
    question = _arg(inputs, "question", 0, "")
    docs = _arg(inputs, "docs", 2, []) or []
    web_results = _arg(inputs, "web_results", 3, []) or []
    patient = _arg(inputs, "patient", 1)
    retrieval_queries = _arg(inputs, "retrieval_queries", 8, []) or []
    chunk_items = [_doc_trace_item(doc, i) for i, doc in enumerate(docs, 1) if isinstance(doc, dict)]
    web_items: list[dict[str, Any]] = []
    for index, result in enumerate(web_results, 1):
        if isinstance(result, dict):
            title = result.get("title")
            url = result.get("url")
            domain = result.get("domain")
            snippet = result.get("snippet", "")
        else:
            title = getattr(result, "title", None)
            url = getattr(result, "url", None)
            domain = getattr(result, "domain", None)
            snippet = getattr(result, "snippet", "")
        web_items.append({
            "rank": index, "title": title, "url": url,
            "domain": domain, "snippet": _text_summary(snippet),
        })
    return {
        "question": _text_summary(question),
        "patient_context_provided": bool(patient),
        "wiki_retrieval_candidates_available": len(chunk_items),
        "wiki_retrieval_candidates": chunk_items,
        "web_sources": web_items,
        "retrieval_queries": [_text_summary(item) for item in retrieval_queries],
    }


def _redact_prompt(prompt: str) -> str:
    """Keep source context inspectable while always removing patient/history fields."""
    value = str(prompt or "")
    replacements = (
        ("Долговременная память:\n", "Последние сообщения:\n"),
        ("Последние сообщения:\n", "Текущий вопрос пользователя:\n"),
        ("Контекст пациента текущего запроса:\n", "Источники:\n"),
    )
    for start, end in replacements:
        if start in value and end in value:
            before, rest = value.split(start, 1)
            _, after = rest.split(end, 1)
            value = before + start + "[REDACTED: private context]\n" + end + after
    return value


def _trace_prompt_outputs(outputs: Any) -> dict[str, Any]:
    prompt = str(outputs or "")
    safe_prompt = _redact_prompt(prompt)
    result = {"prompt_chars": len(prompt), "prompt_sha256": _sha256(prompt)}
    if trace_content_enabled():
        result["prompt_redacted"] = safe_prompt[:12000]
        result["prompt_truncated"] = len(safe_prompt) > 12000
    return result


def _trace_gigachat_inputs(inputs: Any) -> dict[str, Any]:
    messages = _arg(inputs, "messages", 0, []) or []
    safe_messages: list[dict[str, Any]] = []
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "")
        safe_content = _redact_prompt(content)
        item = {"role": message.get("role"), **_text_summary(safe_content)}
        if not trace_content_enabled():
            item.pop("text", None)
        safe_messages.append(item)
    return {"model": _settings.gigachat_model, "messages": safe_messages}


def _trace_gigachat_outputs(outputs: Any) -> dict[str, Any]:
    return {"completion": _text_summary(outputs, limit=6000)}


def _trace_selected_context_inputs(inputs: Any) -> dict[str, Any]:
    docs = _arg(inputs, "docs", 0, []) or []
    if not isinstance(docs, list):
        docs = []
    return {
        "selected_chunk_count": len(docs),
        "selected_chunks": [
            _doc_trace_item(item, index)
            for index, item in enumerate(docs, 1)
            if isinstance(item, dict)
        ],
    }


def traceable_span(
    *,
    name: str,
    run_type: str = "chain",
    process_inputs: Callable[[Any], dict[str, Any]] | None = None,
    process_outputs: Callable[[Any], dict[str, Any]] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that safely becomes a no-op when tracing is disabled."""
    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        if _langsmith_traceable is None or not tracing_enabled():
            return func
        try:
            return _langsmith_traceable(
                name=name,
                run_type=run_type,
                process_inputs=process_inputs,
                process_outputs=process_outputs,
                enabled=True,
            )(func)
        except TypeError:
            # Compatibility with older SDKs: only decorate when tracing is enabled.
            return _langsmith_traceable(
                name=name,
                run_type=run_type,
                process_inputs=process_inputs,
                process_outputs=process_outputs,
            )(func)
    return decorate


# Public processors used by decorators in existing service modules.
trace_answer_inputs = _trace_answer_inputs
trace_answer_outputs = _trace_answer_outputs
trace_retrieval_inputs = _trace_retrieval_inputs
trace_retrieval_outputs = _trace_retrieval_outputs
trace_prompt_inputs = _trace_prompt_inputs
trace_prompt_outputs = _trace_prompt_outputs
trace_gigachat_inputs = _trace_gigachat_inputs
trace_gigachat_outputs = _trace_gigachat_outputs


@traceable_span(
    name="Wiki chunks passed to GigaChat context",
    run_type="retriever",
    process_inputs=_trace_selected_context_inputs,
    process_outputs=lambda outputs: {"selected_chunk_count": outputs},
)
def trace_selected_context_docs(docs: list[dict[str, Any]]) -> int:
    """Record exactly which Wiki chunks are assembled into the model prompt."""
    return len(docs)
