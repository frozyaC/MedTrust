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
