from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

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
    assert '@admin_router.post("/knowledge/add")' in source
    assert "KnowledgeRepository().add_documents(documents)" in source


def test_startup_seed_does_not_replace_a_populated_index_automatically():
    method = _method(ROOT / "app/db/seed.py", "seed_knowledge_index")
    assert "if document_count > 0:" in method
    assert "Use POST /api/v1/knowledge/reindex only for an intentional full replacement" in method
    # The only automatic call to destructive reindex is below the empty-index guard.
    assert method.index("if document_count > 0:") < method.index("repo.reindex(parse_zip(data))")


@pytest.mark.parametrize("role,status", [(None, 401), ("registrar", 403), ("kb_owner", 200)])
def test_additive_import_requires_owner_and_accepts_zip(monkeypatch, role, status):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import admin_router
    from app.core.auth import CurrentUser, get_current_user, verify_request_origin

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[verify_request_origin] = lambda: None
    if role:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=uuid4(), login="employee", name="Сотрудник", role=role,
        )
    add_documents = Mock(return_value={"mode": "additive_upsert", "documents_added": 26})
    monkeypatch.setattr("app.api.routes.KnowledgeRepository.add_documents", add_documents)
    with TestClient(app) as client:
        response = client.post("/api/v1/knowledge/add", files={
            "file": ("knowledge.zip", (ROOT / "data/sample_sufler.zip").read_bytes(), "application/zip"),
        })
    assert response.status_code == status, response.text
    if role == "kb_owner":
        assert response.json()["mode"] == "additive_upsert"
        assert len(add_documents.call_args.args[0]) == 26
    else:
        add_documents.assert_not_called()


@pytest.mark.parametrize("count,stored_hash", [(5, None), (5, "changed"), (5, "matching"), (0, None)])
def test_seed_preserves_populated_index_and_initializes_empty_one(monkeypatch, tmp_path, count, stored_hash):
    from app.db import seed

    archive = tmp_path / "base.zip"
    archive.write_bytes(b"seed fixture")
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    repo = Mock()
    repo.document_count.return_value = count
    repo.get_index_archive_hash.return_value = archive_hash if stored_hash == "matching" else stored_hash
    repo.reindex.return_value = {"documents": 1, "chunks": 2}
    parse = Mock(return_value=["parsed document"])
    monkeypatch.setattr(seed, "get_settings", lambda: SimpleNamespace(knowledge_index_archive=str(archive)))
    monkeypatch.setattr(seed, "KnowledgeRepository", lambda: repo)
    monkeypatch.setattr(seed, "parse_zip", parse)

    seed.seed_knowledge_index()

    if count:
        parse.assert_not_called()
        repo.reindex.assert_not_called()
        repo.save_index_archive_hash.assert_not_called()
    else:
        repo.reindex.assert_called_once_with(["parsed document"])
        repo.save_index_archive_hash.assert_called_once_with(archive_hash)


def test_cardiology_runner_authenticates_and_uses_current_api_telemetry(monkeypatch, tmp_path, capsys):
    import run_cardiology_evaluation as runner

    requests = []

    class Opener:
        def open(self, request, timeout):
            requests.append((request.full_url, json.loads(request.data), request.get_header("Origin")))
            if request.full_url.endswith("/auth/login"):
                payload = {"id": "test", "login": "employee", "name": "Test", "role": "registrar"}
            else:
                assert len(requests) == 2  # Login completed before the first query.
                payload = {"answer": "Нет сведений", "sources": [], "retrieval": [],
                           "search_backend": "local_wiki_only", "web_search_attempted": False,
                           "source_checks_passed": False}
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(runner.urllib.request, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(runner, "getpass", lambda _prompt: "runner-test-password")
    monkeypatch.setattr(runner, "REPORTS", tmp_path)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "test-commit")
    monkeypatch.setattr("sys.argv", ["run_cardiology_evaluation", "--login", "employee", "--limit", "1", "--pause", "0"])

    assert runner.main() == 0
    assert requests[0][1] == {"login": "employee", "password": "runner-test-password"}
    assert requests[1][0].endswith("/api/v1/query")
    assert requests[0][2] == requests[1][2] == "http://127.0.0.1:5173"
    report = json.loads(next(tmp_path.glob("cardiology_evaluation_*.json")).read_text(encoding="utf-8"))
    assert report["summary"]["local_wiki_policy_passed"] == 1
    assert report["git_commit"] == "test-commit"
    assert "runner-test-password" not in capsys.readouterr().out
    assert all("runner-test-password" not in file.read_text(encoding="utf-8") for file in tmp_path.iterdir())
