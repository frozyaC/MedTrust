import pytest

from app.schemas.api import ManualWebSearchRequest

# The archived source fixture omits provider adapters; the complete MedTrust repo includes this module.
pytest.importorskip("app.services.gigachat")
from app.services.manual_web_search import _patient_search_context, _queries


def test_manual_web_search_request_accepts_patient_context():
    request = ManualWebSearchRequest(
        question="Нужна ли МРТ с контрастом?",
        patient={
            "age": 72,
            "sex": "женский",
            "contraindications": ["хроническая болезнь почек"],
            "anamnesis": "Пациент Иван Иванов принимает постоянные препараты.",
        },
    )

    assert request.patient is not None
    assert request.patient.age == 72
    assert request.patient.sex == "женский"
    assert request.patient.contraindications == ["хроническая болезнь почек"]


def test_patient_context_contains_clinical_factors_but_redacts_direct_identifiers():
    context = _patient_search_context({
        "age": 72,
        "sex": "женский",
        "contraindications": ["хроническая болезнь почек", "аллергия на контраст"],
        "anamnesis": (
            "Пациент Иван Иванов, телефон +7 999 123-45-67, "
            "email ivan@example.com. Принимает антикоагулянты."
        ),
    })

    assert "72 лет" in context
    assert "женский" in context
    assert "хроническая болезнь почек" in context
    assert "аллергия на контраст" in context
    assert "антикоагулянты" in context
    assert "Иван Иванов" not in context
    assert "ivan@example.com" not in context
    assert "+7 999 123-45-67" not in context


def test_search_uses_patient_context_first_and_preserves_general_query_fallback():
    question = "Какие риски МРТ с контрастом?"
    patient = {
        "age": 72,
        "sex": "женский",
        "contraindications": ["хроническая болезнь почек"],
        "anamnesis": "Принимает антикоагулянты.",
    }

    queries = _queries(question, patient)

    assert "72 лет" in queries[0]
    assert "женский" in queries[0]
    assert "хроническая болезнь почек" in queries[0]
    assert "антикоагулянты" in queries[0]
    assert queries[1] == question


def test_missing_patient_context_keeps_original_query_first():
    question = "Как подготовиться к гастроскопии?"
    assert _queries(question, None)[0] == question


def test_manual_web_answer_passes_patient_context_to_search_and_model(monkeypatch):
    from types import SimpleNamespace
    import app.services.manual_web_search as module

    search_client = SimpleNamespace(
        settings=SimpleNamespace(
            web_search_enabled=True,
            web_search_timeout_seconds=3,
            web_search_fallback_timeout_seconds=1,
        ),
        _request=lambda query, timeout: [{
            "url": "https://example.org/clinical-guidance",
            "title": "MRI contrast and kidney function",
            "content": "MRI contrast guidance describes kidney function assessment and clinical precautions.",
        }],
        _parse_safe_results=lambda raw, limit=1: [],
        _enrich_results=lambda results, query="": [],
    )
    prompts = []
    class FakeGigaChat:
        def chat(self, prompt):
            prompts.append(prompt)
            return "Ответ по найденному источнику."

    monkeypatch.setattr(module, "SearXNGWebSearchClient", lambda: search_client)
    monkeypatch.setattr(module, "is_relevant_web_result", lambda query, item: True)
    monkeypatch.setattr(module, "has_answerable_web_evidence", lambda query, item: True)
    monkeypatch.setattr(module, "get_gigachat_client", lambda: FakeGigaChat())

    patient = {
        "age": 72,
        "sex": "женский",
        "contraindications": ["хроническая болезнь почек"],
        "anamnesis": "Принимает антикоагулянты.",
    }
    result = module.manual_web_answer("Какие риски МРТ с контрастом?", 1, patient)

    assert result["status"] == "success"
    assert result["diagnostics"]["patient_context_applied"] is True
    assert "72 лет" in result["diagnostics"]["attempted_queries"][0]["query"]
    assert "хроническая болезнь почек" in result["diagnostics"]["attempted_queries"][0]["query"]
    assert len(prompts) == 1
    assert "пол: женский" in prompts[0]
    assert "антикоагулянты" in prompts[0]
