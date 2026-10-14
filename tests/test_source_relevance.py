from app.services.gigachat import SYSTEM_PROMPT
from app.services.rag import RagService
from app.services.source_relevance import classify_source_relevance, is_weather_query


def test_system_prompt_requests_brief_bullet_structured_answers():
    assert "маркированными пунктами" in SYSTEM_PROMPT
    assert "одна основная мысль на пункт" in SYSTEM_PROMPT
    assert "нумерованный список" in SYSTEM_PROMPT


def test_weather_query_matches_source_for_yekaterinburg_and_rejects_other_city():
    query = "Погода Екатеринбург"
    matching = classify_source_relevance(
        query,
        title="Weather forecast for Yekaterinburg today",
        url="https://gismeteo.ru/weather-yekaterinburg",
        content="Forecast for Yekaterinburg: temperature 12°C, wind 3 m/s.",
        source_type="web",
    )
    other_city = classify_source_relevance(
        query,
        title="Weather forecast for Moscow today",
        url="https://weather.com/weather/today/l/Moscow",
        content="Forecast for Moscow: temperature 12°C, wind 3 m/s.",
        source_type="web",
    )

    assert is_weather_query(query)
    assert matching.label == "relevant"
    assert matching.score >= 0.8
    assert other_city.label == "irrelevant"
    assert other_city.reason == "weather_location_mismatch"


def test_clinical_body_temperature_is_not_classified_as_weather():
    assert not is_weather_query("Какая температура тела у пациента при простуде?")


def test_multi_document_wiki_selection_keeps_relevant_articles_and_drops_off_topic_hit(monkeypatch):
    class Settings:
        rag_max_wiki_sources = 3

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    question = "допуск на территорию и общая информация"
    docs = [
        {
            "chunk_id": "wrong-high-score", "document_id": "wrong-document",
            "title": "Питание при госпитализации", "wiki_path": "Регистратура/Словарь/Питание",
            "section": "Питание", "source_url": None,
            "content": "Общие правила питания и госпитализации пациента.",
            "rrf_score": 0.04, "dense_similarity": 0.94, "dense_rank": 1,
        },
        {
            "chunk_id": "parking-access", "document_id": "parking-document",
            "title": "Паркинг, допуск на территорию, парковка",
            "wiki_path": "Регистратура/Словарь/Не_медицинские_услуги/Допуск_на_территорию",
            "section": "Садовая 15", "source_url": "https://wiki.example.com/parking",
            "content": "На Садовой 15 пациентам доступна парковка. Условия допуска зависят от филиала.",
            "rrf_score": 0.012, "dense_similarity": 0.24, "dense_rank": 9,
            "lexical_rank": 1, "path_rank": 1,
        },
        {
            "chunk_id": "general-info", "document_id": "general-document",
            "title": "Общая информация по парковке",
            "wiki_path": "Регистратура/Словарь/Общая_информация",
            "section": "Парковка", "source_url": "https://wiki.example.com/general",
            "content": "Общая информация: на Садовой 15 действуют отдельные правила парковки для пациентов.",
            "rrf_score": 0.010, "dense_similarity": 0.19, "dense_rank": 11,
            "lexical_rank": 2, "path_rank": 3,
        },
        {
            "chunk_id": "parking-second-chunk", "document_id": "parking-document",
            "title": "Паркинг, допуск на территорию, парковка",
            "wiki_path": "Регистратура/Словарь/Не_медицинские_услуги/Допуск_на_территорию",
            "section": "Потерянный талон", "source_url": "https://wiki.example.com/parking",
            "content": "При потере талона обратитесь к автоматической кассе.",
            "rrf_score": 0.011, "dense_similarity": 0.29, "dense_rank": 8,
            "lexical_rank": 4, "path_rank": 1,
        },
    ]

    selected = RagService._wiki_sufficient_docs(docs, question=question)
    titles = {doc["title"] for doc in selected}
    document_ids = {doc["document_id"] for doc in selected}

    assert "Паркинг, допуск на территорию, парковка" in titles
    assert "Общая информация по парковке" in titles
    assert "wrong-document" not in document_ids
    assert len(document_ids) >= 2

    prompt = RagService._build_prompt(
        question, None, docs, [], {"summary": "", "messages": []}, wiki_sufficient=False
    )
    assert "Паркинг, допуск на территорию, парковка" in prompt
    assert "Общая информация по парковке" in prompt
    assert "На Садовой 15 пациентам доступна парковка" in prompt
    assert "отдельные правила парковки для пациентов" in prompt

    retrieval = RagService._retrieval_view(docs, question=question)
    assert all("source_relevance" in row for row in retrieval)
    assert any(row["source_relevance"]["label"] == "irrelevant" for row in retrieval)


def test_weather_query_always_uses_live_search_instead_of_wiki(monkeypatch):
    doc = {
        "title": "Погода Екатеринбурга", "wiki_path": "Справочник/Погода",
        "section": "Прогноз", "content": "Прогноз погоды: температура 12°C.",
        "dense_similarity": 0.99, "rrf_score": 0.99,
        "lexical_rank": 1, "path_rank": 1,
    }
    assert is_weather_query("Погода Екатеринбург")
    assert not RagService._wiki_is_sufficient([doc], "Погода Екатеринбург")


