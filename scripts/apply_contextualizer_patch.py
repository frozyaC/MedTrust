"""Apply the Query Rewriting integration to the existing MedTrust rag.py.

Run from the MedTrust repository root after extracting the patch archive.
The script intentionally edits only stable integration points so recent v30/v31
RAG/search changes remain untouched. A backup of rag.py is created once.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Не удалось безопасно применить шаг «{label}»: "
            f"найдено совпадений {count}, ожидалось 1."
        )
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(
        pattern, lambda _match: replacement, text, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise RuntimeError(
            f"Не удалось безопасно применить шаг «{label}»: "
            f"найдено совпадений {count}, ожидалось 1."
        )
    return updated


def main() -> int:
    root = Path.cwd()
    rag_path = root / "app" / "services" / "rag.py"
    contextualizer_path = root / "app" / "services" / "contextualizer.py"
    if not rag_path.is_file():
        print(
            "Ошибка: запустите скрипт из корня репозитория MedTrust "
            "(где находится app/services/rag.py).",
            file=sys.stderr,
        )
        return 2
    if not contextualizer_path.is_file():
        print(
            "Ошибка: сначала распакуйте архив в корень MedTrust, чтобы появился "
            "app/services/contextualizer.py.",
            file=sys.stderr,
        )
        return 2

    original = rag_path.read_text(encoding="utf-8")
    marker = "self.contextualizer = LLMContextualizer(self.gigachat)"
    if marker in original:
        if '"query_context": contextualization.as_dict()' in original:
            print("Интеграция Contextualizer уже установлена; файл не изменён.")
            return 0
        print(
            "Ошибка: найден частично установленный Contextualizer. "
            "Файл не изменён; проверьте rag.py вручную.",
            file=sys.stderr,
        )
        return 3

    updated = original
    try:
        import_anchor = "from app.services.embeddings import get_embedding_client\n"
        updated = replace_once(
            updated,
            import_anchor,
            "from app.services.contextualizer import LLMContextualizer\n" + import_anchor,
            "импорт LLMContextualizer",
        )
        init_anchor = "        self.memory = ConversationMemory()\n"
        updated = replace_once(
            updated,
            init_anchor,
            init_anchor + "        self.contextualizer = LLMContextualizer(self.gigachat)\n",
            "инициализация LLMContextualizer",
        )
        old_context_line = (
            "        contextualized = "
            "self._contextualize_question(question, memory_context)\n"
        )
        new_context_block = (
            "        contextualization = self.contextualizer.resolve(\n"
            "            current_question=question,\n"
            "            memory_context=memory_context,\n"
            "            conversation_id=conversation_id,\n"
            "            query_id=query_id,\n"
            "        )\n"
            "        contextualized = contextualization.resolved_query or question.strip()\n"
        )
        updated = replace_once(
            updated,
            old_context_line,
            new_context_block,
            "LLM-нормализация вопроса перед поиском",
        )

        title_block = (
            "        if self.memory.all_messages_count(conversation_id) == 1:\n"
            "            self.memory.update_title(conversation_id, question)\n"
        )
        clarification_block = title_block + '''        if contextualization.clarification_required:
            answer = contextualization.clarification_question or (
                "Уточните, пожалуйста, к какой услуге или теме относится ваш вопрос?"
            )
            self.memory.add_message(
                conversation_id, "assistant", answer, query_id=query_id, sources=[]
            )
            clarification_diagnostics = {
                "status": "clarification_required",
                "stage": "query_contextualization",
                "intent": contextualization.intent,
                "confidence": contextualization.confidence,
                "source_checks_passed": False,
                "clarification_required": True,
                "resolved_query": None,
                "initial_issues": [],
                "reviewed_issues": [],
                "repaired_issues": [],
                "final_issues": [],
                "attempts": {
                    "contextualizer": int(contextualization.llm_attempted),
                    "initial_generation": False,
                    "source_attribution": 0,
                    "facet_coverage_check": 0,
                },
            }
            return {
                "query_id": query_id,
                "conversation_id": conversation_id,
                "answer": answer,
                "answer_reviewed": False,
                "source_checks_passed": False,
                "answer_validation_mode": "query_contextualization",
                "answer_review_diagnostics": clarification_diagnostics,
                "raw_question": question,
                "resolved_query": None,
                "query_context": contextualization.as_dict(),
                "sources": [],
                "retrieval": [],
                "web_search_attempted": False,
                "web_search_used": False,
                "web_search_status": "not_needed",
                "web_search_by_facet": [],
                "web_search_queries": [],
                "retrieval_query": None,
                "retrieval_queries": [],
                "resource_usage": self._resource_usage(
                    "",
                    gigachat_calls=int(contextualization.llm_attempted),
                    embedding_calls=0,
                    provider_usage=getattr(self.gigachat, "last_usage", None),
                    embedding_usage=None,
                ),
            }
'''
        updated = replace_once(
            updated,
            title_block,
            clarification_block,
            "остановка поиска при неоднозначном вопросе",
        )

        prompt_pattern = (
            r'prompt = self\._build_prompt\(\s*'
            r'question, patient, docs, web_response\.results, memory_context, wiki_sufficient,'
        )
        updated = replace_regex_once(
            updated,
            prompt_pattern,
            'prompt = self._build_prompt(\n'
            '                question, patient, docs, web_response.results, memory_context, '
            'wiki_sufficient,',
            "передача исходного вопроса генератору ответа",
        )
        prompt_kwarg_anchor = '                web_result_aspects=web_result_aspects,\n'
        updated = replace_once(
            updated,
            prompt_kwarg_anchor,
            prompt_kwarg_anchor + '                resolved_query=contextualized,\n',
            "передача resolved_query генератору ответа",
        )
        signature_anchor = (
            '        wiki_sufficient: bool,\n'
            '        web_result_aspects: dict[str, list[str]] | None = None,\n'
            '    ) -> str:\n'
        )
        updated = replace_once(
            updated,
            signature_anchor,
            '        wiki_sufficient: bool,\n'
            '        web_result_aspects: dict[str, list[str]] | None = None,\n'
            '        resolved_query: str | None = None,\n'
            '    ) -> str:\n',
            "расширение контракта _build_prompt",
        )
        current_question_anchor = (
            '            f"Текущий вопрос:\\n{question}\\n\\n"\n'
            '            f"Контекст пациента:\\n'
        )
        updated = replace_once(
            updated,
            current_question_anchor,
            '            f"Текущий вопрос:\\n{question}\\n\\n"\n'
            '            f"Нормализованный поисковый запрос:\\n'
            '{resolved_query or question}\\n\\n"\n'
            '            f"Контекст пациента:\\n',
            "передача нормализованного запроса в контекст ответа",
        )

        updated = replace_once(
            updated,
            '            "retrieval_query": contextualized,\n',
            '            "raw_question": question,\n'
            '            "resolved_query": contextualized,\n'
            '            "query_context": contextualization.as_dict(),\n'
            '            "retrieval_query": contextualized,\n',
            "возврат resolved_query и диагностики",
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        print(
            "Файл rag.py не изменён. Архив совместим только с ожидаемой "
            "структурой текущего MedTrust.",
            file=sys.stderr,
        )
        return 4

    backup_path = rag_path.with_name("rag.py.pre_contextualizer.bak")
    if not backup_path.exists():
        backup_path.write_text(original, encoding="utf-8")
    rag_path.write_text(updated, encoding="utf-8", newline="\n")
    print("Contextualizer интегрирован. Создана резервная копия:", backup_path.name)
    print(
        "Добавлен этап LLM Query Rewriting, сохранение raw/resolved query "
        "и остановка поиска при неоднозначности."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
