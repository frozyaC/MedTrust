from app.services.rag import RagService
from app.services.safety import is_safe_domain


def test_external_domain_policy_remains_separate_from_query_scope():
    assert is_safe_domain("https://www.nice.org.uk/guidance/cg150", {"nice.org.uk"})
    assert not is_safe_domain("http://www.nice.org.uk/guidance/cg150", {"nice.org.uk"})


def test_low_score_wiki_candidates_are_not_discarded(monkeypatch):
    class Settings:
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())
    doc = {
        "title": "Подготовка к гастроскопии",
        "wiki_path": "Регистратура/Словарь/Эндоскопия",
        "section": "Подготовка",
        "path_segments": ["Регистратура", "Словарь", "Эндоскопия"],
        "source_url": None,
        "content": "Не есть перед исследованием согласно инструкции клиники.",
        "dense_similarity": 0.21,
        "rrf_score": 0.014,
        "lexical_rank": None,
        "path_rank": None,
    }

    selected = RagService._wiki_sufficient_docs([doc])

    assert selected == [doc]


def test_gastroscopy_query_reaches_wiki_retrieval_and_answer_generation(monkeypatch):
    from types import SimpleNamespace

    from app.services.web_search import WebSearchResponse

    class Settings:
        web_min_wiki_dense_similarity = 0.62
        memory_follow_up_max_chars = 300
        rag_max_history_messages = 4
        rag_max_history_message_chars = 600
        gigachat_max_tokens = 450

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    class FakeMemory:
        def __init__(self):
            self.messages = []

        def ensure_conversation(self, conversation_id):
            return conversation_id or "conversation-test"

        def build_context(self, conversation_id):
            return {"summary": "", "messages": []}

        def add_message(self, conversation_id, role, content, **kwargs):
            self.messages.append((role, content, kwargs))

        def all_messages_count(self, conversation_id):
            return sum(role == "user" for role, _, _ in self.messages)

        def update_title(self, conversation_id, title):
            pass

    class FakeGigaChat:
        last_usage = {}

        def __init__(self):
            self.prompts = []

        def chat(self, prompt):
            self.prompts.append(prompt)
            return (
                "Подготовка к гастроскопии зависит от клинической инструкции и вида седации. "
                "Проверьте указания эндоскопического кабинета и уточните у него правила приёма "
                "пищи, жидкости и лекарств. В найденном фрагменте базы есть только общая "
                "информация, а подробной памятки не найдено."
            )

    doc = {
        "chunk_id": "gastroscopy-chunk",
        "title": "Подготовка к гастроскопии",
        "wiki_path": "Регистратура/Словарь/Эндоскопия",
        "section": "Подготовка",
        "path_segments": ["Регистратура", "Словарь", "Эндоскопия"],
        "source_url": None,
        "content": "Общие сведения о подготовке к гастроскопии.",
        "rrf_score": 0.014,
        "dense_similarity": 0.21,
        "dense_rank": 8,
        "lexical_rank": None,
        "path_rank": None,
    }
    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.gigachat = FakeGigaChat()
    search_calls = []

    def fake_search(question, patient, top_k):
        search_calls.append((question, patient, top_k))
        return [doc]

    service.search = fake_search
    service.web_search = SimpleNamespace(
        search=lambda *args, **kwargs: WebSearchResponse("empty", [])
    )

    result = service.answer("Как подготовиться к гастроскопии", None, 5)

    assert search_calls == [("Как подготовиться к гастроскопии", None, 5)]
    assert result["answer"].startswith("Подготовка к гастроскопии")
    assert result["retrieval"][0]["title"] == "Подготовка к гастроскопии"
    assert result["sources"][0]["title"] == "Подготовка к гастроскопии"
    assert result["sources"][0]["used_in_answer"] is False
    assert "Общие сведения о подготовке к гастроскопии" in service.gigachat.prompts[0]
    assert result["resource_usage"]["gigachat_calls"] == 1
