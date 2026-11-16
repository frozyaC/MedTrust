from __future__ import annotations

from app.services import langsmith_tracing as tracing


def test_langsmith_answer_trace_does_not_include_patient_fields(monkeypatch):
    payload = {
        "question": "Как записать пациента?",
        "patient": {"age": 48, "sex": "female", "anamnesis": "private note"},
        "top_k": 5,
        "conversation_id": "private-conversation-id",
    }
    traced = tracing._trace_answer_inputs(payload)
    assert traced["patient_context_provided"] is True
    assert traced["conversation_id_provided"] is True
    assert "private note" not in str(traced)
    assert "private-conversation-id" not in str(traced)
    assert "48" not in str(traced)


def test_langsmith_chunk_trace_uses_hash_instead_of_raw_content(monkeypatch):
    monkeypatch.setattr(tracing, "trace_content_enabled", lambda: False)
    chunk = {
        "chunk_id": "chunk-123",
        "wiki_path": "Словарь/Лаборатория/ОАК.md",
        "content": "Текст внутренней инструкции, который не должен утечь в trace",
        "rrf_score": 0.031,
        "dense_rank": 1,
        "lexical_rank": 2,
    }
    traced = tracing._doc_trace_item(chunk, 1)
    assert traced["chunk_id"] == "chunk-123"
    assert traced["path"] == "Словарь/Лаборатория/ОАК.md"
    assert "Текст внутренней инструкции" not in str(traced)
    assert traced["content"]["sha256"]
    assert traced["content"]["chars"] > 0


def test_langsmith_prompt_redacts_history_and_patient_context():
    prompt = (
        "Долговременная память:\nprivate summary\n\n"
        "Последние сообщения:\nprivate transcript\n\n"
        "Текущий вопрос пользователя:\nquestion\n\n"
        "Контекст пациента текущего запроса:\nprivate patient json\n\n"
        "Источники:\npublic wiki source"
    )
    safe = tracing._redact_prompt(prompt)
    assert "private summary" not in safe
    assert "private transcript" not in safe
    assert "private patient json" not in safe
    assert "public wiki source" in safe
