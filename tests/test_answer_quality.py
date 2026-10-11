from app.services.rag import RagService


def test_diagnostic_questions_get_a_source_grounded_completeness_rubric():
    requirements = RagService._answer_quality_requirements(
        "Какие современные рекомендации по диагностике мигрени у взрослых?"
    )
    text = "\n".join(requirements).casefold()

    assert "клинические признаки" in text
    assert "сопутствующие симптомы" in text
    assert "длительность и частота" in text
    assert "дневник" in text
    assert "тревожные признаки" in text
    assert "не выдумывай" in text


def test_treatment_questions_add_safety_and_dosage_constraints():
    requirements = RagService._answer_quality_requirements(
        "Какие препараты применяют для лечения мигрени и какие дозировки рекомендуются?"
    )
    text = "\n".join(requirements).casefold()

    assert "противопоказания" in text
    assert "дозу" in text
    assert "не предлагай индивидуальную схему лечения" in text


def test_quality_review_prompt_treats_draft_as_untrusted_and_preserves_source_boundaries():
    prompt = RagService._build_quality_review_prompt(
        base_prompt="Источники: [WEB1] руководство NICE. Допустимая цитата: [WEB1].",
        question="Какие рекомендации по диагностике мигрени?",
        draft_answer="Мигрень подтверждается одним симптомом [WEB1].",
    )

    assert "черновик, а не источник доказательств" in prompt
    assert "Улучши полноту" in prompt
    assert "не добавляй факты из памяти модели" in prompt
    assert "не превращай" in prompt or "диагностический критерий" in prompt
    assert "Мигрень подтверждается одним симптомом [WEB1]." in prompt


def test_general_question_does_not_get_diagnostic_specific_checklist():
    requirements = RagService._answer_quality_requirements(
        "Как записать пациента к травматологу?"
    )
    text = "\n".join(requirements).casefold()

    assert "клинические признаки и характеристики состояния" not in text
    assert "каждый существенный медицинский тезис" in text


def test_content_check_rejects_aura_claim_that_makes_headache_mandatory():
    sources = [{"citation": "[WEB1]", "title": "NICE guideline", "snippet": "Migraine with aura can be diagnosed with or without headache."}]
    evidence = {"[WEB1]": "Migraine with aura can be diagnosed with or without headache. Typical aura symptoms are fully reversible."}
    answer = "Мигрень с аурой диагностируется при наличии симптомов ауры, сопровождающихся головной болью [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени с аурой у взрослых?",
        answer,
        sources,
        evidence,
    )

    assert any("головную боль как обязательное условие" in issue for issue in issues)


def test_content_check_rejects_wrong_age_scope_for_adults():
    sources = [{"citation": "[WEB1]", "title": "NICE guideline", "snippet": "The guideline covers young people aged 12 years and older and adults."}]
    answer = "Рекомендации относятся к взрослым пациентам старше 12 лет [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": sources[0]["snippet"]},
    )

    assert any("возрастной группы" in issue for issue in issues)


def test_content_check_rejects_unsupported_clinical_numeric_values():
    sources = [{"citation": "[WEB1]", "title": "NICE overview", "snippet": "Overview of headache diagnosis and management."}]
    answer = "Приступ мигрени длится от 4 до 72 часов [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": sources[0]["snippet"]},
    )

    assert any("Числовые клинические значения" in issue for issue in issues)


