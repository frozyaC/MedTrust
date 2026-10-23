from app.services.web_evidence_guard import evidence_rejection_reason, has_explicit_price


def test_general_payment_policy_does_not_support_gastroscopy_price() -> None:
    reason = evidence_rejection_reason(
        "Сколько стоит гастроскопия?",
        title="Оплата медицинских услуг",
        url="https://clinic.example/payment",
        snippet="Услуги можно оплатить по ДМС или за счёт пациента.",
    )
    assert reason == "price_procedure_mismatch"


def test_gastroscopy_price_is_eligible_when_source_names_service_and_amount() -> None:
    text = "Гастроскопия — 3 500 рублей."
    assert has_explicit_price(text)
    assert evidence_rejection_reason(
        "Сколько стоит гастроскопия?",
        title="Цены на услуги эндоскопии",
        url="https://clinic.example/prices",
        snippet=text,
    ) is None


def test_price_page_without_explicit_amount_is_not_answer_evidence() -> None:
    reason = evidence_rejection_reason(
        "Сколько стоит гастроскопия?",
        title="Цены на гастроскопию",
        url="https://clinic.example/prices",
        snippet="Уточняйте стоимость у администратора.",
    )
    assert reason == "price_requires_explicit_amount"


def test_obesity_article_does_not_support_mri_contrast_contraindications() -> None:
    reason = evidence_rejection_reason(
        "Какие противопоказания к МРТ с контрастированием необходимо проверить перед записью?",
        title="Ожирение у взрослых",
        url="https://extranet.who.int/example.pdf",
        snippet="Рекомендации по профилактике и лечению ожирения у взрослых.",
    )
    assert reason == "contraindication_procedure_mismatch"


def test_mri_contrast_safety_source_can_pass_relevance_guard() -> None:
    assert evidence_rejection_reason(
        "Какие противопоказания к МРТ с контрастированием необходимо проверить перед записью?",
        title="MRI contrast safety and contraindications",
        url="https://hospital.example/mri-contrast-safety",
        snippet=(
            "Before MRI with gadolinium contrast, review kidney function, prior allergic reactions, "
            "pregnancy and implant safety with the radiology team."
        ),
    ) is None


def test_mri_article_without_contrast_information_is_rejected_for_contrast_question() -> None:
    reason = evidence_rejection_reason(
        "Какие противопоказания к МРТ с контрастированием необходимо проверить перед записью?",
        title="MRI safety",
        url="https://hospital.example/mri-safety",
        snippet="MRI safety requires checking compatible implants and metal devices.",
    )
    assert reason == "contraindication_contrast_mismatch"


def test_explicit_free_service_is_price_evidence() -> None:
    assert has_explicit_price("Гастроскопия проводится бесплатно по направлению.")
    assert evidence_rejection_reason(
        "Сколько стоит гастроскопия?",
        title="Порядок проведения гастроскопии",
        url="https://clinic.example/gastroscopy",
        snippet="Гастроскопия проводится бесплатно по направлению.",
    ) is None


def test_price_of_another_procedure_cannot_support_gastroscopy_price() -> None:
    reason = evidence_rejection_reason(
        "Сколько стоит гастроскопия?",
        title="Услуги клиники",
        url="https://clinic.example/prices",
        snippet="Гастроскопия доступна по записи. МРТ — 4 000 рублей.",
    )
    assert reason == "price_amount_not_linked_to_service"


def test_search_query_in_url_does_not_turn_unrelated_page_into_evidence() -> None:
    reason = evidence_rejection_reason(
        "Какие противопоказания к МРТ с контрастированием?",
        title="Ожирение у взрослых",
        url="https://example.org/search?q=МРТ+с+контрастированием+противопоказания",
        snippet="Рекомендации по контролю массы тела.",
    )
    assert reason == "contraindication_procedure_mismatch"
