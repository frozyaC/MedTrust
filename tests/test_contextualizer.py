from app.services.contextualizer import ContextualizationResult, LLMContextualizer


def test_short_attribute_questions_are_detected_as_fragments() -> None:
    assert LLMContextualizer._is_fragment("стоимость")
    assert LLMContextualizer._is_fragment("А подготовка?")
    assert LLMContextualizer._is_fragment("сколько стоит?")
    assert not LLMContextualizer._is_fragment("Какие противопоказания у гастроскопии?")


def test_extract_json_accepts_json_fenced_model_response() -> None:
    result = LLMContextualizer._extract_json(
        '```json\n{"intent":"follow_up","resolved_query":"Стоимость анализа ОАК"}\n```'
    )
    assert result["intent"] == "follow_up"
    assert result["resolved_query"] == "Стоимость анализа ОАК"


def test_valid_follow_up_result_keeps_normalized_query() -> None:
    result = LLMContextualizer._result_from_payload(
        {
            "intent": "follow_up",
            "resolved_query": "Стоимость общего анализа крови (ОАК)",
            "entities": {"service": "ОАК"},
            "corrections": [],
            "confidence": 0.94,
            "clarification_required": False,
            "clarification_question": None,
        },
        "стоимость",
        "previous-message-id",
    )
    assert result.resolved_query == "Стоимость общего анализа крови (ОАК)"
    assert result.clarification_required is False
    assert result.depends_on_message_id == "previous-message-id"


def test_ambiguous_result_requires_clarification_and_cannot_be_searched() -> None:
    result = LLMContextualizer._result_from_payload(
        {
            "intent": "ambiguous",
            "resolved_query": None,
            "entities": {},
            "corrections": [],
            "confidence": 0.42,
            "clarification_required": True,
            "clarification_question": "Стоимость какого анализа вы имеете в виду?",
        },
        "стоимость",
        None,
    )
    assert result.clarification_required is True
    assert result.resolved_query is None
    assert result.clarification_question == "Стоимость какого анализа вы имеете в виду?"


def test_new_question_without_model_query_falls_back_to_original_question() -> None:
    result = LLMContextualizer._result_from_payload(
        {"intent": "new_question", "resolved_query": None, "confidence": 0.7},
        "Какие противопоказания нужно проверить перед гастроскопией?",
        None,
    )
    assert result.resolved_query == "Какие противопоказания нужно проверить перед гастроскопией?"
    assert result.clarification_required is False


def test_fallback_for_fragment_without_context_asks_a_question() -> None:
    result = LLMContextualizer._fallback_result("стоимость", {}, {"messages": []}, None)
    assert result.clarification_required is True
    assert result.resolved_query is None
    assert result.clarification_question


def test_fallback_with_context_preserves_topic_in_search_query() -> None:
    result = LLMContextualizer._fallback_result(
        "подготовка",
        {
            "last_resolved_query": "Состав общего анализа крови (ОАК)",
            "entities": {"service": "ОАК"},
        },
        {"messages": [{"role": "user", "content": "Что входит в ОАК?"}]},
        "previous-message-id",
    )
    assert result.clarification_required is False
    assert result.resolved_query is not None
    assert "контекст предыдущего запроса" in result.resolved_query
    assert "ОАК" in result.resolved_query


def test_result_contract_contains_only_safe_expected_fields() -> None:
    result = ContextualizationResult(
        intent="new_question",
        resolved_query="Подготовка к ОАК",
        entities={"service": "ОАК"},
        corrections=[],
        confidence=0.9,
        clarification_required=False,
        clarification_question=None,
    ).as_dict()
    assert result["resolved_query"] == "Подготовка к ОАК"
    assert result["clarification_required"] is False
    assert "depends_on_message_id" in result


def test_single_topic_short_follow_up_resolves_to_gastroscopy_price() -> None:
    result = LLMContextualizer._deterministic_fragment_result(
        "Сколько стоит?",
        {
            "last_resolved_query": "Подготовка к гастроскопии",
            "entities": {"service": "гастроскопия"},
            "active_topic": "гастроскопия",
        },
        {"messages": [{"role": "user", "content": "А подготовка?"}]},
        "previous-message-id",
    )
    assert result is not None
    assert result.clarification_required is False
    assert result.resolved_query == "Стоимость гастроскопии (ФГДС): актуальные цены и диапазон цен в клиниках"
    assert result.intent == "follow_up"


def test_short_price_follow_up_after_comparison_asks_which_service() -> None:
    comparison = "Сравни подготовку к общему анализу крови (ОАК) и биохимическому анализу крови."
    result = LLMContextualizer._deterministic_fragment_result(
        "Сколько стоит?",
        {"last_resolved_query": comparison, "entities": {}, "active_topic": None},
        {"messages": [{"role": "user", "content": comparison}]},
        "previous-message-id",
    )
    assert result is not None
    assert result.clarification_required is True
    assert result.resolved_query is None
    assert "ОАК" in (result.clarification_question or "")
    assert "биохимический анализ крови" in (result.clarification_question or "")


def test_short_follow_up_without_any_topic_requires_clarification() -> None:
    result = LLMContextualizer._deterministic_fragment_result(
        "Стоимость", {}, {"messages": []}, None
    )
    assert result is not None
    assert result.clarification_required is True
    assert result.resolved_query is None


def test_answer_to_pending_price_clarification_resolves_cost_of_cbc() -> None:
    result = LLMContextualizer._deterministic_fragment_result(
        "ОАК",
        {"pending_question": "Сколько стоит?"},
        {"messages": []},
        "previous-message-id",
    )
    assert result is not None
    assert result.clarification_required is False
    assert result.resolved_query == "Стоимость общего анализа крови (ОАК): актуальные цены и диапазон цен в лабораториях"
    assert result.status == "resolved_from_clarification_reply"


def test_gastroscopy_follow_up_uses_a_standalone_preparation_query() -> None:
    result = LLMContextualizer._deterministic_fragment_result(
        "А подготовка?",
        {"last_resolved_query": "Противопоказания перед гастроскопией", "entities": {}},
        {"messages": [{"role": "user", "content": "Какие противопоказания перед гастроскопией?"}]},
        "previous-message-id",
    )
    assert result is not None
    assert result.resolved_query == "Подготовка к гастроскопии"
    assert result.clarification_required is False


def test_obvious_typo_is_corrected_and_reported() -> None:
    resolved, corrections = LLMContextualizer._apply_obvious_typos(
        "Какая подготвока нужна перед гатроскопией?",
        "Какая подготвока нужна перед гатроскопией?",
    )
    assert resolved == "Какая подготовка нужна перед гастроскопией?"
    assert {item["original"] for item in corrections} == {"подготвока", "гатроскопией"}


def test_new_full_question_is_not_misread_as_answer_to_pending_clarification() -> None:
    result = LLMContextualizer._deterministic_fragment_result(
        "Какие противопоказания проверить перед гастроскопией?",
        {"pending_question": "Сколько стоит?"},
        {"messages": []},
        "previous-message-id",
    )
    assert result is None