def test_content_check_accepts_numeric_values_present_in_cited_evidence():
    evidence_text = (
        "Migraine headache lasts 4 to 72 hours. Aura symptoms develop over at least 5 minutes "
        "and last for 5 to 60 minutes."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendation", "snippet": evidence_text}]
    answer = "Приступ длится 4–72 часа. Симптомы ауры развиваются не менее 5 минут и длятся 5–60 минут [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert not any("Числовые клинические значения" in issue for issue in issues)


def test_content_check_detects_missing_red_flags_and_unsupported_concepts():
    evidence_text = (
        "Consider further investigations for sudden-onset headache reaching maximum intensity within 5 minutes. "
        "Consider using a headache diary."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = "Для диагностики оценивают фотобоязнь и исключают опухоли мозга [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert any("тревожные признаки" in issue for issue in issues)
    assert any("светобоязнь" in issue for issue in issues)
    assert any("опухоли" in issue for issue in issues)
    assert any("дневник головной боли" in issue for issue in issues)


def test_quality_prompt_explicitly_checks_polarity_population_and_numeric_support():
    prompt = RagService._build_quality_review_prompt(
        base_prompt="Источники: [WEB1].",
        question="Какие современные рекомендации по диагностике мигрени у взрослых?",
        draft_answer="Мигрень с аурой требует головной боли. [WEB1]",
        content_issues=["Числовые клинические значения не подтверждены."],
    )

    assert "отрицания" in prompt
    assert "головная боль обязательна" in prompt
    assert "старше 12 лет" in prompt
    assert "Числовые клинические значения не подтверждены." in prompt


def test_gigachat_system_instructions_enforce_source_grounding_and_scope():
    from app.services.gigachat import GigaChatClient

    client = GigaChatClient.__new__(GigaChatClient)
    captured = {}
    client.chat_messages = lambda messages: captured.setdefault("messages", messages) or ""
    client.chat("question")
    system_prompt = captured["messages"][0]["content"].casefold()

    assert "сохраняй числа, единицы" in system_prompt
    assert "не делай головную боль обязательным условием ауры" in system_prompt
    assert "если вопрос об взрослых — отвечай про взрослых" in system_prompt
    assert "не ставь персональный диагноз" in system_prompt


def test_content_check_flags_substantive_claim_lines_without_local_citations():
    sources = [{"citation": "[WEB1]", "title": "NICE", "snippet": "Source text."}]
    answer = (
        "Современные рекомендации требуют оценки клинических характеристик и анамнеза пациента.\n\n"
        "Для каждого подтверждённого тезиса источник указан [WEB1]."
    )

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": "Source text."},
    )

    assert any("без локальной ссылки" in issue for issue in issues)


def test_content_check_allows_cited_claims_and_bolded_section_labels():
    sources = [{"citation": "[WEB1]", "title": "NICE", "snippet": "Source text."}]
    answer = (
        "**Оценка и диагностика**\n"
        "Оценивают длительность головной боли и сопутствующие симптомы [WEB1]."
    )

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": "Source text."},
    )

    assert not any("без локальной ссылки" in issue for issue in issues)


def test_review_issue_diagnostics_classify_common_medical_failure_reasons():
    from app.services.rag import RagService

    issues = [
        "Числовые клинические значения не подтверждаются процитированным текстом источников: 4–72 (hour).",
        "Несоответствие возрастной группы: вопрос об взрослых.",
        "Потенциальное искажение критерия ауры: нельзя представлять головную боль как обязательное условие.",
        "В процитированном источнике есть тревожные признаки/показания к обследованию, но ответ их пропускает.",
    ]
    details = RagService._issue_details(issues)

    assert [item["category"] for item in details] == [
        "numeric_support",
        "population_scope",
        "clinical_polarity",
        "red_flags_omission",
    ]
    assert [item["message"] for item in details] == issues


def test_answer_review_diagnostics_has_stable_empty_shape():
    from app.services.rag import RagService

    diagnostics = RagService._answer_review_diagnostics()

    assert diagnostics["status"] == "not_run"
    assert diagnostics["stage"] == "not_started"
    assert diagnostics["initial_issues"] == []
    assert diagnostics["reviewed_issues"] == []
    assert diagnostics["repaired_issues"] == []
    assert diagnostics["final_issues"] == []
    assert diagnostics["attempts"]["initial_generation"] is False


def test_numeric_endpoint_is_supported_by_source_range():
    assert RagService._numeric_fact_is_supported(
        (("72",), "hour"),
        {(("4", "72"), "hour")},
    )


def test_adult_answer_normalization_removes_wrong_over_12_caveat():
    answer = (
        "Продолжительность приступа у взрослых составляет 4–72 часа [WEB1].\n\n"
        "Представленные выше критерии относятся исключительно к взрослым пациентам старше 12 лет.\n"
        "Для диагностики мигрени у детей существуют отдельные правила."
    )

    normalized = RagService._normalize_answer_for_question(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        answer,
    )

    assert "4–72 часа" in normalized
    assert "старше 12 лет" not in normalized
    assert "у детей" not in normalized