def test_weather_question_searches_web_and_returns_source_relevance(monkeypatch):
    from types import SimpleNamespace

    from app.services.web_search import WebSearchResponse, WebSearchResult

    class Settings:
        rag_max_wiki_sources = 3
        rag_max_web_sources = 2
        rag_max_source_chars = 4200
        gigachat_max_tokens = 450

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    class FakeMemory:
        def __init__(self):
            self.messages = []

        def ensure_conversation(self, conversation_id):
            return conversation_id or "conversation-weather-test"

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
        last_usage = {}

        def chat(self, prompt):
            assert "Forecast for Yekaterinburg" in prompt
            assert "маркированными пунктами" in prompt
            return "- **Погода в Екатеринбурге:** 12 °C, ясно, ветер 3 м/с [WEB1]."

    web_result = WebSearchResult(
        title="Weather forecast for Yekaterinburg today",
        url="https://gismeteo.ru/weather-yekaterinburg",
        snippet=(
            "Forecast for Yekaterinburg today: temperature 12°C, wind speed 3 m/s. "
            "Conditions clear; expected precipitation 0 mm."
        ),
        rank=1,
        domain="gismeteo.ru",
    )
    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.gigachat = FakeGigaChat()
    service.search = lambda question, patient, top_k: [{
        "chunk_id": "unrelated-wiki", "document_id": "unrelated-document",
        "title": "Памятка по питанию", "wiki_path": "Регистратура/Питание",
        "section": "Питание", "path_segments": ["Регистратура", "Питание"],
        "source_url": None, "content": "Рекомендации по питанию пациентов.",
        "rrf_score": 0.99, "dense_similarity": 0.99, "dense_rank": 1,
        "lexical_rank": 1, "path_rank": 1,
    }]
    web_calls = []

    def fake_web_search(query, limit=3):
        web_calls.append((query, limit))
        return WebSearchResponse("success", [web_result])

    service.web_search = SimpleNamespace(search=fake_web_search)
    result = service.answer("Погода Екатеринбург", None, 5)

    assert web_calls == [("Погода Екатеринбург", 3)]
    assert result["web_search_attempted"] is True
    assert result["web_search_used"] is True
    assert result["sources"][0]["source_type"] == "web"
    assert result["sources"][0]["relevance"]["label"] == "relevant"
    assert result["sources"][0]["used_in_answer"] is True
    assert "12 °C" in result["answer"]


def test_real_parking_article_selects_sadovaya_patient_rules_not_taxi_or_lost_ticket(monkeypatch):
    from pathlib import Path

    from app.services.ingestion import parse_zip

    class Settings:
        rag_max_wiki_sources = 3

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    archive_path = Path(__file__).resolve().parents[1] / "data" / "sample_sufler.zip"
    documents = parse_zip(archive_path.read_bytes())
    parking = next(document for document in documents if "Паркинг" in document.filename)

    # Use the project's actual Wiki export, but deterministic retrieval ranks so the
    # test checks passage selection rather than depending on a live embedding service.
    candidates = []
    for index, (section, content) in enumerate(parking.sections):
        candidates.append({
            "chunk_id": str(index),
            "document_id": parking.source_key,
            "title": parking.title,
            "wiki_path": parking.wiki_path,
            "section": section,
            "source_url": parking.source_url,
            "content": content,
            "rrf_score": 1 / (index + 1),
            "dense_similarity": max(0.1, 0.8 - index * 0.02),
            "dense_rank": index + 1,
            "lexical_rank": index + 1,
            "path_rank": 1,
        })

    question = "Какие правила допуска на территорию и парковки для пациентов на Садовой 15?"
    selected = RagService._wiki_sufficient_docs(candidates, question=question)
    sections = [str(doc["section"]) for doc in selected]
    contents = "\n".join(str(doc["content"]) for doc in selected).lower()

    assert any("Садовая 15" in section and "Для пациентов клиники" in section for section in sections)
    assert "три часа" in contents
    assert "300 рублей" in contents
    assert "утерянного талона" not in contents
    assert "для такси" not in contents
    assert not any("Строителей 64Б" in section for section in sections)


def test_source_relevance_understands_paraphrased_parking_and_access_terms():
    assessment = classify_source_relevance(
        "Где оставить машину у филиала?",
        title="Допуск на территорию",
        path="Регистратура/Словарь/Не медицинские услуги/Допуск на территорию",
        section="Садовая 15",
        content="Для пациентов предусмотрена парковка; первые три часа бесплатно, далее оплата.",
        source_type="wiki",
    )
    assert assessment.label == "relevant"
    assert assessment.reason == "domain_concept_match"


def test_source_relevance_expanded_clinical_vocabulary_matches_medication_questions():
    assessment = classify_source_relevance(
        "Какие побочные эффекты и противопоказания у препарата?",
        title="Лекарственная терапия",
        section="Противопоказания и нежелательные реакции",
        content="Возможны побочные эффекты. Учитывайте противопоказания и дозировку препарата.",
        source_type="wiki",
    )
    assert assessment.label == "relevant"
    assert assessment.reason == "domain_concept_match"
