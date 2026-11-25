"""Calculate document-level retrieval metrics for one LangSmith trace and attach them.

This is an opt-in evaluation utility. It does not change the MedTrust RAG pipeline
and does not send query, answer, patient, or Wiki chunk text to LangSmith.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "tests" / "evaluation"
DEFAULT_LABELS = EVALUATION_DIR / "retrieval_demo_labels.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.retrieval_metrics import (  # noqa: E402
    ranked_unique_documents,
    retrieval_quality_metrics,
)


def load_labels(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Файл эталонной разметки не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Некорректный JSON в файле разметки {path}: {exc}") from exc

    expected = data.get("expected_source_paths") if isinstance(data, dict) else None
    if not isinstance(expected, list) or not expected:
        raise ValueError("В файле разметки нужен непустой expected_source_paths")
    if any(not isinstance(item, str) or not item.strip() for item in expected):
        raise ValueError("Каждый expected_source_path должен быть непустой строкой")
    return data


def extract_retrieval(run: Any) -> list[dict[str, Any]]:
    """Read privacy-safe retrieval records from the root RAG run output."""
    outputs = getattr(run, "outputs", None)
    if not isinstance(outputs, dict):
        raise ValueError("У выбранного Run нет структурированного outputs")

    records = outputs.get("retrieved_chunks")
    if records is None:
        records = outputs.get("retrieval")
    if not isinstance(records, list) or not records:
        raise ValueError(
            "В outputs выбранного Run нет retrieved_chunks/retrieval. "
            "Укажите ID корневого Run 'MedTrust RAG query', а не дочернего span."
        )

    cleaned: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        # Metric implementation expects document paths. Do not pass chunk text.
        path = (
            item.get("path") or item.get("wiki_path") or item.get("source_path")
            or item.get("document_path")
        )
        if path:
            cleaned.append({"path": str(path), "chunk_id": item.get("chunk_id")})
    if not cleaned:
        raise ValueError("В retrieval output нет ни одного чанка с путём документа")
    return cleaned


def calculate_metrics(
    expected_paths: list[str], retrieval: list[dict[str, Any]], k: int
) -> dict[str, float | int]:
    metrics = retrieval_quality_metrics(expected_paths, retrieval, k=k)
    if metrics is None:
        raise ValueError("Не удалось рассчитать retrieval metrics: отсутствует эталонная разметка")
    return metrics


def attach_feedback(
    client: Any,
    run_id: str,
    metrics: dict[str, float | int],
    labels: dict[str, Any],
) -> list[str]:
    """Attach four numeric metric scores to the LangSmith root trace."""
    k = int(metrics["k"])
    extra = {
        "evaluation_type": "manual_retrieval_reference",
        "label_set_id": labels.get("label_set_id", "medtrust-retrieval-demo-v1"),
        "case_id": labels.get("case_id", "retrieval-demo"),
        "k": k,
        "relevance_unit": "unique_wiki_document_path",
        "expected_source_paths": list(labels["expected_source_paths"]),
        "retrieved_unique_documents": int(metrics["retrieved_unique_documents"]),
        "relevant_documents_retrieved_at_k": int(metrics["relevant_documents_retrieved_at_k"]),
    }
    metric_keys = (
        "precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k",
    )
    feedback_ids: list[str] = []
    for metric_key in metric_keys:
        result = client.create_feedback(
            # For feedback on a root trace, trace_id targets the root run.
            trace_id=run_id,
            key=f"retrieval_{metric_key}",
            score=float(metrics[metric_key]),
            comment=(
                f"{metric_key}={metrics[metric_key]} at K={k}; "
                "document-level evaluation over unique Wiki paths. "
                "Reference paths were manually labelled for this demonstration case."
            ),
            extra=extra,
        )
        feedback_id = getattr(result, "id", None)
        if feedback_id is not None:
            feedback_ids.append(str(feedback_id))
    flush = getattr(client, "flush", None)
    if callable(flush):
        flush()
    return feedback_ids


def _print_results(
    run: Any,
    labels: dict[str, Any],
    metrics: dict[str, float | int],
    dry_run: bool,
) -> None:
    print(f"Run: {getattr(run, 'name', '<unknown>')} ({getattr(run, 'id', '<unknown>')})")
    print(f"Разметка: {labels.get('case_id', 'retrieval-demo')}")
    print("Эталонно релевантные документы:")
    for path in labels["expected_source_paths"]:
        print(f"  - {path}")
    print("Ранжированные уникальные документы:")
    run_outputs = getattr(run, "outputs", {}) or {}
    ranked_input = run_outputs.get("retrieved_chunks") or run_outputs.get("retrieval") or []
    for item in ranked_unique_documents(
        ranked_input, labels["expected_source_paths"]
    )[: max(5, int(metrics["k"]))]:
        marker = "RELEVANT" if item["relevant"] else "NOT RELEVANT"
        print(f"  {item['rank']}. [{marker}] {item['path']}")
    print("Метрики (уникальные пути Wiki, без повторного учёта чанков одного документа):")
    for key in ("precision_at_k", "recall_at_k", "mrr_at_k", "ndcg_at_k"):
        print(f"  {key}: {metrics[key]}")
    print(f"  K: {metrics['k']}")
    print(f"  retrieved_unique_documents: {metrics['retrieved_unique_documents']}")
    print(f"  relevant_documents_retrieved_at_k: {metrics['relevant_documents_retrieved_at_k']}")
    if dry_run:
        print("DRY RUN: оценки не отправлялись в LangSmith.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Посчитать retrieval metrics для одного LangSmith trace и прикрепить их к Run."
    )
    parser.add_argument("--run-id", required=True, help="ID корневого Run 'MedTrust RAG query' в LangSmith")
    parser.add_argument("--k", type=int, default=5, help="K для Precision/Recall/MRR/nDCG (по умолчанию: 5)")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="JSON с ручной эталонной разметкой")
    parser.add_argument("--dry-run", action="store_true", help="Только рассчитать и показать метрики, не отправлять в LangSmith")
    args = parser.parse_args()

    if args.k < 1:
        parser.error("--k должен быть >= 1")

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        from langsmith import Client
    except ImportError as exc:
        print(f"Не удалось загрузить зависимости: {exc}", file=sys.stderr)
        return 2

    try:
        labels = load_labels(args.labels)
        client = Client()
        run = client.read_run(args.run_id)
        parent_run_id = getattr(run, "parent_run_id", None)
        if parent_run_id is not None:
            raise ValueError(
                "Передан дочерний span. Нужен ID корневого Run 'MedTrust RAG query'."
            )
        retrieval = extract_retrieval(run)
        metrics = calculate_metrics(labels["expected_source_paths"], retrieval, args.k)
        _print_results(run, labels, metrics, args.dry_run)
        if not args.dry_run:
            feedback_ids = attach_feedback(client, str(args.run_id), metrics, labels)
            print(f"LangSmith feedback отправлен: {len(feedback_ids) or 4} метрики.")
            print("Откройте этот Run и проверьте раздел Feedback / Scores.")
        return 0
    except Exception as exc:
        print(f"Ошибка расчёта/публикации метрик: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