def test_diagnostic_completion_adds_cited_diary_and_red_flags_from_evidence():
    evidence = (
        "[WEB1] Recommendations: Consider using a headache diary to aid the diagnosis of primary headaches. "
        "Record frequency, duration and severity of headaches, associated symptoms, all prescribed and over the "
        "counter medications taken to relieve headaches, possible precipitants and relationship of headaches to "
        "menstruation for a minimum of 8 weeks. Evaluate people with worsening headache with fever, sudden-onset "
        "headache reaching maximum intensity within 5 minutes, new-onset neurological deficit, impaired level "
        "of consciousness, recent head trauma, headache triggered by cough or sneeze, headache triggered by "
        "exercise, orthostatic headache, symptoms suggestive of giant cell arteritis, acute narrow angle glaucoma "
        "or a substantial change in the characteristics of their headache."
    )
    answer = "Оценивают характер боли, сопутствующие симптомы и продолжительность приступа [WEB1]."

    completed = RagService._complete_diagnostic_answer_from_evidence(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        answer,
        {"[WEB1]": evidence},
    )

    assert "дневник головной боли" in completed.casefold()
    assert "8 недель" in completed
    assert "дальнейшее обследование или направление" in completed.casefold()
    assert "внезапная головная боль" in completed.casefold()
    assert completed.count("[WEB1]") >= 3


