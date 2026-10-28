from app.services.answer_presentation import (
    ensure_bullet_format,
    renumber_ordered_lists,
    safe_no_evidence_response,
)


def test_ordered_list_items_stay_in_one_sequence_across_blank_lines() -> None:
    answer = (
        "1. Направить в травмпункт при свежей травме.\n\n"
        "1. Направить к травматологу поликлиники при наличии заключения."
    )
    result = renumber_ordered_lists(answer)
    assert result.startswith("1. Направить")
    assert "\n\n2. Направить" in result


def test_unrelated_paragraph_starts_a_new_ordered_list() -> None:
    answer = "1. Первый пункт.\n\nОбычный абзац.\n\n1. Новый список."
    result = renumber_ordered_lists(answer)
    assert "1. Первый пункт." in result
    assert "1. Новый список." in result


def test_bullet_formatter_preserves_numbering_when_source_has_blank_lines() -> None:
    answer = "1. Первое условие.\n\n1. Второе условие."
    result = ensure_bullet_format(answer)
    assert "1. Первое условие." in result
    assert "2. Второе условие." in result


def test_price_fallback_does_not_claim_verified_sources_were_checked() -> None:
    result = safe_no_evidence_response("Сколько стоит гастроскопия?")
    assert "локальной базе знаний MedTrust не удалось найти материал" in result
    assert "подтверждающий стоимость гастроскопии" in result
    assert "веб-результатов" not in result


def test_contraindication_fallback_uses_precise_neutral_wording() -> None:
    result = safe_no_evidence_response(
        "Какие противопоказания к МРТ с контрастированием нужно проверить?"
    )
    assert "не найден материал" in result
    assert "именно для МРТ с контрастированием" in result
    assert "не буду перечислять неподтверждённые ограничения" in result
