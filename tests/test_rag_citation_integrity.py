from types import SimpleNamespace

from app.services.rag import RagService
from app.services.web_search import WebSearchResult


def _doc() -> dict:
    return {
        "title": "Нерелевантная Wiki статья",
        "wiki_path": "Регистратура/Обзвон/example",
        "section": "Раздел",
        "path_segments": ["Регистратура", "Обзвон", "example"],
        "source_url": None,
        "content": "Список врачей.",
    }


def _web() -> WebSearchResult:
    return WebSearchResult(
        title="NICE migraine diagnosis",
        url="https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
        snippet="Clinical assessment is essential in diagnosis of migraine.",
        rank=1,
        domain="cks.nice.org.uk",
    )


def test_build_prompt_excludes_wiki_citations_when_wiki_is_insufficient(monkeypatch):
    class Settings:
        memory_follow_up_max_chars = 300
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    prompt = RagService._build_prompt(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        None,
        [_doc()],
        [_web()],
        {"summary": "нет", "messages": []},
        wiki_sufficient=False,
    )

    assert "WEB1" in prompt
    assert "Нерелевантная Wiki статья" not in prompt
    assert "[W1]" not in prompt
    assert "[WEB1]" in prompt


def test_collect_sources_excludes_wiki_when_wiki_is_insufficient():
    sources = RagService._collect_sources([_doc()], [_web()], wiki_sufficient=False)

    assert [source["source_id"] for source in sources] == ["WEB1"]


def test_filter_used_sources_rejects_citation_not_in_prompt_sources():
    sources = RagService._collect_sources([], [_web()], wiki_sufficient=False)

    assert RagService._filter_used_sources("Ответ [W1].", sources) == []
    assert RagService._filter_used_sources("Ответ [WEB1].", sources)[0]["source_id"] == "WEB1"