def test_numeric_validation_accepts_adult_duration_even_if_source_also_has_pediatric_range():
    evidence_text = (
        "Duration of headache: 4 to 72 hours in adults; 1 to 72 hours in young people aged 12 to 17 years. "
        "Aura symptoms develop over at least 5 minutes and last 5 to 60 minutes."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = "У взрослых приступ мигрени может длиться 4–72 часа [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert not any("Числовые клинические значения" in issue for issue in issues)


def test_uncited_checker_accepts_multiline_claims_cited_at_end_of_markdown_paragraph():
    answer = (
        "Характеристики головной боли:\n"
        "Боль может быть односторонней или двусторонней, а обычная активность может усиливать её. [WEB1]\n\n"
        "Независимый тезис без источника, который требует отдельной проверки."
    )

    missing = RagService._uncited_substantive_lines(answer)

    assert any("Независимый тезис" in item for item in missing)
    assert not any("односторонней" in item for item in missing)


def test_content_check_detects_mixing_migraine_and_tension_headache_features():
    evidence_text = (
        "Tension-type headache pain quality is pressing/tightening (non-pulsating). "
        "Migraine pain quality is pulsating and its intensity is moderate or severe."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = "При мигрени боль обычно пульсирующая или давящая [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert any("смешение типов головной боли" in issue for issue in issues)


def test_completed_diagnostic_answer_does_not_fail_for_supported_diary_and_red_flags():
    evidence_text = (
        "Consider using a headache diary to aid the diagnosis of primary headaches. Record frequency, duration "
        "and severity of headaches, associated symptoms, all prescribed and over the counter medications taken "
        "to relieve headaches, possible precipitants and relationship of headaches to menstruation for a minimum "
        "of 8 weeks. Evaluate people who present with worsening headache with fever, sudden-onset headache "
        "reaching maximum intensity within 5 minutes, new-onset neurological deficit, new-onset cognitive "
        "dysfunction, change in personality, impaired level of consciousness, recent (typically within the past "
        "3 months) head trauma, headache triggered by cough, valsalva or sneeze, headache triggered by exercise, "
        "orthostatic headache, symptoms suggestive of giant cell arteritis, acute narrow angle glaucoma or a "
        "substantial change in the characteristics of their headache. Migraine pain quality is pulsating and "
        "its duration is 4 to 72 hours in adults. Symptoms of aura can occur with or without headache and develop "
        "over at least 5 minutes and last 5 to 60 minutes."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = (
        "Мигренозная боль может быть односторонней или двусторонней, пульсирующей, умеренной или сильной и "
        "усиливаться при обычной активности; приступ длится 4–72 часа у взрослых [WEB1].\n\n"
        "Аура может возникать с головной болью или без неё, развиваться постепенно не менее 5 минут и "
        "длиться 5–60 минут [WEB1]."
    )
    completed = RagService._complete_diagnostic_answer_from_evidence(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", answer, {"[WEB1]": evidence_text}
    )
    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        completed,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert "дневник головной боли" in completed.casefold()
    assert "дальнейшее обследование или направление" in completed.casefold()
    assert "старше 12 лет" not in completed
    assert not any("дневник головной боли" in issue for issue in issues)
    assert not any("тревожные признаки" in issue for issue in issues)
    assert not any("Числовые клинические значения" in issue for issue in issues)
    assert not any("смешение типов головной боли" in issue for issue in issues)


def test_content_check_detects_mixing_migraine_and_tension_headache_features():
    evidence_text = (
        "Tension-type headache pain quality is pressing/tightening (non-pulsating). "
        "Migraine pain quality is pulsating and its intensity is moderate or severe."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = "При мигрени боль обычно пульсирующая или давящая [WEB1]."

    issues = RagService._answer_content_issues(
        "Какие рекомендации по диагностике мигрени у взрослых?",
        answer,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert any("смешение типов головной боли" in issue for issue in issues)


def test_completed_diagnostic_answer_does_not_fail_for_supported_diary_and_red_flags():
    evidence_text = (
        "Consider using a headache diary to aid the diagnosis of primary headaches. Record frequency, duration "
        "and severity of headaches, associated symptoms, all prescribed and over the counter medications taken "
        "to relieve headaches, possible precipitants and relationship of headaches to menstruation for a minimum "
        "of 8 weeks. Evaluate people who present with worsening headache with fever, sudden-onset headache "
        "reaching maximum intensity within 5 minutes, new-onset neurological deficit, new-onset cognitive "
        "dysfunction, change in personality, impaired level of consciousness, recent (typically within the past "
        "3 months) head trauma, headache triggered by cough, valsalva or sneeze, headache triggered by exercise, "
        "orthostatic headache, symptoms suggestive of giant cell arteritis, acute narrow angle glaucoma or a "
        "substantial change in the characteristics of their headache. Migraine pain quality is pulsating and "
        "its duration is 4 to 72 hours in adults. Symptoms of aura can occur with or without headache and develop "
        "over at least 5 minutes and last 5 to 60 minutes."
    )
    sources = [{"citation": "[WEB1]", "title": "NICE recommendations", "snippet": evidence_text}]
    answer = (
        "Мигренозная боль может быть односторонней или двусторонней, пульсирующей, умеренной или сильной и "
        "усиливаться при обычной активности; приступ длится 4–72 часа у взрослых [WEB1].\n\n"
        "Аура может возникать с головной болью или без неё, развиваться постепенно не менее 5 минут и "
        "длиться 5–60 минут [WEB1]."
    )
    completed = RagService._complete_diagnostic_answer_from_evidence(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", answer, {"[WEB1]": evidence_text}
    )
    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        completed,
        sources,
        {"[WEB1]": evidence_text},
    )

    assert "дневник головной боли" in completed.casefold()
    assert "дальнейшее обследование или направление" in completed.casefold()
    assert "старше 12 лет" not in completed
    assert not any("дневник головной боли" in issue for issue in issues)
    assert not any("тревожные признаки" in issue for issue in issues)
    assert not any("Числовые клинические значения" in issue for issue in issues)
    assert not any("смешение типов головной боли" in issue for issue in issues)


def test_source_grounded_normalization_separates_migraine_pain_and_corrects_aura_wording():
    evidence_text = (
        "Tension-type headache pain quality is pressing/tightening (non-pulsating). "
        "Migraine pain quality is pulsating. Symptoms of aura can occur with or without headache and are "
        "fully reversible, develop over at least 5 minutes and last 5 to 60 minutes."
    )
    answer = (
        "При мигрени боль может быть пульсирующей или давящей [WEB1]. "
        "Наличие ауры перед началом головной боли или во время нее [WEB1]."
    )

    completed = RagService._complete_diagnostic_answer_from_evidence(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        answer,
        {"[WEB1]": evidence_text},
    )

    assert "пульсирующей или давящей" not in completed
    assert "Аура может возникать с головной болью или без неё" in completed
    assert "5–60 минут" in completed
    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        completed,
        [{"citation": "[WEB1]", "title": "NICE", "snippet": evidence_text}],
        {"[WEB1]": evidence_text},
    )
    assert not any("смешение типов головной боли" in issue for issue in issues)
    assert not any("головную боль как обязательное условие" in issue for issue in issues)


def test_auto_completed_sections_do_not_misattributable_to_nice_when_source_is_not_nice():
    evidence_text = (
        "Consider using a headache diary to aid primary headache diagnosis. Record frequency, duration and severity. "
        "Further investigation is advised for sudden-onset headache reaching maximum intensity within 5 minutes."
    )
    answer = "Оценка головной боли и сопутствующих симптомов [WEB1]."

    completed = RagService._complete_diagnostic_answer_from_evidence(
        "Какие рекомендации по диагностике головной боли у взрослых?",
        answer,
        {"[WEB1]": evidence_text},
    )

    assert "Источник предлагает рассмотреть дневник" in completed
    assert "NICE предлагает рассмотреть дневник" not in completed


def test_sound_sensitivity_is_supported_by_nice_wording_light_and_or_sound():
    evidence_text = (
        "Migraine symptoms include unusual sensitivity to light and/or sound or nausea and/or vomiting."
    )
    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        "При мигрени возможна чувствительность к свету и звуку [WEB1].",
        [{"citation": "[WEB1]", "title": "NICE", "snippet": evidence_text}],
        {"[WEB1]": evidence_text},
    )
    assert not any("звукочувствительность" in issue for issue in issues)


def test_one_source_auto_citation_fixes_missing_local_citations_without_llm_retry():
    answer = (
        "Боль может быть односторонней или двусторонней, а интенсивность — умеренной или сильной.\n\n"
        "Симптомы ауры развиваются постепенно и длятся 5–60 минут."
    )
    result = RagService._add_citations_to_uncited_blocks(
        answer, [{"citation": "[WEB1]", "source_id": "WEB1"}]
    )
    assert result.count("[WEB1]") == 2
    assert not RagService._uncited_substantive_lines(result)


def test_gigachat_request_sets_output_token_limit_and_captures_provider_usage(monkeypatch):
    from types import SimpleNamespace
    from app.services.gigachat import GigaChatClient

    captured = {}

    class FakeResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "choices": [{"message": {"content": "Ответ [WEB1]."}}],
                "usage": {"prompt_tokens": 123, "completion_tokens": 87, "total_tokens": 210},
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.gigachat.requests.post", fake_post)
    client = GigaChatClient.__new__(GigaChatClient)
    client.settings = SimpleNamespace(
        gigachat_base_url="https://api.giga.chat/v1",
        gigachat_model="GigaChat-2",
        gigachat_verify_ssl=False,
        gigachat_max_tokens=700,
    )
    client._token = "cached-token"
    client._expires_at = 9999999999
    client._lock = __import__("threading").Lock()
    client.last_usage = {}

    answer = client.chat_messages([{"role": "user", "content": "test"}])
    assert answer == "Ответ [WEB1]."
    assert captured["json"]["max_tokens"] == 700
    assert client.last_usage == {"prompt_tokens": 123, "completion_tokens": 87, "total_tokens": 210}


def test_resource_usage_uses_actual_provider_token_counts(monkeypatch):
    class Settings:
        gigachat_max_tokens = 700
    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    usage = RagService._resource_usage(
        "some prompt", gigachat_calls=1, embedding_calls=1,
        provider_usage={"prompt_tokens": 123, "completion_tokens": 87, "total_tokens": 210},
    )
    assert usage["gigachat_calls"] == 1
    assert usage["embedding_api_calls"] == 1
    assert usage["input_tokens"] == 123
    assert usage["output_tokens"] == 87
    assert usage["total_tokens"] == 210
    assert usage["usage_source"] == "provider"


def test_embedding_usage_is_cleared_when_provider_returns_no_usage(monkeypatch):
    from types import SimpleNamespace
    from app.services.embeddings import EmbeddingClient

    client = EmbeddingClient.__new__(EmbeddingClient)
    client.model = "Qwen/Qwen3-Embedding-0.6B"
    client.batch_size = 32
    client.last_usage = {"prompt_tokens": 999, "total_tokens": 999}
    client.client = SimpleNamespace(embeddings=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=[0.1, 0.2])],
    )))

    assert client.embed_one("test query") == [0.1, 0.2]
    assert client.last_usage == {}


