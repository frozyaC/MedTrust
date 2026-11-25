"""Create/update the MedTrust Golden Set v1 retrieval dataset in LangSmith.

Run from the project root after setting LANGSMITH_API_KEY in .env.
Only synthetic Golden Set questions and expected Wiki paths are uploaded; no
patient records, conversations, or live API responses are included.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "evaluation"))
os.chdir(ROOT)

from app.core.config import get_settings  # noqa: E402
from run_evaluation import validate_dataset  # noqa: E402

DATASET_PATH = ROOT / "tests" / "evaluation" / "golden_set_v1.json"


def _get_metadata(example: Any) -> dict[str, Any]:
    metadata = getattr(example, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=None, help="Переопределить имя датасета LangSmith")
    parser.add_argument("--dry-run", action="store_true", help="Только показать объём импорта")
    args = parser.parse_args()

    dataset_json = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases = validate_dataset(dataset_json)
    dataset_name = args.name or "MedTrust Golden Set v1 — Retrieval"

    examples = [
        {
            "inputs": {"question": case["question"], "top_k": 5},
            "reference_outputs": {
                "expected_source_paths": case.get("expected_source_paths") or []
            },
            "metadata": {
                "case_id": str(case["id"]),
                "category": str(case["category"]),
                "complexity": str(case.get("complexity") or ""),
                "knowledge_coverage": str(case["knowledge_coverage"]),
                "label_type": "expected_wiki_document_paths",
            },
        }
        for case in cases
    ]
    print(f"Golden Set: {len(cases)} кейсов; LangSmith dataset: {dataset_name!r}")
    if args.dry_run:
        print("Dry run: будут переданы только вопросы Golden Set, expected_source_paths и безопасные метаданные.")
        return 0

    settings = get_settings()
    if not settings.langsmith_api_key.strip():
        print("Ошибка: LANGSMITH_API_KEY не задан в .env", file=sys.stderr)
        return 2
    dataset_name = args.name or settings.langsmith_dataset_name

    try:
        from langsmith import Client
    except ImportError:
        print("Ошибка: установите SDK командой pip install -r requirements.txt", file=sys.stderr)
        return 2

    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    client = Client()
    if not client.has_dataset(dataset_name=dataset_name):
        client.create_dataset(
            dataset_name=dataset_name,
            description=(
                "MedTrust Golden Set v1 для оценки retrieval на уровне документов Wiki. "
                "Эталоны задаются путями документов, а не отдельными chunk_id."
            ),
        )

    existing_ids = {
        str(_get_metadata(example).get("case_id"))
        for example in client.list_examples(dataset_name=dataset_name)
        if _get_metadata(example).get("case_id") is not None
    }
    pending = [
        example for example in examples
        if str(example["metadata"]["case_id"]) not in existing_ids
    ]
    if pending:
        client.create_examples(dataset_name=dataset_name, examples=pending)
    print(
        f"Готово: добавлено {len(pending)}, уже существовало {len(existing_ids)}, "
        f"итого в датасете не менее {len(existing_ids) + len(pending)} примеров."
    )
    print("Откройте LangSmith → Datasets → " + dataset_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
