from types import SimpleNamespace

from app.services.gigachat import SYSTEM_PROMPT
from app.services.rag import RagService
from app.services.source_relevance import (
    has_topic_specific_clinical_evidence,
    requires_fresh_clinical_search,
)
from app.services.web_search import WebSearchResponse


QUESTION = "Какие современные рекомендации по диагностике мигрени у взрослых?"


def test_system_prompt_defines_registrar_assistant_role_and_history_rules():
    assert "помощник регистратора" in SYSTEM_PROMPT
    assert "сотрудник регистратуры" in SYSTEM_PROMPT
    assert "conversation_id" in SYSTEM_PROMPT
    assert "не переноси сведения о прежнем пациенте на другого" in SYSTEM_PROMPT
    assert "современных клинических рекомендаций" in SYSTEM_PROMPT


def test_short_follow_up_uses_previous_user_question(monkeypatch):
    monkeypatch.setattr(
        "app.services.rag.get_settings",
        lambda: SimpleNamespace(memory_follow_up_max_chars=300),
    )
    memory = {
        "messages": [
            {"role": "user", "content": "Какие современные рекомендации по диагностике мигрени у взрослых?"},
            {"role": "assistant", "content": "В источнике обсуждаются признаки мигрени."},
        ]
    }

    result = RagService._contextualize_question("А симптомы?", memory)

    assert "диагностике мигрени у взрослых" in result
    assert "А симптомы?" in result
    assert "Контекст предыдущего вопроса:" not in result
    assert "Текущий уточняющий вопрос:" not in result


def test_new_standalone_question_does_not_inherit_unrelated_topic():
    memory = {
        "messages": [{"role": "user", "content": "Куда записать пациента при травме?"}]
    }
    question = "Какие анализы нужны перед УЗИ?"

    assert RagService._contextualize_question(question, memory) == question


def test_current_clinical_guidance_is_never_satisfied_by_static_wiki_alone():
    irrelevant_high_similarity_doc = {
        "chunk_id": "administrative-doc",
        "document_id": "administrative-doc",
        "title": "ВОЗРАЖЕНИЯ (скрипты ответа)",
        "wiki_path": "Регистратура/Скрипты/Возражения",
        "section": "Срок давности назначений истек",
        "path_segments": ["Регистратура", "Скрипты", "Возражения"],
        "source_url": None,
        "content": "Для получения свежих рекомендаций пациенту нужно повторно обратиться к специалисту.",
        "dense_similarity": 0.99,
        "rrf_score": 0.99,
        "lexical_rank": 1,
        "path_rank": 1,
    }

    assert requires_fresh_clinical_search(QUESTION)
    assert not RagService._wiki_is_sufficient([irrelevant_high_similarity_doc], QUESTION)


def test_topic_specific_clinical_evidence_rejects_generic_or_unrelated_wiki_text():
    unrelated = (
        "ВОЗРАЖЕНИЯ Срок давности назначений истек. "
        "Пациенту необходимо повторно обратиться к специалисту за новыми рекомендациями."
    )
    relevant = (
        "Migraine diagnosis in adults. Clinical diagnosis and recommendations for migraine "
        "include assessment of headache characteristics and associated symptoms."
    )

    assert not has_topic_specific_clinical_evidence(QUESTION, unrelated)
    assert has_topic_specific_clinical_evidence(QUESTION, relevant)


def test_answer_does_not_fallback_to_web_when_local_evidence_is_missing(monkeypatch):
    from types import SimpleNamespace

    class Settings:
        memory_follow_up_max_chars = 300
        gigachat_max_tokens = 450

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    class FakeMemory:
        def __init__(self):
            self.messages = []
        def ensure_conversation(self, conversation_id):
            return conversation_id or "conversation-test"
        def build_context(self, conversation_id):
            return {"summary": "", "messages": []}
        def add_message(self, conversation_id, role, content, **kwargs):
            self.messages.append((role, content, kwargs))
        def all_messages_count(self, conversation_id):
            return sum(role == "user" for role, _, _ in self.messages)
        def update_title(self, conversation_id, title):
            pass

    class FakeContextualizer:
        def resolve(self, **kwargs):
            question = kwargs["current_question"]
            return SimpleNamespace(
                resolved_query=question, clarification_required=False,
                clarification_question=None, llm_attempted=False,
                intent="new_question", confidence=1.0,
                as_dict=lambda: {"resolved_query": question},
            )

    class ForbiddenWebSearch:
        def search(self, *args, **kwargs):
            raise AssertionError("Main /query endpoint attempted internet search")

    class FakeGigaChat:
        last_usage = {}
        def chat(self, prompt):
            raise AssertionError("No local source: GigaChat must not invent an answer")

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.contextualizer = FakeContextualizer()
    service.knowledge_gap_tracker = SimpleNamespace(record_gap=lambda **kwargs: None)
    service.gigachat = FakeGigaChat()
    service.web_search = ForbiddenWebSearch()
    service._search_question_aspects = lambda question, patient, top_k: ([], [question])

    result = service.answer(QUESTION, None, 5)

    assert result["web_search_attempted"] is False
    assert result["web_search_used"] is False
    assert result["web_search_status"] == "disabled_for_query_endpoint"
    assert result["web_search_policy"] == "disabled_for_query_endpoint"
    assert result["sources"] == []
    assert result["source_checks_passed"] is False
    assert result["resource_usage"]["gigachat_calls"] == 0


def test_prompt_uses_previous_turn_as_context_but_not_as_source(monkeypatch):
    settings = SimpleNamespace(
        rag_max_wiki_sources=3,
        rag_max_history_messages=4,
        rag_max_history_message_chars=600,
    )
    monkeypatch.setattr("app.services.rag.get_settings", lambda: settings)
    memory = {
        "summary": "Тема: мигрень у взрослых",
        "messages": [
            {"role": "user", "content": "Какие современные рекомендации по диагностике мигрени у взрослых?"},
            {"role": "assistant", "content": "В прошлом ответе обсуждалась диагностика мигрени."},
        ],
    }

    prompt = RagService._build_prompt(
        "А симптомы?",
        None,
        [],
        [],
        memory,
        wiki_sufficient=False,
        contextualized_question=(
            "Контекст предыдущего вопроса: Какие современные рекомендации по диагностике мигрени у взрослых?\n"
            "Текущий уточняющий вопрос: А симптомы?"
        ),
    )

    assert "Последние сообщения" in prompt
    assert "В прошлом ответе обсуждалась диагностика мигрени" in prompt
    assert "Смысл вопроса с учётом предыдущего контекста" in prompt
    assert "не считай историю источником фактов" in prompt


def test_general_medical_search_query_is_not_polluted_by_random_wiki_city():
    wiki_docs = [
        {
            "title": "Список врачей Екатеринбург",
            "section": "Врачи",
            "wiki_path": "Регистратура/Екатеринбург/Врачи",
            "content": "В клинике в Екатеринбурге доступны разные специалисты.",
        }
    ]

    assert RagService._web_query_for_aspect(QUESTION, wiki_docs) == QUESTION
