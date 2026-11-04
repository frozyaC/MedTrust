"""Deterministic, explainable scoring for MedTrust Golden Set v1.

The evaluator deliberately does not use an LLM. It separates answer-fact coverage,
retrieval, source selection/attribution and API-side validation so a single score
cannot hide where a failure occurred. Case-specific aliases/patterns live in the
Golden Set JSON, not in this module.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote

ABSTENTION_PATTERNS = (
    r"\bне\s+(?:найден\w*|удалось\s+найти|указан\w*|описан\w*|"
    r"подтвержден\w*|определен\w*|установлен\w*|перечислен\w*|содерж\w*)\b",
    r"\bнет\s+(?:данн\w*|сведен\w*|информац\w*)\b",
    r"\b(?:данн\w*|сведен\w*|информац\w*)\s+нет\b",
    r"\bинформац\w*(?:\s+в\s+базе\s+знаний)?\s+нет\b",
    r"\bнедостаточн\w*\s+(?:данн\w*|информац\w*|сведен\w*)\b",
    r"\bотсутств\w*\s+(?:информац\w*|сведен\w*|данн\w*)\b",
    r"\bне\s+располагаю\s+(?:информац\w*|сведен\w*)\b",
    r"\bне\s+могу\s+подтвердить\b",
)


def _has_abstention(text: str) -> bool:
    normalized = normalize(text)
    return any(re.search(pattern, normalized) for pattern in ABSTENTION_PATTERNS)

STOP_WORDS = {
    "и", "или", "а", "но", "в", "во", "на", "по", "из", "за", "до", "от",
    "к", "ко", "с", "со", "у", "о", "об", "для", "при", "после", "перед",
    "это", "этот", "эта", "эти", "как", "что", "который", "которая", "которые",
    "быть", "есть", "являться", "можно", "нужно", "необходимо", "следует",
    "пациент", "пациента", "пациенту", "пациенты", "пациентов",
}

# Small, domain-specific equivalence map. Numeric identifiers/durations are never
# relaxed by this map; they must still be present in the answer or explicit matcher.
TOKEN_ALIASES = {
    "воздерживаться": "непринимать",
    "воздержаться": "непринимать",
    "прием": "принимать",
    "пища": "еда",
    "пищи": "еда",
    "жидкости": "жидкость",
    "государственный": "референсный",
    "государственная": "референсный",
    "государственной": "референсный",
    "единый": "референсный",
    "единая": "референсный",
    "единую": "референсный",
}


def normalize(text: str) -> str:
    """Normalize prose for literal comparisons (not used to erase numeric values)."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold().replace("ё", "е")
    value = value.replace("–", "-").replace("—", "-")
    return re.sub(r"[^0-9a-zа-я]+", " ", value).strip()


def normalize_path(path: str) -> str:
    """Normalize Wiki paths while preserving the actual article hierarchy."""
    value = unquote(str(path or "")).replace("\\", "/").strip()
    value = re.sub(r"^(?:\./|/)+", "", value)
    parts: list[str] = []
    for raw_part in PurePosixPath(value).parts:
        raw_part = re.sub(r"(?i)\.md$", "", raw_part)
        part = normalize(raw_part.replace("_", " "))
        if not part or part in {".", ".."}:
            continue
        parts.append(part)
    # Expected paths may be relative to knowledge-base/Регистратура, while an
    # indexed path can include either or both repository/knowledge-base prefixes.
    root_prefixes = {"knowledge base", "knowledgebase", "регистратура"}
    while parts and parts[0] in root_prefixes:
        parts.pop(0)
    return "/".join(parts)


def _path_matches(expected: str, actual: str) -> bool:
    exp = normalize_path(expected)
    act = normalize_path(actual)
    if not exp or not act:
        return False
    # API paths may have a repository prefix; compare complete path suffixes, not
    # arbitrary substring fragments (to avoid matching similarly named documents).
    return act == exp or act.endswith("/" + exp)


def _tokens(text: str) -> set[str]:
    words = normalize(text).split()
    result: set[str] = set()
    for word in words:
        if word in STOP_WORDS or (len(word) < 2 and not word.isdigit()):
            continue
        if word in TOKEN_ALIASES:
            word = TOKEN_ALIASES[word]
        # Conservative Russian suffix normalization; retain short technical/code tokens.
        if re.fullmatch(r"[а-я]+", word) and len(word) > 5:
            for suffix in (
                "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими",
                "иях", "ать", "ять", "ить", "еть", "ать", "ение", "ения", "ению",
                "иями", "ами", "ями", "ах", "ях", "ией", "иям", "ые", "ое", "ая",
                "яя", "ой", "ий", "ый", "ую", "юю", "ов", "ев", "ей", "ам", "ям",
                "ом", "ем", "а", "я", "ы", "и", "у", "ю", "е", "о", "ь",
            ):
                if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                    word = word[:-len(suffix)]
                    break
        result.add(word)
    return result


