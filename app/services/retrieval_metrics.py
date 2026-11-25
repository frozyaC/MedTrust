"""Deterministic document-level metrics for ranked MedTrust retrieval results."""
from __future__ import annotations

import math
import re
import unicodedata
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote


def normalize_document_path(path: str) -> str:
    """Normalize Wiki paths while preserving their document hierarchy."""
    value = unquote(str(path or "")).replace("\\", "/").strip()
    value = re.sub(r"^(?:\./|/)+", "", value)
    parts: list[str] = []
    for raw_part in PurePosixPath(value).parts:
        raw_part = re.sub(r"(?i)\.md$", "", raw_part)
        part = unicodedata.normalize("NFKC", raw_part.replace("_", " ")).casefold()
        part = part.replace("ё", "е")
        part = re.sub(r"[^0-9a-zа-я]+", " ", part).strip()
        if part and part not in {".", ".."}:
            parts.append(part)
    # Paths can be stored relative to the Wiki root or include repository prefixes.
    while parts and parts[0] in {"knowledge base", "knowledgebase", "регистратура"}:
        parts.pop(0)
    return "/".join(parts)


def _path_matches(expected_path: str, actual_path: str) -> bool:
    expected = normalize_document_path(expected_path)
    actual = normalize_document_path(actual_path)
    return bool(expected and actual and (actual == expected or actual.endswith("/" + expected)))


def retrieval_quality_metrics(
    expected_paths: list[str], retrieval: list[dict[str, Any]], k: int = 5
) -> dict[str, float | int]:
    """Calculate Precision@K, Recall@K, MRR@K and binary nDCG@K.

    The ranking unit is a unique Wiki document path, not a chunk. This prevents a
    document with many retrieved chunks from occupying multiple relevant slots.
    Precision uses a fixed denominator K, matching the project's evaluator policy.
    """
    if k < 1:
        raise ValueError("k должен быть положительным")

    expected_by_norm: dict[str, str] = {}
    for path in expected_paths:
        normalized = normalize_document_path(path)
        if normalized:
            expected_by_norm.setdefault(normalized, str(path))
    if not expected_by_norm:
        raise ValueError("expected_paths должен содержать хотя бы один путь документа")

    ranked_paths: list[str] = []
    seen: set[str] = set()
    for item in retrieval if isinstance(retrieval, list) else []:
        if not isinstance(item, dict):
            continue
        raw_path = (
            item.get("path") or item.get("wiki_path") or item.get("source_path")
            or item.get("document_path")
        )
        normalized = normalize_document_path(str(raw_path or ""))
        if normalized and normalized not in seen:
            seen.add(normalized)
            ranked_paths.append(str(raw_path))

    top_paths = ranked_paths[:k]
    relevance = [
        any(_path_matches(expected_path, actual_path)
            for expected_path in expected_by_norm.values())
        for actual_path in top_paths
    ]
    relevant_hits = sum(relevance)
    first_relevant_rank = next(
        (rank for rank, is_relevant in enumerate(relevance, start=1) if is_relevant),
        None,
    )
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, is_relevant in enumerate(relevance, start=1)
        if is_relevant
    )
    ideal_hits = min(len(expected_by_norm), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return {
        "k": int(k),
        "retrieved_unique_documents": len(ranked_paths),
        "relevant_documents_retrieved_at_k": int(relevant_hits),
        "precision_at_k": round(relevant_hits / k, 4),
        "recall_at_k": round(relevant_hits / len(expected_by_norm), 4),
        "mrr_at_k": round(1.0 / first_relevant_rank, 4) if first_relevant_rank else 0.0,
        "ndcg_at_k": round(dcg / idcg, 4) if idcg else 0.0,
    }


def ranked_unique_documents(
    retrieval: list[dict[str, Any]], expected_paths: list[str]
) -> list[dict[str, Any]]:
    """Return an ordered, de-duplicated path list with manual relevance labels."""
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in retrieval if isinstance(retrieval, list) else []:
        if not isinstance(item, dict):
            continue
        raw_path = (
            item.get("path") or item.get("wiki_path") or item.get("source_path")
            or item.get("document_path")
        )
        normalized = normalize_document_path(str(raw_path or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ranked.append({
            "rank": len(ranked) + 1,
            "path": str(raw_path),
            "relevant": any(_path_matches(path, str(raw_path)) for path in expected_paths),
        })
    return ranked
