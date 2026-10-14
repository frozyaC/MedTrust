from pathlib import Path

from app.services.ingestion import parse_zip
from app.services.rag import RagService
from app.services.source_relevance import answerability_score, classify_source_relevance


COMBINED_QUESTION = (
    "Есть ли парковка на Садовой 15 и к какому врачу ревматологу "
    "можно обратиться за консультацией?"
)


def _candidate(document, section_index, *, rank):
    section, content = document.sections[section_index]
    return {
        "chunk_id": f"{document.source_key}:{section_index}",
        "document_id": document.source_key,
        "title": document.title,
        "wiki_path": document.wiki_path,
        "path_segments": document.path_segments,
        "source_url": document.source_url,
        "section": section,
        "content": content,
        "rrf_score": 1.0 / (60 + rank),
        "dense_similarity": max(0.1, 0.8 - rank * 0.02),
        "dense_rank": rank,
        "lexical_rank": rank,
        "path_rank": rank,
    }


def _source_documents():
    archive = Path(__file__).resolve().parents[1] / "data" / "sample_sufler.zip"
    documents = parse_zip(archive.read_bytes())
    parking = next(doc for doc in documents if "Паркинг" in doc.filename)
    rheumatologist = next(doc for doc in documents if "Ревматолог" in doc.filename)
    return parking, rheumatologist


def test_combined_parking_and_specialist_question_is_split_into_facets():
    assert RagService._split_multi_intent_question(COMBINED_QUESTION) == [
        "Есть ли парковка на Садовой 15?",
        "К какому врачу ревматологу можно обратиться за консультацией?",
    ]


def test_specialist_appointment_section_is_ranked_as_direct_answer():
    _, rheumatologist = _source_documents()
    assignment_index = next(
        index for index, (section, content) in enumerate(rheumatologist.sections)
        if "Распределение записи" in section and "Рыбина Ольга Сергеевна" in content
    )
    doc = _candidate(rheumatologist, assignment_index, rank=5)
    question = "К какому врачу ревматологу можно обратиться за консультацией?"

    relevance = classify_source_relevance(
        question,
        title=doc["title"],
        path=doc["wiki_path"],
        section=doc["section"],
        content=doc["content"],
        source_type="wiki",
    )
    answerability, reason = answerability_score(
        question,
        title=doc["title"],
        path=doc["wiki_path"],
        section=doc["section"],
        content=doc["content"],
        source_score=relevance.score,
        content_score=0.0,
    )

    assert relevance.label == "relevant"
    assert relevance.reason == "specialty_appointment_assignment_match"
    assert answerability >= 0.9
    assert reason == "specialty_appointment_assignment"
    assert "Рыбина Ольга Сергеевна" in doc["content"]


def test_split_search_selects_patient_parking_rules_and_rheumatologist_names(monkeypatch):
    class Settings:
        rag_max_wiki_sources = 3

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    parking, rheumatologist = _source_documents()

    parking_indices = [
        index for index, (section, _) in enumerate(parking.sections)
        if "Садовая 15" in section and any(
            cue in section.lower() for cue in ("для такси", "для пациентов клиники", "для пациентов травмпункта")
        )
    ]
    rheumatologist_indices = [
        index for index, (section, content) in enumerate(rheumatologist.sections)
        if "Распределение записи" in section or "Рыбина Ольга Сергеевна" in content
    ]

    service = RagService.__new__(RagService)
    calls = []

    def fake_search(query, patient, top_k):
        calls.append(query)
        if "парков" in query.lower():
            # Return taxi ahead of patient rules to reproduce the bad single-source answer.
            ordered_indices = sorted(
                parking_indices,
                key=lambda idx: 0 if "Для такси" in parking.sections[idx][0] else 1,
            )
            return [
                _candidate(parking, index, rank=rank)
                for rank, index in enumerate(ordered_indices, start=1)
            ]
        return [
            _candidate(rheumatologist, index, rank=rank)
            for rank, index in enumerate(rheumatologist_indices, start=1)
        ]

    service.search = fake_search
    candidates, aspects = service._search_question_aspects(COMBINED_QUESTION, None, 12)
    selected = RagService._wiki_sufficient_docs(candidates, question=COMBINED_QUESTION)
    prompt = RagService._build_prompt(
        COMBINED_QUESTION, None, candidates, [], {"summary": "", "messages": []}, wiki_sufficient=True
    )

    selected_sections = "\n".join(doc["section"] for doc in selected)
    selected_contents = "\n".join(doc["content"] for doc in selected)
    assert aspects == [
        "Есть ли парковка на Садовой 15?",
        "К какому врачу ревматологу можно обратиться за консультацией?",
    ]
    assert calls == aspects
    assert "Для пациентов клиники" in selected_sections
    assert "три часа" in selected_contents.lower()
    assert "300 рублей" in selected_contents.lower()
    assert "Распределение записи" in selected_sections
    assert "Рыбина Ольга Сергеевна" in selected_contents
    assert "Для такси" not in selected_sections
    assert "Рыбина Ольга Сергеевна" in prompt
    assert "300 рублей" in prompt
    assert "Найден для аспекта" in prompt


