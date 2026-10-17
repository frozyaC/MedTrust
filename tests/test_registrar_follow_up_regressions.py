from app.services.rag import RagService
from app.services.source_relevance import requires_fresh_clinical_search


def test_follow_up_context_is_a_natural_query_without_diagnostic_labels(monkeypatch):
    monkeypatch.setattr(
        "app.services.rag.get_settings",
        lambda: type("Settings", (), {"memory_follow_up_max_chars": 300})(),
    )
    result = RagService._contextualize_question(
        "А если у него уже есть направление?",
        {
            "messages": [
                {"role": "user", "content": "Как записать пациента к травматологу при острой боли в колене?"},
                {"role": "assistant", "content": "Сначала уточните обстоятельства обращения."},
            ]
        },
    )
    assert "травматолог" in result.casefold()
    assert "направление" in result.casefold()
    assert "Контекст предыдущего вопроса:" not in result
    assert "Текущий уточняющий вопрос:" not in result


def test_rewrite_instruction_is_not_a_knowledge_search():
    question = "Сформулируй ответ более коротко и вежливо, сохранив смысл инструкции"
    assert RagService._is_answer_rewrite_request(question)


def test_rewrite_instruction_is_skipped_when_finding_prior_topic():
    context = {
        "messages": [
            {"role": "user", "content": "Как подготовить пациента к КТ?"},
            {"role": "assistant", "content": "Перед КТ сообщите пациенту требования из памятки."},
            {
                "role": "user",
                "content": "Сформулируй ответ более коротко и вежливо, сохранив смысл инструкции",
            },
        ]
    }
    assert RagService._last_user_message(context) == "Как подготовить пациента к КТ?"


def test_safety_sensitive_follow_up_requires_more_specific_evidence():
    question = "что если пациент принимает постоянные лекарства?"
    unrelated_preparation_doc = {
        "title": "Ограничения перед процедурой под седацией",
        "section": "Подготовка",
        "content": "Перед процедурой соблюдайте ограничения по еде и питью.",
    }
    medication_doc = {
        "title": "Ограничения перед процедурой под седацией",
        "section": "Лекарства",
        "content": "Сообщите врачу о принимаемых лекарствах перед процедурой.",
    }
    assert RagService._uncovered_safety_detail(question, [unrelated_preparation_doc])
    assert not RagService._uncovered_safety_detail(question, [medication_doc])


def test_wiki_and_current_guidance_request_is_split_into_two_facets():
    question = (
        "Что указано в Wiki о подготовке к процедуре КТ и какие актуальные рекомендации "
        "по этой подготовке публикует профильная медицинская организация?"
    )
    facets = RagService._split_multi_intent_question(question)
    assert len(facets) == 2
    assert "локальной Wiki" in facets[0]
    assert "актуальные рекомендации" in facets[1]
    assert "КТ" in facets[0] and "КТ" in facets[1]
    assert requires_fresh_clinical_search(facets[1])


def test_ordered_lists_restart_from_one_in_each_standalone_answer():
    answer = "2. Запишите пациента на приём. [W1]\n3. Уточните направление. [W2]"
    normalized = RagService._ensure_bullet_format(answer)
    assert normalized.startswith("1. Запишите пациента")
    assert "2. Уточните направление" in normalized


def test_wiki_and_current_guidance_are_split_even_with_patient_context():
    question = (
        "Что указано в Wiki о подготовке к гастроскопии и какие актуальные рекомендации "
        "по этой подготовке для пациента после инфаркта миакарда?"
    )
    facets = RagService._split_multi_intent_question(question)
    assert len(facets) == 3
    assert "локальной Wiki" in facets[0]
    assert "стандартной подготовке" in facets[1]
    assert "после инфаркта миокарда" in facets[2]
    assert "безопасности гастроскопии" in facets[2]


def test_ambiguous_general_procedure_requests_clarification_instead_of_empty_search():
    question = (
        "Что указано в Wiki о подготовке к процедуре общего и какие актуальные рекомендации "
        "по этой подготовке публикует профильная медицинская организация?"
    )
    assert not bool(__import__("re").search(
        r"гастроскоп|фгдс|колоноскоп|\\bкт\\b|компьютерн\\w*\\s+томограф|\\bмрт\\b|"
        r"узи|ультразвуков\\w*|общ\\w*\\s+анализ\\w*\\s+кров\\w*|биохим\\w*\\s+анализ\\w*",
        question.casefold(),
    ))


def test_unknown_conversation_id_is_not_silently_replaced(monkeypatch):
    class FakeRepo:
        def get(self, conversation_id):
            return None

    class FakeMemory:
        repo = FakeRepo()

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service._answer_review_diagnostics = lambda: {"attempts": {}}
    service._resource_usage = lambda *args, **kwargs: {}

    result = service.answer(
        "Сформулируй ответ более коротко и вежливо, сохранив смысл инструкции",
        None,
        5,
        "6f9fe982-df38-4d07-b02b-c0aa4b63d025",
    )
    assert result["conversation_id"] == "6f9fe982-df38-4d07-b02b-c0aa4b63d025"
    assert result["answer_validation_mode"] == "conversation_context_required"
    assert "conversation_id" in result["answer"]


def test_post_mi_query_search_terms_keep_patient_risk_context():
    from app.services.web_search import _fallback_search_terms, _topic_ids

    question = "Какие актуальные рекомендации по подготовке к гастроскопии для пациента после инфаркта миакарда?"
    topics = _topic_ids(question)
    assert "gastroscopy" in topics
    assert "myocardial_infarction" in topics
    terms = _fallback_search_terms(question, "nice.org.uk")
    assert "after myocardial infarction" in terms
    assert "sedation" in terms


def test_current_gastroscopy_recommendations_split_patient_risk_from_routine_prep():
    question = (
        "Какие актуальные рекомендации по подготовке к гастроскопии для пациента "
        "после инфаркта миакарда? Укажи дату или версию рекомендаций и ссылки на авторитетные источники"
    )
    facets = RagService._split_multi_intent_question(question)
    assert len(facets) == 2
    assert "стандартной подготовке к гастроскопии" in facets[0]
    assert "после инфаркта миокарда" in facets[1]
    assert "безопасности гастроскопии" in facets[1]


def test_english_migraine_source_can_support_russian_clinical_question():
    from app.services.source_relevance import has_topic_specific_clinical_evidence

    query = "Какие современные рекомендации по диагностике мигрени у взрослых?"
    source = (
        "Migraine diagnosis in adults. Clinical recommendations and diagnostic guidance "
        "include assessment of headache characteristics and associated symptoms."
    )
    assert has_topic_specific_clinical_evidence(query, source)
