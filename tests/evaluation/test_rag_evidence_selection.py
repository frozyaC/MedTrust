from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("pgvector")
pytest.importorskip("psycopg")

import app.services.rag as rag_module
from app.services.rag import RagService
from app.services.source_relevance import classify_source_relevance


def _doc(section: str, content: str, score: float) -> dict:
    return {
        "chunk_id": section,
        "title": "Справочник УЗИ брюшной полости",
        "wiki_path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП",
        "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП",
        "section": section,
        "content": content,
        "source_url": None,
        "path_segments": ["Регистратура", "Словарь", "УЗИ", "УЗИ ОБП"],
        "rrf_score": score,
        "dense_similarity": 0.7,
        "dense_rank": 1,
        "document_id": "same-wiki-article",
    }


def test_cbc_query_rejects_biochemistry_page_cross_talk():
    assessment = classify_source_relevance(
        "состав общего анализа крови",
        title="Биохимия",
        path="Регистратура/Словарь/Лаборатория/Анализы_крови/Биохимия",
        content="Биохимический анализ крови помогает оценить функции внутренних органов.",
    )
    assert assessment.label == "irrelevant"
    assert assessment.reason == "different_laboratory_test:cbc"


def test_preparation_query_keeps_same_article_code_and_booking_siblings(monkeypatch):
    monkeypatch.setattr(rag_module, "get_settings", lambda: SimpleNamespace(rag_max_wiki_sources=3))
    question = "подготовка к ультразвуковому исследованию брюшной полости"
    docs = [
        _doc("УЗИ Органов брюшной полости > Подготовка", "За 8 часов не принимать пищу, за 4 часа не пить. За 1–2 дня снизить газообразующие продукты.", 0.050),
        _doc("УЗИ Органов брюшной полости", "|14011|УЗИ брюшной полости|\n|40029|УЗИ брюшной полости и почек|", 0.049),
        _doc("УЗИ Органов брюшной полости > Запись", "Записывать до ФГС. После ФГС УЗИ ОБП выполнять нельзя.", 0.048),
    ]
    selected = RagService._wiki_sufficient_docs(docs, question=question)
    selected_sections = {doc["section"] for doc in selected}
    assert len(selected) == 3
    assert "УЗИ Органов брюшной полости > Подготовка" in selected_sections
    assert "УЗИ Органов брюшной полости" in selected_sections
    assert "УЗИ Органов брюшной полости > Запись" in selected_sections
    assert sum(bool(doc.get("supplemental_context")) for doc in selected) == 2


def test_source_attribution_uses_full_evidence_not_short_preview():
    full_text = "служебный заголовок " * 60 + "Услуга 14011 — УЗИ брюшной полости и почек."
    sources = [{
        "source_id": "W1", "source_type": "wiki", "title": "УЗИ ОБП",
        "section": "УЗИ брюшной полости", "path": "Регистратура/Словарь/УЗИ/УЗИ_ОБП",
        "snippet": full_text[:700], "_internal_evidence_text": full_text,
        "citation": "[W1]", "matched_query_aspects": ["подготовка УЗИ"],
    }]
    answer, updated, audit = RagService._attribute_answer_to_sources(
        "- Услуга 14011 — УЗИ брюшной полости и почек.", sources
    )
    assert "[W1]" in answer
    assert audit and audit[0]["supported"] is True
    assert updated[0]["used_in_answer"] is True


def test_facet_coverage_is_explicitly_not_a_completeness_measure():
    coverage = RagService._facet_coverage(
        ["подготовка УЗИ"],
        [{
            "source_id": "W1", "source_type": "wiki", "matched_query_aspects": ["подготовка УЗИ"],
            "title": "УЗИ", "path": "Регистратура/УЗИ", "section": "Подготовка",
            "snippet": "За 8 часов не принимать пищу.",
        }],
        [{"supported": True, "source_ids": ["W1"], "claim": "За 8 часов не принимать пищу"}],
    )
    assert coverage[0]["covered"] is True
    assert coverage[0]["completeness_assessed"] is False
    assert coverage[0]["coverage_scope"] == "claim_presence_not_answer_completeness"


def test_hiv_timing_query_keeps_service_code_sibling_from_same_article(monkeypatch):
    monkeypatch.setattr(rag_module, "get_settings", lambda: SimpleNamespace(rag_max_wiki_sources=3))
    question = "срок готовности анализа на ВИЧ"
    timing = _doc(
        "Антитела к ВИЧ > Задержка результатов",
        "Результат задержан на 8 рабочих дней после готовности у нас. Общий срок 2 дня в клинике и 8 дней в референсной лаборатории.",
        0.052,
    )
    code = _doc(
        "Антитела к ВИЧ",
        "# Антитела к ВИЧ\n|18001|Антитела к ВИЧ 1/2 (anti-HIV)|",
        0.049,
    )
    selected = RagService._wiki_sufficient_docs([timing, code], question=question)
    assert len(selected) == 2
    code_doc = next(item for item in selected if "18001" in item["content"])
    assert code_doc["supplemental_context"] is True


def test_attribution_accepts_exact_analyte_name_in_table_row():
    sources = [{
        "source_id": "W1", "source_type": "wiki", "title": "Общий анализ крови",
        "section": "Состав анализа", "path": "Регистратура/Словарь/Лаборатория/ОАК",
        "snippet": "Лейкоциты (WBC) | 10^9/л | 4,5-10,2",
        "_internal_evidence_text": "Лейкоциты (WBC) | 10^9/л | 4,5-10,2",
        "citation": "[W1]", "matched_query_aspects": ["состав ОАК"],
    }]
    answer, updated, audit = RagService._attribute_answer_to_sources(
        "- Лейкоциты (количество белых клеток крови).", sources
    )
    assert "[W1]" in answer
    assert audit[0]["supported"] is True
    assert updated[0]["used_in_answer"] is True


def test_facet_coverage_distinguishes_retrieved_from_attributed_sources():
    coverage = RagService._facet_coverage(
        ["состав ОАК"],
        [{
            "source_id": "W1", "source_type": "wiki", "matched_query_aspects": ["состав ОАК"],
            "title": "ОАК", "path": "Регистратура/ОАК", "section": "Состав",
            "snippet": "Лейкоциты (WBC)",
        }],
        [],
    )[0]
    assert coverage["covered"] is False
    assert coverage["wiki_evidence_available"] is True
    assert coverage["coverage_status"] == "evidence_found_but_not_attributed"
