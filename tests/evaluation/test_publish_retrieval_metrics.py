from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from publish_retrieval_metrics import (  # noqa: E402
    attach_feedback,
    calculate_metrics,
    extract_retrieval,
    load_labels,
)


def _retrieval():
    return [
        {"path": "Регистратура/Скрипты/Грубый_пациент", "chunk_id": "w1-a"},
        {"path": "Регистратура/Скрипты/Грубый_пациент", "chunk_id": "w1-b"},
        {"path": "Регистратура/Скрипты/Грубый_пациент", "chunk_id": "w1-c"},
        {"path": "Регистратура/Словарь/Травматология/Общая_информация", "chunk_id": "w2-a"},
        {"path": "Регистратура/Словарь/Травматология/Общая_информация", "chunk_id": "w2-b"},
        {"path": "Регистратура/Словарь/Травматология/Общая_информация", "chunk_id": "w2-c"},
        {"path": "Регистратура/Словарь/Травмпункт/Травмпункт", "chunk_id": "w3-a"},
        {"path": "Регистратура/Словарь/Травматология/Общая_информация", "chunk_id": "w2-d"},
        {"path": "Регистратура/Словарь/Травмпункт/Травмпункт", "chunk_id": "w3-b"},
    ]


def test_extract_retrieval_reads_root_output_without_chunk_text():
    run = SimpleNamespace(outputs={"retrieved_chunks": _retrieval()})
    rows = extract_retrieval(run)
    assert len(rows) == 9
    assert "content" not in rows[0]


def test_demo_metrics_match_expected_document_level_values():
    labels_path = ROOT / "tests" / "evaluation" / "retrieval_demo_labels.json"
    labels = load_labels(labels_path)
    metrics = calculate_metrics(labels["expected_source_paths"], _retrieval(), k=5)
    assert metrics["retrieved_unique_documents"] == 3
    assert metrics["relevant_documents_retrieved_at_k"] == 2
    assert metrics["precision_at_k"] == 0.4
    assert metrics["recall_at_k"] == 1.0
    assert metrics["mrr_at_k"] == 0.5
    assert metrics["ndcg_at_k"] == 0.6934


def test_attach_feedback_creates_four_scores_and_flushes():
    class FakeClient:
        def __init__(self):
            self.calls = []
            self.flushed = False

        def create_feedback(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(id=f"feedback-{len(self.calls)}")

        def flush(self):
            self.flushed = True

    labels = load_labels(ROOT / "tests" / "evaluation" / "retrieval_demo_labels.json")
    metrics = calculate_metrics(labels["expected_source_paths"], _retrieval(), k=5)
    client = FakeClient()
    ids = attach_feedback(client, "00000000-0000-0000-0000-000000000001", metrics, labels)
    assert len(ids) == 4
    assert {call["key"] for call in client.calls} == {
        "retrieval_precision_at_k",
        "retrieval_recall_at_k",
        "retrieval_mrr_at_k",
        "retrieval_ndcg_at_k",
    }
    assert all(call["trace_id"] == "00000000-0000-0000-0000-000000000001" for call in client.calls)
    assert client.flushed is True
