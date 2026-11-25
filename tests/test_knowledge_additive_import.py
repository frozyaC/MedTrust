from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _method(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_additive_import_upserts_only_matching_document_and_never_truncates_index():
    method = _method(ROOT / "app/db/repository.py", "add_documents")
    assert "TRUNCATE knowledge_documents" not in method
    assert "ON CONFLICT (source_key) DO UPDATE" in method
    assert "DELETE FROM knowledge_chunks WHERE document_id = %s" in method
    assert "content_hash" in method


def test_additive_import_is_exposed_as_separate_api_route():
    source = (ROOT / "app/api/routes.py").read_text(encoding="utf-8")
    assert '@router.post("/knowledge/add")' in source
    assert "KnowledgeRepository().add_documents(documents)" in source


def test_startup_seed_does_not_replace_a_populated_index_automatically():
    method = _method(ROOT / "app/db/seed.py", "seed_knowledge_index")
    assert "if document_count > 0:" in method
    assert "Use POST /api/v1/knowledge/reindex only for an intentional full replacement" in method
    # The only automatic call to destructive reindex is below the empty-index guard.
    assert method.index("if document_count > 0:") < method.index("repo.reindex(parse_zip(data))")