def test_nice_migraine_excerpt_preserves_diagnosis_aura_diary_and_red_flags(monkeypatch):
    from types import SimpleNamespace
    from app.services.web_search import WebSearchResult

    monkeypatch.setattr(
        "app.services.rag.get_settings",
        lambda: SimpleNamespace(rag_max_web_sources=2, rag_max_source_chars=4200),
    )
    text = (
        "Headaches in over 12s NICE CG150 "
        "1.1.1 Evaluate people who present with headache and the following: worsening headache with fever; "
        "sudden-onset headache reaching maximum intensity within 5 minutes; new-onset neurological deficit; "
        "impaired level of consciousness; recent head trauma; headache triggered by cough, valsalva or sneeze; "
        "headache triggered by exercise; orthostatic headache; symptoms suggestive of giant cell arteritis; "
        "acute narrow angle glaucoma; a substantial change in the characteristics of their headache. "
        "1.1.2 Consider further investigations. 1.1.3 Consider using a headache diary to aid the diagnosis "
        "of primary headaches. 1.1.4 Record frequency, duration and severity, associated symptoms, medications, "
        "possible precipitants and relationship to menstruation for a minimum of 8 weeks. "
        "1.2 Diagnosis Table 1 Headache features according to headache type Pain location Bilateral Unilateral or bilateral "
        "Pain quality Pressing/tightening Pulsating Pain intensity Mild or moderate Moderate or severe "
        "Effect on activities Not aggravated by routine activities Aggravated by or causes avoidance of routine activities "
        "Other symptoms None Unusual sensitivity to light and/or sound or nausea and/or vomiting. "
        "Duration of headache 30 minutes to continuous 4 to 72 hours in adults 1 to 72 hours in young people aged 12 to 17 years. "
        "Frequency Episodic migraine on fewer than 15 days per month. Chronic migraine on 15 or more days per month, "
        "with at least 8 days having features of migraine, for more than 3 months. Migraine with aura 1.2.2 Suspect aura "
        "in people who present with or without headache and with neurological symptoms that are fully reversible, "
        "develop over at least 5 minutes and last 5 to 60 minutes. 1.2.3 Diagnose migraine with aura with typical visual, "
        "sensory or speech symptoms. 1.2.4 Consider referral for atypical aura symptoms. Menstrual-related migraine."
    )
    result = WebSearchResult(
        title="Headaches in over 12s: diagnosis and management - NICE",
        url="https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
        snippet=text,
        rank=1,
        domain="www.nice.org.uk",
    )

    compacted = RagService._compact_web_results(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", [result]
    )[0]
    compact = compacted.snippet.casefold()
    assert len(compact) <= 4200
    assert "4 to 72 hours in adults" in compact
    assert "develop over at least 5 minutes" in compact
    assert "minimum of 8 weeks" in compact
    assert "sudden-onset headache reaching maximum intensity within 5 minutes" in compact
    assert "last 5 to 60 minutes" in compact
    compact_answer = RagService._build_concise_migraine_diagnostic_answer(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        {"[WEB1]": f"NICE {compacted.url} {compact}"},
    )
    assert compact_answer is not None
    assert "4–72 часа" in compact_answer
    assert "5–60 минут" in compact_answer
    assert "дневник" in compact_answer.casefold()
    assert "обследование/направление" in compact_answer.casefold()


