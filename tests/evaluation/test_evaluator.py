from __future__ import annotations

from evaluator import evaluate_case, normalize_path, summarize
from run_evaluation import validate_dataset


def _case(**overrides):
    value = {
        "id": "QX", "question": "test", "category": "test",
        "knowledge_coverage": "full", "expected_facts": ["не есть 8 часов"],
        "missing_facts": "", "expected_source_paths": ["Словарь/УЗИ/УЗИ_ОБП.md"],
        "expected_fact_aliases": {
            "не есть 8 часов": ["за 8 часов до процедуры воздержаться от приема пищи"]
        },
    }
    value.update(overrides)
    return value


def test_path_normalization_ignores_repository_prefix_and_markdown_extension():
    expected = "Словарь/Лаборатория/Анализы_крови/ОАК.md"
    actual = "Регистратура\\Словарь\\Лаборатория\\Анализы_крови\\ОАК"
    assert normalize_path(expected) == normalize_path(actual)


def test_equivalent_fasting_phrase_is_matched():
    result = evaluate_case(
        _case(),
        {
            "answer": "За 8 часов до процедуры воздержаться от приема пищи.",
            "sources": [{"source_id": "W1", "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП", "used_in_answer": True}],
            "retrieval": [{"path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП"}],
            "source_checks_passed": True,
            "answer_review_diagnostics": {"status": "passed", "used_source_ids": ["W1"]},
        },
    )
    assert result["fact_coverage"] == 1.0
    assert result["matched_facts"] == ["не есть 8 часов"]
    assert result["expected_sources_used"] is True
    assert result["status"] == "passed"


def test_code_is_never_matched_when_numeric_identifier_is_missing():
    result = evaluate_case(
        _case(expected_facts=["ОАК развернутый, код 14501"], expected_fact_aliases={}),
        {"answer": "Общий анализ крови развернутый.", "sources": [], "retrieval": [], "source_checks_passed": False},
    )
    assert result["fact_coverage"] == 0.0
    assert result["fact_match_details"][0]["method"] == "numeric_requirement_missing"


def test_relation_fact_needs_explicit_relation_matcher():
    result = evaluate_case(
        _case(
            expected_facts=["8 рабочих дней отсчитываются после готовности исследования в клинике"],
            expected_fact_aliases={},
        ),
        {"answer": "8 рабочих дней. В клинике исследование занимает 2 дня.", "sources": [], "retrieval": []},
    )
    assert result["fact_coverage"] == 0.0
    assert result["fact_match_details"][0]["method"] == "explicit_relation_matcher_required"


def test_absent_case_does_not_fail_for_unused_irrelevant_retrieval_candidates():
    result = evaluate_case(
        _case(knowledge_coverage="absent", expected_facts=[], expected_source_paths=[], missing_facts="ответ отсутствует"),
        {
            "answer": "В локальной базе знаний нет данных по этому вопросу.",
            "sources": [{"source_id": "W1", "path": "Регистратура/Скрипты/Общее", "used_in_answer": False}],
            "retrieval": [{"path": "Регистратура/Скрипты/Общее"}],
            "answer_review_diagnostics": {"used_source_ids": []},
        },
    )
    assert result["status"] == "passed"
    assert result["score"] == 3


def test_partial_case_requires_gap_disclosure_related_to_missing_topic():
    case = _case(knowledge_coverage="partial", missing_facts="стоимость услуги не указана")
    response = {
        "answer": "За 8 часов до процедуры воздержаться от приема пищи. Стоимость услуги в базе знаний не указана.",
        "sources": [{"source_id": "W1", "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП", "used_in_answer": True}],
        "retrieval": [{"path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП"}],
        "source_checks_passed": True,
        "answer_review_diagnostics": {"status": "passed", "used_source_ids": ["W1"]},
    }
    result = evaluate_case(case, response)
    assert result["missing_facts_disclosed"] is True


def test_summary_includes_needs_review_by_category():
    summary = summarize([
        {"category": "A", "status": "passed", "score": 5, "max_score": 5},
        {"category": "A", "status": "needs_review", "score": 2, "max_score": 5},
    ])
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["needs_review"] == 1
    assert summary["by_category"]["A"]["needs_review"] == 1


def test_path_normalization_removes_nested_knowledge_base_and_registry_prefixes():
    assert normalize_path("knowledge-base/Регистратура/Словарь/УЗИ/УЗИ_ОБП.md") == normalize_path(
        "Словарь/УЗИ/УЗИ_ОБП"
    )


def test_path_matching_does_not_match_only_a_common_filename():
    from evaluator import _path_matches

    assert _path_matches("Словарь/УЗИ/УЗИ_ОБП.md", "Регистратура/Словарь/УЗИ/УЗИ_ОБП")
    assert not _path_matches("Словарь/УЗИ/УЗИ_ОБП.md", "Регистратура/Другое/УЗИ_ОБП")