def test_parking_query_scores_taxi_subsection_below_general_patient_rules():
    parking, _ = _source_documents()
    patient_index = next(
        index for index, (section, _) in enumerate(parking.sections)
        if "Для пациентов клиники" in section and "Садовая 15" in section
    )
    taxi_index = next(
        index for index, (section, _) in enumerate(parking.sections)
        if "Для такси" in section and "Садовая 15" in section
    )
    patient_doc = _candidate(parking, patient_index, rank=5)
    taxi_doc = _candidate(parking, taxi_index, rank=1)
    query = "Есть ли парковка на Садовой 15?"

    def score(doc):
        relevance = classify_source_relevance(
            query, title=doc["title"], path=doc["wiki_path"],
            section=doc["section"], content=doc["content"],
        )
        return answerability_score(
            query, title=doc["title"], path=doc["wiki_path"],
            section=doc["section"], content=doc["content"],
            source_score=relevance.score,
            content_score=classify_source_relevance(query, content=doc["section"] + doc["content"]).score,
        )[0]

    assert score(patient_doc) > score(taxi_doc)


def test_answer_runs_facet_search_and_reports_both_supporting_sources(monkeypatch):
    from types import SimpleNamespace

    from app.services.web_search import WebSearchResponse

    class Settings:
        rag_max_wiki_sources = 3
        rag_max_web_sources = 2
        rag_max_source_chars = 4200
        rag_max_history_messages = 4
        rag_max_history_message_chars = 600
        memory_follow_up_max_chars = 300
        web_min_wiki_dense_similarity = 0.62
        gigachat_max_tokens = 450

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    parking, rheumatologist = _source_documents()
    parking_indices = [
        index for index, (section, _) in enumerate(parking.sections)
        if "Садовая 15" in section and any(cue in section for cue in (
            "Для такси", "Для пациентов клиники", "Для пациентов травмпункта"
        ))
    ]
    assignment_index = next(
        index for index, (section, content) in enumerate(rheumatologist.sections)
        if "Распределение записи" in section and "Рыбина Ольга Сергеевна" in content
    )

    class FakeMemory:
        def __init__(self):
            self.messages = []

        def ensure_conversation(self, conversation_id):
            return conversation_id or "multi-intent-test-conversation"

        def build_context(self, conversation_id):
            return {"summary": "", "messages": []}

        def add_message(self, conversation_id, role, content, **kwargs):
            self.messages.append((role, content, kwargs))

        def all_messages_count(self, conversation_id):
            return sum(role == "user" for role, _, _ in self.messages)

        def update_title(self, conversation_id, title):
            return None

        def maybe_update_summary(self, conversation_id, gigachat):
            return None

    class FakeGigaChat:
        last_usage = {"input_tokens": 50, "output_tokens": 45, "total_tokens": 95}

        def chat(self, prompt):
            assert "Для пациентов клиники" in prompt
            assert "300 рублей" in prompt
            assert "Рыбина Ольга Сергеевна" in prompt
            assert "Зуева Наталья Викторовна" in prompt
            return (
                "- **Парковка на Садовой 15:** пациентам доступны зоны A, B и C; "
                "первые 3 часа бесплатно, затем 300 рублей за каждый полный или неполный час [W1].\n"
                "- **Консультация ревматолога:** в разделе о распределении записи указаны "
                "Рыбина Ольга Сергеевна, Зуева Наталья Викторовна, Галиева Алсу Ринатовна, "
                "Мамедова Лейла Руслановна и Тарасова Е. Г. [W2]."
            )

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.gigachat = FakeGigaChat()
    service.embeddings = SimpleNamespace(last_usage={})
    search_calls = []

    def fake_search(query, patient, top_k):
        search_calls.append(query)
        if "парков" in query.casefold():
            ordered = sorted(
                parking_indices,
                key=lambda idx: 0 if "Для такси" in parking.sections[idx][0] else 1,
            )
            return [_candidate(parking, idx, rank=rank) for rank, idx in enumerate(ordered, start=1)]
        return [_candidate(rheumatologist, assignment_index, rank=1)]

    service.search = fake_search
    service.web_search = SimpleNamespace(
        search=lambda query, limit=3: WebSearchResponse("no_relevant_results", [])
    )

    result = service.answer(COMBINED_QUESTION, None, top_k=5)

    assert len(search_calls) == 2
    assert result["retrieval_queries"] == [
        "Есть ли парковка на Садовой 15?",
        "К какому врачу ревматологу можно обратиться за консультацией?",
    ]
    assert "300 рублей" in result["answer"]
    assert "Рыбина Ольга Сергеевна" in result["answer"]
    assert result["resource_usage"]["embedding_api_calls"] == 2
    assert len([source for source in result["sources"] if source["source_type"] == "wiki"]) >= 2