def test_concise_nice_migraine_answer_is_substantive_and_citation_grounded():
    evidence = (
        "NICE https://www.nice.org.uk/guidance/cg150/chapter/recommendations "
        "Table 1 Headache features according to headache type Pain location Unilateral or bilateral "
        "Pain quality Pulsating Pain intensity Moderate or severe Effect on activities Aggravated by, or causes avoidance of, "
        "routine activities of daily living Other symptoms Unusual sensitivity to light and/or sound or nausea and/or vomiting. "
        "Duration of headache 4 to 72 hours in adults. Episodic migraine (with or without aura) on fewer than 15 days per month. "
        "Chronic migraine (with or without aura) on 15 or more days per month, with at least 8 days having features of migraine, "
        "for more than 3 months. 1.1.3 Consider using a headache diary. 1.1.4 Record frequency, duration and severity, "
        "associated symptoms, medications, possible precipitants and relationship to menstruation for a minimum of 8 weeks. "
        "1.1.1 Evaluate people with worsening headache with fever; sudden-onset headache reaching maximum intensity within 5 minutes; "
        "new-onset neurological deficit; new-onset cognitive dysfunction; change in personality; impaired level of consciousness; "
        "recent head trauma; headache triggered by cough, valsalva or sneeze; headache triggered by exercise; orthostatic headache; "
        "symptoms suggestive of giant cell arteritis; acute narrow angle glaucoma; a substantial change in the characteristics of their headache. "
        "Symptoms of aura can occur with or without headache and are fully reversible, develop over at least 5 minutes and last 5 to 60 minutes. "
        "Typical aura symptoms include visual symptoms, sensory symptoms and speech disturbance."
    )
    answer = RagService._build_concise_migraine_diagnostic_answer(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", {"[WEB1]": evidence}
    )
    assert answer is not None
    assert "односторонней или двусторонней" in answer
    assert "4–72 часа" in answer
    assert "5–60 минут" in answer
    assert "15 дней" in answer
    assert "дневник" in answer.casefold()
    assert "внезапной боли" in answer.casefold()
    assert answer.count("[WEB1]") >= 4
    assert len(answer.split()) < 190