def _numbers(text: str) -> set[str]:
    value = normalize(text)
    return set(re.findall(r"\d+(?:[.,]\d+)?", value))


def _explicit_alias_match(answer: str, aliases: list[str]) -> tuple[bool, str | None]:
    for alias in aliases:
        if not isinstance(alias, str) or not alias.strip():
            continue
        if alias.startswith("re:"):
            try:
                if re.search(alias[3:], answer, re.IGNORECASE | re.DOTALL):
                    return True, alias
            except re.error:
                continue
        elif normalize(alias) in normalize(answer):
            return True, alias
    return False, None


def _fact_match(
    fact: str,
    answer: str,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    if normalize(fact) and normalize(fact) in normalize(answer):
        return {"matched": True, "method": "normalized_exact", "matched_alias": fact}

    # Never award a fact when any explicit number/code in the expected fact is absent,
    # including when a case-specific regex alias happens to match other wording.
    expected_numbers = _numbers(fact)
    answer_numbers = _numbers(answer)
    missing_numbers = sorted(expected_numbers - answer_numbers)
    if missing_numbers:
        return {
            "matched": False, "method": "numeric_requirement_missing",
            "missing_numbers": missing_numbers,
        }

    alias_match, alias = _explicit_alias_match(answer, aliases or [])
    if alias_match:
        return {"matched": True, "method": "case_alias", "matched_alias": alias}

    # Relational facts (the point from which a duration is counted, precedence,
    # ownership or conditional rules) must match an explicit matcher. Bag-of-words
    # overlap is not enough to prove the relationship.
    relational_fact = bool(re.search(
        r"отсчитыва\w*|после\s+готовност|до\s+фгс|перед\s+фгс|"
        r"только\s+если|при\s+наличии|в\s+случае|не\s+от\s+момента|"
        r"исключительно|только\s+в|только\s+для",
        normalize(fact),
    ))
    if relational_fact:
        return {"matched": False, "method": "explicit_relation_matcher_required"}

    # For facts that combine multiple durations, matching every number and every
    # keyword somewhere in the answer is not enough: it can accidentally pair
    # "8" from one clause with "working days" from another (e.g. total 10 working
    # days, including 8 calendar days in the reference lab). Such facts require a
    # case-specific regex/alias that verifies the number-to-unit relationship.
    has_multiple_durations = len(expected_numbers) > 1 and bool(re.search(
        r"дн\w*|час\w*|недел\w*|месяц\w*|минут\w*|лет|года?",
        normalize(fact),
    ))
    if has_multiple_durations:
        return {"matched": False, "method": "numeric_context_not_verified"}

    expected_tokens = _tokens(fact)
    answer_tokens = _tokens(answer)
    if not expected_tokens:
        return {"matched": False, "method": "no_comparable_terms"}

    overlap = expected_tokens & answer_tokens
    ratio = len(overlap) / len(expected_tokens)
    # This is a fallback only. We keep the threshold high and mark the method so a
    # human can inspect borderline matches; structured aliases are preferred.
    if len(expected_tokens) >= 3 and ratio >= 0.88:
        return {
            "matched": True, "method": "conservative_token_equivalence",
            "token_coverage": round(ratio, 3),
        }
    return {
        "matched": False, "method": "insufficient_token_overlap",
        "token_coverage": round(ratio, 3),
        "missing_terms": sorted(expected_tokens - answer_tokens),
    }


def _collect_source_paths(items: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(items, list):
        return paths
    for item in items:
        if not isinstance(item, dict):
            continue
        path = item.get("path") or item.get("source_path") or item.get("document_path")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        path = path or metadata.get("path") or metadata.get("source_path")
        if not path and isinstance(item.get("path_segments"), list):
            path = "/".join(str(part) for part in item["path_segments"])
        if path:
            paths.append(str(path))
    return paths


def _used_source_ids(response: dict[str, Any], diagnostics: dict[str, Any], sources: list[Any]) -> set[str]:
    ids = diagnostics.get("used_source_ids") or response.get("used_source_ids") or []
    used = {str(value) for value in ids if value is not None}
    for source in sources:
        if isinstance(source, dict) and source.get("used_in_answer"):
            if source.get("source_id") is not None:
                used.add(str(source["source_id"]))
    return used


def _gap_disclosed(answer: str, missing_facts: str) -> bool:
    """Require explicit disclosure for the information gap described by this case."""
    if not str(missing_facts or "").strip():
        return True
    sentences = [
        normalize(part) for part in re.split(r"[.!?;\n]+", answer or "")
        if normalize(part)
    ]
    gap = normalize(missing_facts)

    # A conflict statement itself is an explicit disclosure. Keep it sentence-local,
    # and also check any other independently named gaps in the same case.
    conflict_required = bool(re.search(r"противореч|расхожд", gap))
    conflict_disclosed = any(
        re.search(r"противореч|расхожд|различающ|неоднозначн", sentence)
        for sentence in sentences
    )
    disclosure_pattern = (
        r"не\s+(?:найден\w*|удалось\s+найти|указан\w*|описан\w*|"
        r"подтвержден\w*|определен\w*|установлен\w*|перечислен\w*|содерж\w*)|"
        r"нет\s+(?:данн\w*|сведен\w*|информац\w*)|"
        r"(?:данн\w*|сведен\w*|информац\w*)\s+нет|"
        r"информац\w*(?:\s+в\s+базе\s+знаний)?\s+нет|"
        r"недостаточн\w*\s+(?:данн\w*|информац\w*|сведен\w*)|"
        r"отсутств\w*|не\s+располагаю|не\s+могу\s+подтвердить"
    )
    disclosure_sentences = [
        sentence for sentence in sentences
        if re.search(disclosure_pattern, sentence) or re.search(
            r"противореч|расхожд|различающ|неоднозначн", sentence
        )
    ]
    if conflict_required and not conflict_disclosed:
        return False

    topic_groups: tuple[tuple[str, str], ...] = (
        (r"стоимост|цен|тариф|оплат|доплат", r"стоимост|цен|тариф|оплат|доплат"),
        (r"срок|длительност|готовност", r"срок|длительност|готов|ожидан"),
        (r"возраст|лет|ребен|ребенк|дет", r"возраст|лет|ребен|ребенк|дет"),
        (r"документ|соглас|паспорт|снилс", r"документ|соглас|паспорт|снилс"),
        (r"забор|пробир|одновременно|вместе", r"забор|пробир|одновременно|вместе"),
        (r"врач|специалист|медик", r"врач|специалист|медик"),
        (r"запис|слот|подтверж|отмен", r"запис|слот|подтверж|отмен|порядок"),
        (r"подготов|диет|огранич", r"подготов|диет|огранич"),
        (r"расписан|график|время", r"расписан|график|время"),
        (r"страхов|полис|дмс|покрыт", r"страхов|полис|дмс|покрыт"),
        (r"парков|паркинг|талон|мест|инвалид", r"парков|паркинг|талон|мест|инвалид"),
        (r"электрон|почт|отправк", r"электрон|почт|отправк"),
        (r"точк|вход|травмпункт|инфекцион", r"точк|вход|травмпункт|инфекцион"),
        (r"состав|перечень|полный\s+список", r"состав|перечень|список"),
        (r"выдач|медкниж", r"выдач|медкниж"),
        (r"назначен|лечен|терап", r"назначен|лечен|терап"),
    )
    required_groups = [
        disclosure_pattern for gap_pattern, disclosure_pattern in topic_groups
        if re.search(gap_pattern, gap)
    ]
    if not required_groups:
        gap_terms = {term for term in _tokens(missing_facts) if len(term) >= 4 and not term.isdigit()}
        return bool(gap_terms) and any(
            re.search(disclosure_pattern, sentence) and bool(gap_terms & _tokens(sentence))
            for sentence in sentences
        )
    return all(
        any(re.search(pattern, sentence) for sentence in disclosure_sentences)
        for pattern in required_groups
    )


def evaluate_case(
    case: dict[str, Any],
    response: dict[str, Any] | None,
    error: str | None = None,
) -> dict[str, Any]:
    base = {
        "id": case["id"], "question": case["question"], "category": case["category"],
        "knowledge_coverage": case["knowledge_coverage"],
    }
    if error or not isinstance(response, dict):
        return {
            **base, "status": "request_error", "error": error or "Некорректный ответ API",
            "score": 0, "max_score": 5,
        }

    answer = str(response.get("answer") or "")
    facts = case.get("expected_facts") or []
    aliases_by_fact = case.get("expected_fact_aliases") or {}
    fact_details: list[dict[str, Any]] = []
    matched: list[str] = []
    missing: list[str] = []
    for fact in facts:
        fact = str(fact)
        match = _fact_match(fact, answer, aliases_by_fact.get(fact, []))
        fact_details.append({"fact": fact, **match})
        (matched if match["matched"] else missing).append(fact)
    fact_coverage = len(matched) / len(facts) if facts else None

    diagnostics = response.get("answer_review_diagnostics") or {}
    sources = response.get("sources") if isinstance(response.get("sources"), list) else []
    retrieval = response.get("retrieval") if isinstance(response.get("retrieval"), list) else []
    returned_paths = _collect_source_paths(sources)
    retrieval_paths = _collect_source_paths(retrieval)
    expected_paths = case.get("expected_source_paths") or []
    matched_in_sources = [expected for expected in expected_paths if any(_path_matches(expected, p) for p in returned_paths)]
    matched_in_retrieval = [expected for expected in expected_paths if any(_path_matches(expected, p) for p in retrieval_paths)]
    used_ids = _used_source_ids(response, diagnostics, sources)
    used_paths = [
        str(source.get("path") or source.get("source_path") or "")
        for source in sources if isinstance(source, dict)
        and str(source.get("source_id")) in used_ids
    ]
    matched_used_paths = [expected for expected in expected_paths if any(_path_matches(expected, p) for p in used_paths)]

    has_source_candidates = bool(sources or retrieval)
    has_used_sources = bool(used_ids)
    expected_source_retrieved = (not expected_paths) or all(
        any(_path_matches(expected, path) for path in retrieval_paths + returned_paths)
        for expected in expected_paths
    )
    expected_source_selected = (not expected_paths) or all(
        any(_path_matches(expected, path) for path in returned_paths)
        for expected in expected_paths
    )
    expected_source_used = (not expected_paths) or all(
        any(_path_matches(expected, path) for path in used_paths)
        for expected in expected_paths
    )
    source_checks_passed = response.get("source_checks_passed") is True
    validation_status = diagnostics.get("status") or response.get("answer_validation_mode")

    if case["knowledge_coverage"] == "absent":
        abstained = _has_abstention(answer)
        # Unrelated candidates in retrieval are not a failure. What matters is that
        # the assistant did not use unsupported Wiki text as evidence in the answer.
        score = (2 if abstained else 0) + (1 if not has_used_sources else 0)
        status = "passed" if abstained and not has_used_sources else "needs_review"
        return {
            **base, "status": status, "score": score, "max_score": 3,
            "abstained": abstained, "has_source_candidates": has_source_candidates,
            "has_used_sources": has_used_sources, "used_source_ids": sorted(used_ids),
            "validation_status": validation_status, "answer": answer,
        }

    # Scoring model for answerable / partially answerable cases:
    # 3 points = expected fact coverage; 1 = expected document actually used;
    # 1 = API evidence validation passed (and, for partial cases, gap disclosed).
    # Retrieval-only presence is reported independently and cannot earn attribution.
    coverage_points = int(round(3 * (fact_coverage or 0.0))) if fact_coverage is not None else 0
    source_points = int(expected_source_used)
    missing_facts_expected = str(case.get("missing_facts") or "")
    missing_disclosed = _gap_disclosed(answer, missing_facts_expected)
    partial_gap_ok = case["knowledge_coverage"] != "partial" or missing_disclosed
    validation_points = int(source_checks_passed and partial_gap_ok)
    score = coverage_points + source_points + validation_points

    complete_enough = fact_coverage is not None and fact_coverage >= 0.75
    status = (
        "passed" if complete_enough and expected_source_selected and expected_source_used
        and source_checks_passed and partial_gap_ok else "needs_review"
    )
    return {
        **base, "status": status, "score": score, "max_score": 5,
        "fact_coverage": round(fact_coverage, 3) if fact_coverage is not None else None,
        "fact_points": coverage_points, "source_points": source_points,
        "validation_points": validation_points, "matched_facts": matched,
        "missing_expected_facts": missing, "fact_match_details": fact_details,
        "has_source_candidates": has_source_candidates, "has_used_sources": has_used_sources,
        "used_source_ids": sorted(used_ids),
        "expected_source_paths": expected_paths,
        "expected_source_paths_matched": matched_in_sources,
        "expected_paths_found_in_retrieval": matched_in_retrieval,
        "expected_paths_used_in_answer": matched_used_paths,
        "expected_sources_retrieved": expected_source_retrieved,
        "expected_sources_selected": expected_source_selected,
        "expected_sources_used": expected_source_used,
        "source_paths_returned": returned_paths,
        "retrieval_paths_returned": retrieval_paths,
        "source_count": len(sources), "retrieval_count": len(retrieval),
        "source_checks_passed": response.get("source_checks_passed"),
        "validation_status": validation_status,
        "missing_facts_expected": missing_facts_expected,
        "missing_facts_disclosed": missing_disclosed,
        "answer": answer,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        groups[result["category"]].append(result)
    return {
        "total": len(results),
        "passed": sum(result["status"] == "passed" for result in results),
        "needs_review": sum(result["status"] == "needs_review" for result in results),
        "request_errors": sum(result["status"] == "request_error" for result in results),
        "score": sum(result["score"] for result in results),
        "max_score": sum(result["max_score"] for result in results),
        "by_category": {
            category: {
                "total": len(items),
                "passed": sum(item["status"] == "passed" for item in items),
                "needs_review": sum(item["status"] == "needs_review" for item in items),
                "score": sum(item["score"] for item in items),
                "max_score": sum(item["max_score"] for item in items),
            }
            for category, items in groups.items()
        },
    }