def test_wiki_answerability_checks_all_hybrid_candidates(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    docs = [
        {**_doc(), "dense_similarity": 0.42, "lexical_rank": 1},
        {**_doc(), "title": "Релевантная статья", "dense_similarity": 0.66, "lexical_rank": 3},
    ]

    assert RagService._wiki_is_sufficient(docs) is True
    selected = RagService._wiki_sufficient_docs(docs)
    assert [d["title"] for d in selected] == ["Релевантная статья"]


def test_follow_up_uses_relevant_wiki_candidate_despite_noisy_top_rrf(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    docs = [
        {**_doc(), "dense_similarity": 0.41, "lexical_rank": 1},
        {**_doc(), "title": "Травматолог-ортопед", "dense_similarity": 0.68, "lexical_rank": 3},
    ]

    prompt = RagService._build_prompt(
        "А если пациент уже обращался в другую клинику?",
        None,
        docs,
        [],
        {"summary": "", "messages": []},
        wiki_sufficient=RagService._wiki_is_sufficient(docs),
    )

    assert "Травматолог-ортопед" in prompt
    assert "Нерелевантная Wiki статья" not in prompt


def test_strong_wiki_match_excludes_weaker_noisy_chunks(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    docs = [
        {
            **_doc(),
            "chunk_id": "noisy",
            "title": "Грубый пациент",
            "dense_similarity": 0.328,
            "lexical_rank": 1,
            "path_rank": 3,
        },
        {
            **_doc(),
            "chunk_id": "trauma-rule",
            "title": "Травматолог-ортопед",
            "content": (
                "Если травма случилась в течение 7 дней и пациент не обращался в больницу, "
                "запись в травмпункт. Если обращался в другую клинику — запись к травматологу."
            ),
            "dense_similarity": 0.660,
            "lexical_rank": 3,
            "path_rank": None,
        },
        {
            **_doc(),
            "chunk_id": "operation",
            "title": "Травматолог-ортопед",
            "section": "Консультация по операции",
            "dense_similarity": 0.550,
            "lexical_rank": 6,
            "path_rank": None,
        },
    ]

    selected = RagService._wiki_sufficient_docs(docs)
    assert [doc["chunk_id"] for doc in selected] == ["trauma-rule"]

    prompt = RagService._build_prompt(
        "Куда записать пациента при травме 5 дней назад?",
        None,
        docs,
        [],
        {"summary": "", "messages": []},
        wiki_sufficient=True,
    )
    assert "trauma-rule" not in prompt  # IDs are metadata, not evidence text.
    assert "Если травма случилась в течение 7 дней" in prompt
    assert "Грубый пациент" not in prompt
    assert "Консультация по операции" not in prompt


def test_weak_hybrid_match_can_pass_only_when_no_strong_match_exists(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    docs = [
        {
            **_doc(),
            "title": "Травматолог-ортопед",
            "dense_similarity": 0.535,
            "lexical_rank": 5,
            "path_rank": None,
        },
        {
            **_doc(),
            "title": "Грубый пациент",
            "dense_similarity": 0.328,
            "lexical_rank": 1,
            "path_rank": 3,
        },
    ]
    assert [doc["title"] for doc in RagService._wiki_sufficient_docs(docs)] == [
        "Травматолог-ортопед"
    ]


def test_old_and_new_insufficient_phrases_are_recognized():
    assert RagService._is_insufficient_answer("нужные данные не найдены")
    assert RagService._is_insufficient_answer("Данных может быть недостаточно.")
    assert not RagService._is_insufficient_answer("Запись в травмпункт [W1].")


def test_false_no_data_answer_uses_evidence_fallback_without_extra_model_calls(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62
        memory_follow_up_max_chars = 300

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    doc = {
        **_doc(),
        "chunk_id": "trauma-rule",
        "title": "Травматолог-ортопед",
        "wiki_path": "Регистратура/Словарь/Травматология/Общая_информация",
        "section": "Острые травмы",
        "path_segments": ["Регистратура", "Словарь", "Травматология", "Общая_информация"],
        "source_url": None,
        "content": (
            "Если травма случилась в течение 7 дней, и пациент не консультировался "
            "по этой проблеме со специалистом (не обращался в больницу) — запись в травмпункт. "
            "Если пациент посетил врача другой клиники и есть заключения, рекомендации — "
            "запись к травматологу в поликлинику."
        ),
        "rrf_score": 0.032,
        "dense_similarity": 0.660,
        "dense_rank": 1,
        "lexical_rank": 3,
        "path_rank": None,
    }

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

        def maybe_update_summary(self, conversation_id, gigachat):
            pass

    class FakeGigaChat:
        def __init__(self):
            self.calls = 0

        def chat(self, prompt):
            self.calls += 1
            if self.calls == 1:
                return "нужные данные не найдены"
            if self.calls == 2:
                return "Если пациент не обращался в больницу, его записывают в травмпункт [W1]."
            return (
                "Если травма произошла в течение 7 дней и пациент не обращался в больницу "
                "по этой проблеме, его записывают в травмпункт. Если он посетил врача другой "
                "клиники и есть заключение или рекомендации, его записывают к травматологу "
                "в поликлинику [W1]."
            )

    class FakeScope:
        def validate(self, question):
            return SimpleNamespace(allowed=True)

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.scope = FakeScope()
    service.gigachat = FakeGigaChat()
    service.web_search = SimpleNamespace(
        search=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Web search not expected"))
    )
    service.search = lambda question, patient, top_k: [doc]

    result = service.answer("Куда записать пациента при травме 5 дней назад?", None, 5)

    assert "в течение 7 дней" in result["answer"]
    assert "к травматологу в поликлинику" in result["answer"]
    assert result["sources"][0]["title"] == "Травматолог-ортопед"
    assert service.gigachat.calls == 1  # one generation call; no citation retry/review/repair
    assert result["resource_usage"]["gigachat_calls"] == 1
    assert result["answer_reviewed"] is True
    assert result["retrieval"][0]["eligible_for_answer"] is True
    audit = result["answer_review_diagnostics"]
    assert audit["status"] == "passed"
    assert audit["stage"] == "single_pass_deterministic_checks_passed"
    assert audit["attempts"]["citation_retry"] == 0
    assert audit["attempts"]["quality_review"] == 0
    assert audit["attempts"]["content_repair"] == 0
    assert audit["final_issues"] == []


def test_extract_fallback_returns_strong_wiki_evidence_with_valid_citation(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    doc = {
        **_doc(),
        "chunk_id": "trauma-rule",
        "title": "Травматолог-ортопед",
        "wiki_path": "Регистратура/Словарь/Травматология/Общая_информация",
        "path_segments": ["Регистратура", "Словарь", "Травматология", "Общая_информация"],
        "source_url": None,
        "content": "При травме в течение 7 дней без обращения в больницу — запись в травмпункт.",
        "dense_similarity": 0.660,
    }
    answer = RagService._extractive_fallback_answer([doc], [], wiki_sufficient=True)
    sources = RagService._collect_sources([doc], [], wiki_sufficient=True)

    assert "запись в травмпункт" in answer
    assert "[W1]" in answer
    assert RagService._filter_used_sources(answer, sources)[0]["source_id"] == "W1"


def test_rag_defensively_rejects_irrelevant_web_source(monkeypatch):
    from app.services.web_search import WebSearchResponse

    class Settings:
        web_min_wiki_dense_similarity = 0.62
        memory_follow_up_max_chars = 300

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

    irrelevant = WebSearchResult(
        title="Myalgic encephalomyelitis / chronic fatigue syndrome - NICE",
        url="https://www.nice.org.uk/guidance/ng206",
        snippet="Recommendations on diagnosis and management of ME/CFS.",
        rank=1,
        domain="www.nice.org.uk",
    )

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.scope = SimpleNamespace(validate=lambda question: SimpleNamespace(allowed=True))
    service.search = lambda question, patient, top_k: []
    service.web_search = SimpleNamespace(
        search=lambda *args, **kwargs: WebSearchResponse("success", [irrelevant])
    )

    result = service.answer(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", None, 5
    )

    assert result["answer"] == "Данных может быть недостаточно."
    assert result["sources"] == []
    assert result["web_search_used"] is False
    assert result["web_search_status"] == "no_relevant_results"
    assert result["answer_review_diagnostics"]["status"] == "not_run"
    assert result["answer_review_diagnostics"]["stage"] == "no_relevant_evidence"


def test_rag_fails_closed_without_extra_model_calls_when_criteria_are_unsupported(monkeypatch):
    from types import SimpleNamespace
    from app.services.web_search import WebSearchResponse

    class Settings:
        web_min_wiki_dense_similarity = 0.62
        memory_follow_up_max_chars = 300

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

        def maybe_update_summary(self, conversation_id, gigachat):
            pass

    class FakeGigaChat:
        def __init__(self):
            self.calls = 0

        def chat(self, prompt):
            self.calls += 1
            return (
                "Мигрень с аурой устанавливается только при приступах от 4 до 72 часов, "
                "а симптомы ауры обязательно сопровождаются головной болью [WEB1]."
            )

    web_result = WebSearchResult(
        title="NICE migraine with aura diagnosis - headaches in over 12s",
        url="https://www.nice.org.uk/guidance/cg150",
        snippet="Overview of headache diagnosis and management for young people aged 12 years and older and adults.",
        rank=1,
        domain="www.nice.org.uk",
    )

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.scope = SimpleNamespace(validate=lambda question: SimpleNamespace(allowed=True))
    service.gigachat = FakeGigaChat()
    service.search = lambda question, patient, top_k: []
    service.web_search = SimpleNamespace(
        search=lambda *args, **kwargs: WebSearchResponse("success", [web_result])
    )

    result = service.answer(
        "Какие современные рекомендации по диагностике мигрени с аурой у взрослых?", None, 5
    )

    assert service.gigachat.calls == 1  # one model call per query by default
    assert result["resource_usage"]["gigachat_calls"] == 1
    assert result["answer_reviewed"] is False
    assert "Overview of headache diagnosis" in result["answer"]
    assert "[WEB1]" in result["answer"]
    assert result["sources"][0]["source_id"] == "WEB1"

    # Failure is now diagnosable from the API payload instead of one generic message.
    audit = result["answer_review_diagnostics"]
    assert audit["status"] == "failed"
    assert audit["stage"] == "deterministic_check_failed_fallback"
    assert audit["attempts"]["quality_review"] == 0
    assert audit["attempts"]["content_repair"] == 0
    assert audit["initial_issues"]
    assert audit["reviewed_issues"] == []
    assert audit["repaired_issues"] == []
    assert audit["final_issues"]
    assert audit["source_ids"] == ["WEB1"]
    assert audit["used_source_ids"] == ["WEB1"]
    assert audit["issue_details"]["initial"]



def test_web_recommendation_content_is_available_to_rag_content_review():
    """The complete fetched NICE chapter, not only its overview, is validation evidence."""
    recommendation_text = (
        "Recommendations. Diagnosis of migraine in adults. Headache lasts 4 to 72 hours. "
        "Consider using a headache diary for at least 8 weeks. Migraine with aura may occur "
        "with or without headache."
    )
    result = WebSearchResult(
        title="Headaches in over 12s: diagnosis and management - NICE",
        url="https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
        snippet=recommendation_text,
        rank=1,
        domain="www.nice.org.uk",
    )

    evidence = RagService._build_source_evidence([], [result], wiki_sufficient=False)

    assert evidence["[WEB1]"]
    assert "4 to 72 hours" in evidence["[WEB1]"]
    assert "headache diary" in evidence["[WEB1]"]
    assert "with or without headache" in evidence["[WEB1]"]


def test_diagnostic_answer_from_nice_source_passes_single_call_and_uses_compact_context(monkeypatch):
    from app.services.web_search import WebSearchResponse

    class Settings:
        web_min_wiki_dense_similarity = 0.62
        memory_follow_up_max_chars = 300
        rag_max_web_sources = 2
        rag_max_source_chars = 4200
        rag_max_history_messages = 4
        rag_max_history_message_chars = 600
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
        def maybe_update_summary(self, conversation_id, gigachat):
            pass

    class FakeGigaChat:
        def __init__(self):
            self.calls = 0
            self.prompt = ""
        def chat(self, prompt):
            self.calls += 1
            self.prompt = prompt
            return (
                "## Оценка и диагностика\n"
                "Боль может быть односторонней или двусторонней, умеренной или сильной; возможны "
                "чувствительность к свету и звуку, тошнота или рвота [WEB1].\n\n"
                "Приступ у взрослых длится от 4 до 72 часов. Эпизодическая мигрень бывает менее 15 дней "
                "в месяц; хроническая — 15 или более дней, в том числе не менее 8 дней с признаками мигрени [WEB1].\n\n"
                "Аура развивается постепенно в течение не менее 5 минут и длится 5–60 минут; она может "
                "возникать перед началом головной боли или во время неё [WEB1].\n\n"
                "Эти рекомендации относятся к взрослым пациентам старше 12 лет."
            )

    evidence = (
        "NICE CG150 Recommendations. 1.1.1 Evaluate people with worsening headache with fever, "
        "sudden-onset headache reaching maximum intensity within 5 minutes, new-onset neurological deficit, "
        "new-onset cognitive dysfunction, change in personality, impaired level of consciousness, recent head trauma, "
        "headache triggered by cough, Valsalva or sneeze, headache triggered by exercise, orthostatic headache, "
        "symptoms suggestive of giant cell arteritis, acute narrow angle glaucoma or a substantial change in headache. "
        "1.1.3 Consider using a headache diary to aid diagnosis. 1.1.4 Record frequency, duration and severity, "
        "associated symptoms, medications, possible precipitants and relationship to menstruation for a minimum of 8 weeks. "
        "1.2.1 Migraine pain location is unilateral or bilateral; pain quality is pulsating; pain intensity is moderate or severe; "
        "it is aggravated by or causes avoidance of routine activities. Other symptoms are unusual sensitivity to light and/or sound "
        "or nausea and/or vomiting. Duration of headache is 4 to 72 hours in adults. Episodic migraine occurs on fewer than 15 days "
        "per month. Chronic migraine occurs on 15 or more days per month, with at least 8 days having features of migraine, "
        "for more than 3 months. Symptoms of aura can occur with or without headache; they are fully reversible, develop gradually "
        "over at least 5 minutes, and last 5 to 60 minutes. Typical aura symptoms include visual symptoms, sensory symptoms and speech disturbance."
    )
    web_result = WebSearchResult(
        title="Headaches in over 12s: diagnosis and management - NICE",
        url="https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
        snippet=evidence,
        rank=1,
        domain="www.nice.org.uk",
    )

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.scope = SimpleNamespace(validate=lambda question: SimpleNamespace(allowed=True))
    service.gigachat = FakeGigaChat()
    service.search = lambda question, patient, top_k: []
    service.web_search = SimpleNamespace(
        search=lambda *args, **kwargs: WebSearchResponse("success", [web_result])
    )

    result = service.answer("Какие современные рекомендации по диагностике мигрени у взрослых?", None, 5)

    assert service.gigachat.calls == 0
    assert result["resource_usage"]["gigachat_calls"] == 0
    assert result["resource_usage"]["max_output_tokens"] == 450
    assert result["resource_usage"]["usage_source"] == "not_called"
    assert result["resource_usage"]["estimated_input_tokens"] == 0
    assert result["resource_usage"]["embedding_api_calls"] == 1
    assert result["answer_reviewed"] is True
    assert result["answer_review_diagnostics"]["status"] == "passed"
    assert result["answer_review_diagnostics"]["stage"] == "deterministic_guideline_template_passed"
    assert result["answer_review_diagnostics"]["attempts"]["initial_generation"] is False
    assert result["answer_review_diagnostics"]["attempts"]["quality_review"] == 0
    assert "старше 12 лет" not in result["answer"]
    assert "дневник" in result["answer"].casefold()
    assert "обследование/направление" in result["answer"].casefold()
    assert "4–72 часа" in result["answer"]
    assert "односторонней или двусторонней" in result["answer"]
    assert "5–60 минут" in result["answer"]
    assert "15 дней" in result["answer"]
    assert result["sources"][0]["source_id"] == "WEB1"


def test_web_context_and_history_are_bounded_for_token_budget(monkeypatch):
    class Settings:
        rag_max_web_sources = 1
        rag_max_source_chars = 1200
        rag_max_history_messages = 2
        rag_max_history_message_chars = 100
        memory_follow_up_max_chars = 300
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    results = [
        WebSearchResult("NICE migraine", "https://nice.org.uk/migraine", "x" * 5000, 1, "nice.org.uk"),
        WebSearchResult("Another migraine", "https://nice.org.uk/migraine2", "y" * 5000, 2, "nice.org.uk"),
    ]
    compact = RagService._compact_web_results("migraine diagnosis", results)
    assert len(compact) == 1
    assert len(compact[0].snippet) <= 1201

    prompt = RagService._build_prompt(
        "Question about migraine", None, [], compact,
        {"summary": "s" * 2000, "messages": [
            {"role": "user", "content": "a" * 1000},
            {"role": "assistant", "content": "b" * 1000},
            {"role": "user", "content": "c" * 1000},
        ]},
        wiki_sufficient=False,
    )
    assert "a" * 150 not in prompt
    assert "b" * 150 not in prompt
    assert len(prompt) < 5000