def test_no_gigachat_usage_when_no_model_call_was_made(monkeypatch):
    class Settings:
        gigachat_max_tokens = 450

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    usage = RagService._resource_usage("", gigachat_calls=0, embedding_calls=1)
    assert usage["gigachat_calls"] == 0
    assert usage["usage_source"] == "not_called"
    assert usage["estimated_input_tokens"] == 0
    assert usage["max_output_tokens"] == 450


def test_concise_template_reports_partial_nice_snippet_without_inventing_missing_criteria():
    evidence = (
        "NICE https://www.nice.org.uk/guidance/cg150/chapter/recommendations "
        "Table 1 Headache features according to headache type Pain location Bilateral Unilateral or bilateral "
        "Unilateral around the eye Pain quality Pressing/tightening (non-pulsating) Pulsating Variable."
    )
    answer = RagService._build_concise_migraine_diagnostic_answer(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", {"[WEB1]": evidence}
    )
    assert answer is not None
    assert "односторонняя или двусторонняя" in answer
    assert "пульсирующий характер" in answer
    assert "нельзя" in answer.casefold()
    assert "[WEB1]" in answer
    assert "4–72" not in answer
    assert "5–60" not in answer
    source = {
        "source_id": "WEB1",
        "citation": "[WEB1]",
        "title": "Headaches in over 12s: diagnosis and management - NICE",
        "url": "https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
        "snippet": evidence,
    }
    issues = RagService._answer_content_issues(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        answer,
        [source],
        {"[WEB1]": evidence},
    )
    assert issues == []


def test_guideline_answer_deduplication_removes_redundant_intro_and_red_flag_section():
    answer = (
        "Современные рекомендации по диагностике мигрени у взрослых включают:\n\n"
        "1. Оценку симптомов и признаков, характерных для мигрени ([WEB1]).\n"
        "2. Использование дневника головной боли для документирования частоты приступов ([WEB1]).\n"
        "3. Диагностику мигрени на основе таблицы клинических характеристик головной боли ([WEB1]).\n\n"
        "**Признаки мигрени у взрослых.** Приступ длится 4–72 часа. [WEB1]\n\n"
        "**Дневник головной боли.** Фиксируйте частоту и длительность боли минимум 8 недель. [WEB1]\n\n"
        "**Когда рассмотреть обследование/направление.** Внезапная головная боль с максимумом за 5 минут; "
        "новый неврологический дефицит; снижение уровня сознания. [WEB1]\n\n"
        "**Когда требуется дальнейшее обследование или направление.** Внезапная головная боль с максимумом "
        "за 5 минут; новый неврологический дефицит. [WEB1]"
    )

    cleaned = RagService._deduplicate_guideline_answer(answer)

    assert "Современные рекомендации по диагностике мигрени у взрослых включают:" not in cleaned
    assert cleaned.count("**Дневник головной боли.**") == 1
    red_flag_headings = (
        cleaned.count("**Когда рассмотреть обследование/направление.**")
        + cleaned.count("**Когда требуется дальнейшее обследование или направление.**")
    )
    assert red_flag_headings == 1
    assert "новый неврологический дефицит" in cleaned


def test_guideline_answer_deduplication_keeps_answer_without_redundancy_unchanged():
    answer = (
        "**Признаки мигрени у взрослых.** Приступ длится 4–72 часа. [WEB1]\n\n"
        "**Аура.** Симптомы развиваются постепенно и длятся 5–60 минут. [WEB1]"
    )

    assert RagService._deduplicate_guideline_answer(answer) == answer
