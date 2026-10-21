from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def test_installer_wires_contextualizer_into_rag_and_exposes_resolved_query(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "app/services").mkdir(parents=True)
    (project_root / "scripts").mkdir(parents=True)

    source_root = Path(__file__).resolve().parents[1]
    shutil.copy2(
        source_root / "app/services/contextualizer.py",
        project_root / "app/services/contextualizer.py",
    )
    script_path = source_root / "scripts/apply_contextualizer_patch.py"

    rag_source = '''from app.services.embeddings import get_embedding_client

class RagService:
    def __init__(self):
        self.memory = ConversationMemory()

    def answer(self, question, patient, top_k, conversation_id=None):
        contextualized = self._contextualize_question(question, memory_context)
        self.memory.add_message(conversation_id, "user", question, query_id=query_id)
        if self.memory.all_messages_count(conversation_id) == 1:
            self.memory.update_title(conversation_id, question)
        prompt = self._build_prompt(
            question, patient, docs, web_response.results, memory_context, wiki_sufficient,
                web_result_aspects=web_result_aspects,
        )
        return {
            "retrieval_query": contextualized,
        }

    def _build_prompt(
        self,
        question: str,
        patient,
        docs,
        web_results,
        memory_context,
        wiki_sufficient: bool,
        web_result_aspects: dict[str, list[str]] | None = None,
    ) -> str:
        return (
            f"Текущий вопрос:\\n{question}\\n\\n"
            f"Контекст пациента:\\nне передан"
        )
'''
    rag_path = project_root / "app/services/rag.py"
    rag_path.write_text(rag_source, encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    updated = rag_path.read_text(encoding="utf-8")
    assert "self.contextualizer.resolve(" in updated
    assert '"query_context": contextualization.as_dict()' in updated
    assert '"resolved_query": contextualized' in updated
    assert "resolved_query=contextualized" in updated
    assert (project_root / "app/services/rag.py.pre_contextualizer.bak").exists()
