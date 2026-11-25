"""Regression checks for the Wiki-only /api/v1/query policy."""
from __future__ import annotations

import ast
from pathlib import Path


RAG_SOURCE = Path(__file__).resolve().parents[1] / "app" / "services" / "rag.py"


def test_rag_service_does_not_import_or_invoke_searxng() -> None:
    source = RAG_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "SearXNGWebSearchClient" not in identifiers
    assert "self.web_search.search" not in source

    answer_method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "answer"
    )
    method_source = ast.get_source_segment(source, answer_method) or ""
    assert "self.web_search.search" not in method_source
    assert "_search_web_aspect" not in method_source
    assert "SearXNG" not in method_source
    assert '"web_search_policy": "disabled_for_query_endpoint"' in method_source


def test_query_does_not_create_search_link_sources() -> None:
    source = RAG_SOURCE.read_text(encoding="utf-8")
    assert "def _unverified_search_links(" not in source
    assert "def _append_search_link_citations(" not in source


def test_knowledge_gap_registration_remains_enabled() -> None:
    source = RAG_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    answer_method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "answer"
    )
    method_source = ast.get_source_segment(source, answer_method) or ""
    assert "self.knowledge_gap_tracker.record_gap(" in method_source


def test_answer_never_invokes_web_search_when_local_wiki_has_no_match(monkeypatch):
    from types import SimpleNamespace

    from app.services.rag import RagService

    monkeypatch.setattr(
        "app.services.rag.get_settings",
        lambda: SimpleNamespace(gigachat_max_tokens=450, memory_follow_up_max_chars=300),
    )

    class FakeMemory:
        def __init__(self):
            self.messages = []

        def ensure_conversation(self, conversation_id):
            return conversation_id or "local-only-test"

        def build_context(self, conversation_id):
            return {"summary": "", "messages": []}

        def add_message(self, conversation_id, role, content, **kwargs):
            self.messages.append((role, content, kwargs))

        def all_messages_count(self, conversation_id):
            return sum(role == "user" for role, _, _ in self.messages)

        def update_title(self, conversation_id, title):
            pass

    class FakeContextualizer:
        def resolve(self, **kwargs):
            question = kwargs["current_question"]
            return SimpleNamespace(
                resolved_query=question,
                clarification_required=False,
                clarification_question=None,
                llm_attempted=False,
                intent="new_question",
                confidence=1.0,
                as_dict=lambda: {"resolved_query": question, "intent": "new_question"},
            )

    class ForbiddenWebSearch:
        def search(self, *args, **kwargs):
            raise AssertionError("/api/v1/query must never invoke external web search")

    class ForbiddenGigaChat:
        last_usage = {}

        def chat(self, prompt):
            raise AssertionError("No answer may be generated without local Wiki evidence")

    service = RagService.__new__(RagService)
    service.memory = FakeMemory()
    service.contextualizer = FakeContextualizer()
    service.knowledge_gap_tracker = SimpleNamespace(record_gap=lambda **kwargs: None)
    service.gigachat = ForbiddenGigaChat()
    # Even an accidentally attached client must not be called by answer().
    service.web_search = ForbiddenWebSearch()
    service._search_question_aspects = lambda question, patient, top_k: ([], [question])

    result = service.answer("Фибриляция", None, 5)

    assert result["search_backend"] == "local_wiki_only"
    assert result["web_search_policy"] == "disabled_for_query_endpoint"
    assert result["web_search_attempted"] is False
    assert result["web_search_used"] is False
    assert result["web_search_status"] == "disabled_for_query_endpoint"
    assert result["web_search_by_facet"] == []
    assert result["attempted_web_queries"] == []
    assert result["sources"] == []
    assert result["answer_review_diagnostics"]["source_evidence_check"]["web_results_returned"] == 0


def test_external_search_remains_only_on_the_manual_web_search_route():
    routes_source = (RAG_SOURCE.parents[1] / "api" / "routes.py").read_text(encoding="utf-8")
    tree = ast.parse(routes_source)
    route_functions = {
        node.name: (ast.get_source_segment(routes_source, node) or "")
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "manual_web_answer(" in route_functions["web_search"]
    assert "RagService().answer(" not in route_functions["web_search"]
    assert "RagService().answer(" in route_functions["query"]
    assert "manual_web_answer(" not in route_functions["query"]
