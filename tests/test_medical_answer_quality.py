"""Regression tests for source-grounded medical answers and fallback sanitization."""

from app.services.rag import RagService


def _source(citation: str = "[W1]", text: str = "") -> tuple[list[dict], dict[str, str]]:
    sources = [
        {
            "source_id": citation.strip("[]"),
            "citation": citation,
            "source_type": "wiki",
            "title": "Инструкция по процедуре",
            "snippet": text,
            "url": "https://example.test/source",
        }
    ]
    return sources, {citation: text}


def test_unsupported_fasting_interval_is_flagged() -> None:
    question = "Какая подготовка нужна перед гастроскопией?"
    answer = "- Не принимать пищу за 8–12 часов до гастроскопии. [W1]"
    sources, evidence = _source(text="Перед гастроскопией сообщите врачу о принимаемых лекарствах.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert any("Числовые медицинские значения" in issue for issue in issues)


def test_supported_fasting_interval_is_not_flagged_as_unsupported_numeric_value() -> None:
    question = "Какая подготовка нужна перед гастроскопией?"
    answer = "- Не принимать пищу за 8–12 часов до гастроскопии. [W1]"
    sources, evidence = _source(
        text="Перед гастроскопией рекомендуется не принимать пищу за 8–12 часов до процедуры."
    )

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert not any("Числовые медицинские значения" in issue for issue in issues)


def test_contraindication_claim_requires_condition_and_risk_relation_in_source() -> None:
    question = "Какие противопоказания нужно проверить перед гастроскопией?"
    answer = "- Острые инфекции являются противопоказанием к гастроскопии. [W1]"
    sources, evidence = _source(text="В инструкции упоминаются острые инфекции у пациентов.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert any("как противопоказание или фактор риска" in issue for issue in issues)


def test_sanitizer_removes_unsourced_condition_from_contraindication_list() -> None:
    question = "Какие противопоказания нужно проверить перед гастроскопией?"
    draft = (
        "# Противопоказания\n\n"
        "- Острые инфекции являются противопоказанием. [W1]\n"
        "- Декомпенсированные сердечно-сосудистые заболевания являются противопоказанием. [W1]"
    )
    sources, evidence = _source(text="Общая подготовка к гастроскопии. Сообщите врачу о принимаемых лекарствах.")

    answer = RagService._sanitize_unverified_medical_draft(question, draft, sources, evidence)

    assert "Острые инфекции" not in answer
    assert "Декомпенсированные сердечно-сосудистые заболевания" not in answer
    assert "НЕПОДТВЕРЖДЁННЫЙ ОТВЕТ" not in answer.upper()
    assert answer.strip()


def test_sanitizer_removes_unsupported_fasting_range_and_empty_headings() -> None:
    question = "Какая подготовка нужна перед гастроскопией?"
    draft = (
        "# Подготовка\n\n"
        "1. **Диета:**\n"
        "- За 8–12 часов прекратить приём пищи и жидкости. [W1]\n"
        "1. **Медикаменты:**"
    )
    sources, evidence = _source(text="Сообщите врачу обо всех принимаемых лекарствах.")

    answer = RagService._sanitize_unverified_medical_draft(question, draft, sources, evidence)

    assert "8–12 часов" not in answer
    assert not any(line.strip().endswith(":") for line in answer.splitlines())
    assert "НЕПОДТВЕРЖДЁННЫЙ ОТВЕТ" not in answer.upper()
    assert answer.strip()


def test_price_audit_rejects_amount_not_present_in_cited_source() -> None:
    question = "Сколько стоит гастроскопия?"
    answer = "- Гастроскопия стоит 3 500 рублей. [W1]"
    sources, evidence = _source(text="Описание процедуры гастроскопии и требования к подготовке.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert any("Конкретные цены или диапазоны не подтверждены" in issue for issue in issues)


def test_empty_price_range_promise_is_flagged() -> None:
    question = "Сколько стоит гастроскопия?"
    answer = "## Пример диапазона цен в частных клиниках:"
    sources, evidence = _source(text="Инструкция по проведению гастроскопии.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert any("не содержит конкретных сумм" in issue for issue in issues)


def test_monetary_facts_extracts_prices_and_ranges() -> None:
    facts = RagService._monetary_facts("Стоимость — от 1 500 до 3 000 рублей; отдельно 500 ₽.")

    assert ("range", "1500", "3000", "RUB") in facts
    assert ("amount", "1500", "RUB") in facts
    assert ("amount", "3000", "RUB") in facts
    assert ("amount", "500", "RUB") in facts


def test_safe_price_fallback_does_not_invent_a_tariff() -> None:
    answer = RagService._safe_unverified_medical_fallback("Сколько стоит гастроскопия?")

    assert "не найден подтверждённый тариф" in answer.lower()
    assert "НЕПОДТВЕРЖДЁННЫЙ ОТВЕТ" not in answer.upper()
    assert not RagService._monetary_facts(answer)


def test_water_restriction_is_not_supported_by_source_that_allows_clear_liquids() -> None:
    claim = "Нельзя пить воду перед гастроскопией."
    evidence = "Можно пить прозрачные жидкости до процедуры."

    assert not RagService._medical_preparation_instruction_supported(claim, evidence)


def test_clear_liquid_permission_requires_source_with_same_direction() -> None:
    claim = "Можно пить прозрачные жидкости до процедуры."

    assert RagService._medical_preparation_instruction_supported(
        claim, "Clear liquids are allowed up to the stated time before the procedure."
    )
    assert not RagService._medical_preparation_instruction_supported(
        claim, "Do not drink liquids before the procedure."
    )


def test_price_sanitizer_replaces_incomplete_range_with_explicit_no_tariff_answer() -> None:
    question = "Сколько стоит гастроскопия?"
    draft = "- Стоимость зависит от факторов. [W1]\n\n## Пример диапазона цен в частных клиниках:"
    sources, evidence = _source(text="Инструкция по проведению гастроскопии.")

    answer = RagService._sanitize_unverified_medical_draft(question, draft, sources, evidence)

    assert "Пример диапазона цен" not in answer
    assert "не найден подтверждённый тариф" in answer.lower()
    assert not RagService._monetary_facts(answer)


def test_medication_change_requires_source_to_support_the_action() -> None:
    question = "Какие ограничения проверить перед гастроскопией?"
    answer = "- Перед гастроскопией отмените варфарин. [W1]"
    sources, evidence = _source(text="Перед гастроскопией сообщите врачу, что принимаете варфарин.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert any("изменить приём лекарства" in issue for issue in issues)


def test_sanitizer_preserves_cautious_advice_not_to_stop_medication() -> None:
    question = "Какая подготовка нужна перед гастроскопией?"
    draft = "- Не отменяйте назначенные препараты самостоятельно."
    sources, evidence = _source(text="Инструкция по подготовке к гастроскопии.")

    answer = RagService._sanitize_unverified_medical_draft(question, draft, sources, evidence)

    assert "Не отменяйте назначенные препараты самостоятельно" in answer


def test_confirmed_price_amount_is_accepted_when_same_cited_source_contains_it() -> None:
    question = "Сколько стоит гастроскопия?"
    answer = "- Стоимость гастроскопии — 1 500 рублей. [W1]"
    sources, evidence = _source(text="Стоимость гастроскопии — 1 500 рублей.")

    issues = RagService._answer_content_issues(question, answer, sources, evidence)

    assert not any("Конкретные цены или диапазоны не подтверждены" in issue for issue in issues)