def test_generic_word_ask_to_clarify_is_not_treated_as_abstention():
    result = evaluate_case(
        _case(knowledge_coverage="absent", expected_facts=[], expected_source_paths=[]),
        {"answer": "Уточните, пожалуйста, какой анализ вас интересует.", "sources": [], "retrieval": []},
    )
    assert result["status"] == "needs_review"
    assert result["abstained"] is False


def test_all_expected_source_paths_must_be_used_for_complex_case_to_pass():
    case = _case(
        expected_facts=["подтвержденный факт"],
        expected_fact_aliases={},
        expected_source_paths=["Словарь/УЗИ/УЗИ_ОБП.md", "Скрипты/Чат.md"],
    )
    response = {
        "answer": "Подтвержденный факт.",
        "sources": [{"source_id": "W1", "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП", "used_in_answer": True}],
        "retrieval": [
            {"path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП"},
            {"path": "Регистратура/Скрипты/Чат"},
        ],
        "source_checks_passed": True,
        "answer_review_diagnostics": {"status": "passed", "used_source_ids": ["W1"]},
    }
    result = evaluate_case(case, response)
    assert result["expected_sources_retrieved"] is True
    assert result["expected_sources_used"] is False
    assert result["status"] == "needs_review"


def test_abstention_phrase_does_not_require_exact_word_order():
    result = evaluate_case(
        _case(knowledge_coverage="absent", expected_facts=[], expected_source_paths=[]),
        {"answer": "По этому вопросу информации в базе знаний нет.", "sources": [], "retrieval": []},
    )
    assert result["abstained"] is True


def test_golden_set_v1_contract_has_49_cases_and_expected_distribution():
    import json
    from pathlib import Path

    dataset = json.loads(Path(__file__).with_name("golden_set_v1.json").read_text(encoding="utf-8"))
    cases = validate_dataset(dataset)
    assert len(cases) == 49
    assert {case["id"] for case in cases} == {f"Q{i:02d}" for i in range(1, 50)}


def test_golden_set_validator_rejects_alias_for_unknown_fact():
    dataset = {
        "golden_set_id": "test",
        "cases": [{
            "id": "QX", "question": "test", "category": "test",
            "knowledge_coverage": "full", "expected_facts": ["fact"],
            "expected_fact_aliases": {"other fact": ["alias"]},
        }],
    }
    import pytest
    with pytest.raises(ValueError, match="неизвестные факты"):
        validate_dataset(dataset)


def test_q02_stop_food_paraphrase_is_matched():
    from pathlib import Path
    import json

    dataset = json.loads(Path(__file__).with_name("golden_set_v1.json").read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["id"] == "Q02")
    result = evaluate_case(
        case,
        {
            "answer": "За 8 часов до исследования прекратить приём пищи.",
            "sources": [{"source_id": "W1", "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП", "used_in_answer": True}],
            "retrieval": [{"path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП"}],
            "source_checks_passed": True,
            "answer_review_diagnostics": {"status": "passed", "used_source_ids": ["W1"]},
        },
    )
    assert "не есть 8 часов" in result["matched_facts"]


def test_numeric_requirements_are_checked_before_regex_aliases():
    result = evaluate_case(
        _case(
            expected_facts=["услуга 14011 и 40029"],
            expected_fact_aliases={"услуга 14011 и 40029": [r"re:(?is)(?=.*14011).+"]},
        ),
        {"answer": "Для услуги 14011 предусмотрена запись.", "sources": [], "retrieval": [], "source_checks_passed": False},
    )
    assert result["fact_match_details"][0]["method"] == "numeric_requirement_missing"


def test_compound_durations_are_not_matched_by_unrelated_numbers():
    import json
    from pathlib import Path

    dataset = json.loads(Path(__file__).with_name("golden_set_v1.json").read_text(encoding="utf-8"))
    case = next(item for item in dataset["cases"] if item["id"] == "Q03")
    fact = "2 дня исследование в клинике и 8 рабочих дней в референсной лаборатории"
    answer = (
        "Общий срок задержки составляет 10 рабочих дней: 2 дня в клинике "
        "и 8 дней в референсной лаборатории."
    )
    result = evaluate_case(
        {**case, "expected_facts": [fact], "expected_fact_aliases": case["expected_fact_aliases"]},
        {"answer": answer, "sources": [], "retrieval": [], "source_checks_passed": False},
    )
    assert result["fact_coverage"] == 0.0
    assert result["fact_match_details"][0]["method"] == "numeric_context_not_verified"
