"""Run Cardioline Cardiology Golden Set v1 against MedTrust /api/v1/query.

Uses only the local-query endpoint. The script does not invoke web search directly.
"""
from __future__ import annotations
import argparse, json, math, platform, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from evaluator_cardiology import evaluate_case, normalize_path, _path_matches, summarize

HERE = Path(__file__).resolve().parent
DATASET = HERE / "golden_set_cardiology_v1.json"
REPORTS = HERE / "reports"


def post_query(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json; charset=utf-8", "Accept":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("API returned JSON that is not an object")
    return parsed


def get_paths(items: Any) -> list[str]:
    out = []
    if not isinstance(items, list): return out
    for item in items:
        if not isinstance(item, dict): continue
        path = item.get("path") or item.get("source_path") or item.get("document_path")
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        path = path or meta.get("path") or meta.get("source_path")
        if not path and isinstance(item.get("path_segments"), list): path = "/".join(map(str, item["path_segments"]))
        if path: out.append(str(path))
    return out


def retrieval_metrics(case_results: list[dict[str, Any]], k: int) -> dict[str, Any]:
    per_case = []
    for result in case_results:
        expected = result.get("expected_source_paths", [])
        retrieved = result.get("retrieval_paths_returned", [])
        if not expected:
            continue
        relevant_ranks = []
        found_expected = set()
        for rank, actual in enumerate(retrieved[:k], start=1):
            for exp in expected:
                if _path_matches(exp, actual):
                    relevant_ranks.append(rank)
                    found_expected.add(exp)
                    break
        precision = len(relevant_ranks) / k
        recall = len(found_expected) / len(expected)
        mrr = (1.0 / min(relevant_ranks)) if relevant_ranks else 0.0
        dcg = sum(1.0 / math.log2(rank + 1) for rank in relevant_ranks)
        ideal_hits = min(len(expected), k)
        idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        ndcg = dcg / idcg if idcg else 0.0
        per_case.append({"id": result["id"], "precision_at_k": precision, "recall_at_k": recall, "mrr_at_k": mrr, "ndcg_at_k": ndcg, "relevant_ranks": relevant_ranks})
    n = len(per_case)
    if not n:
        return {"evaluated_cases": 0, "k": k, "precision_at_k": 0.0, "recall_at_k": 0.0, "mrr_at_k": 0.0, "ndcg_at_k": 0.0, "per_case": []}
    return {
        "evaluated_cases": n, "k": k,
        "precision_at_k": round(sum(x["precision_at_k"] for x in per_case)/n, 4),
        "recall_at_k": round(sum(x["recall_at_k"] for x in per_case)/n, 4),
        "mrr_at_k": round(sum(x["mrr_at_k"] for x in per_case)/n, 4),
        "ndcg_at_k": round(sum(x["ndcg_at_k"] for x in per_case)/n, 4),
        "per_case": per_case,
    }


def policy_diagnostics(response: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(response, dict): return {"search_backend": None, "web_search_attempted": None, "local_wiki_policy_ok": False}
    diag = response.get("answer_review_diagnostics") or {}
    evidence = diag.get("source_evidence_check") or {}
    backend = evidence.get("search_backend")
    attempted = evidence.get("web_search_attempted")
    # Some earlier API builds expose only web_search_enabled. Treat missing telemetry as unverified, not as success.
    return {"search_backend": backend, "web_search_attempted": attempted,
            "local_wiki_policy_ok": backend == "local_wiki_only" and attempted is False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Cardiology Golden Set v1 for MedTrust local Wiki RAG")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=0, help="Run the first N cases; --limit 5 is the pilot")
    parser.add_argument("--ids", nargs="*", help="Run explicit case IDs, e.g. CK01 CK04 CK10")
    parser.add_argument("--pause", type=float, default=0.2)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 10: parser.error("--top-k must be between 1 and 10")
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    cases = data["cases"]
    if args.ids:
        wanted = set(args.ids)
        selected = [c for c in cases if c["id"] in wanted]
        unknown = wanted - {c["id"] for c in selected}
        if unknown: parser.error("Unknown IDs: " + ", ".join(sorted(unknown)))
        cases = selected
    elif args.limit:
        cases = cases[:args.limit]
    if not cases: parser.error("No cases selected")

    endpoint = args.base_url.rstrip("/") + "/api/v1/query"
    print(f"Cardiology Golden Set: {len(cases)} cases; endpoint: {endpoint}")
    print("Each case is sent separately with conversation_id=null; web search is not requested.", flush=True)
    results, raw = [], []
    started = time.monotonic()
    for index, case in enumerate(cases, 1):
        payload = {"question": case["question"], "patient": None, "top_k": args.top_k, "conversation_id": None}
        t0 = time.monotonic(); response = None; error = None
        try:
            response = post_query(endpoint, payload, args.timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            error = str(exc)
        elapsed = round(time.monotonic() - t0, 2)
        result = evaluate_case(case, response, error)
        result["elapsed_seconds"] = elapsed
        retrieval = response.get("retrieval") if isinstance(response, dict) else []
        result["retrieval_paths_returned"] = get_paths(retrieval)
        result["policy"] = policy_diagnostics(response)
        results.append(result)
        raw.append({"id": case["id"], "request": payload, "response": response, "error": error,
                    "elapsed_seconds": elapsed, "policy": result["policy"]})
        print(f"[{index:02d}/{len(cases):02d}] {case['id']} {result['status']} score={result['score']}/{result['max_score']} ({elapsed:.1f}s) | local_only={result['policy']['local_wiki_policy_ok']}", flush=True)
        if args.pause and index < len(cases): time.sleep(args.pause)

    elapsed = round(time.monotonic() - started, 2)
    summary = summarize(results)
    summary["retrieval_metrics"] = retrieval_metrics(results, args.top_k)
    summary["local_wiki_policy_passed"] = sum(bool(x["policy"]["local_wiki_policy_ok"]) for x in results)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORTS.mkdir(parents=True, exist_ok=True)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE.parents[2], stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError): commit = None
    report = {"golden_set_id": data["golden_set_id"], "timestamp_utc": stamp, "base_url": args.base_url,
              "endpoint": endpoint, "git_commit": commit, "python_version": platform.python_version(),
              "top_k": args.top_k, "elapsed_seconds": elapsed, "case_count": len(cases),
              "summary": summary, "results": results}
    json_path = REPORTS / f"cardiology_evaluation_{stamp}.json"
    raw_path = REPORTS / f"cardiology_responses_{stamp}.json"
    md_path = REPORTS / f"cardiology_evaluation_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Cardiology Golden Set v1 — report", "", f"- UTC: {stamp}", f"- Endpoint: `{endpoint}`",
             f"- Cases: {len(cases)}", f"- Elapsed: {elapsed:.1f}s", "", "## Summary", "",
             f"- Passed: {summary['passed']}", f"- Needs review: {summary['needs_review']}",
             f"- Request errors: {summary['request_errors']}", f"- Score: {summary['score']} / {summary['max_score']}",
             f"- Local-only policy confirmed: {summary['local_wiki_policy_passed']} / {len(cases)}", "",
             "## Retrieval", "", f"- Precision@{args.top_k}: {summary['retrieval_metrics']['precision_at_k']}",
             f"- Recall@{args.top_k}: {summary['retrieval_metrics']['recall_at_k']}",
             f"- MRR@{args.top_k}: {summary['retrieval_metrics']['mrr_at_k']}",
             f"- NDCG@{args.top_k}: {summary['retrieval_metrics']['ndcg_at_k']}", "", "## Cases", "",
             "| ID | Status | Score | Local-only |", "|---|---|---:|---|"]
    for item in results:
        lines.append(f"| {item['id']} | {item['status']} | {item['score']}/{item['max_score']} | {item['policy']['local_wiki_policy_ok']} |")
    lines += ["", "## Cases requiring review", ""]
    for item in results:
        if item["status"] != "passed" or not item["policy"]["local_wiki_policy_ok"]:
            lines.append(f"- **{item['id']} — {item['question']}**: {item['status']}, {item['score']}/{item['max_score']}; policy={item['policy']}")
    lines += ["", "> Evaluation is deterministic and is not a clinical correctness certification. The KB archive identifies all content as demonstration/fictitious data.", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print("\nSUMMARY")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nReports:")
    print(md_path.resolve()); print(json_path.resolve()); print(raw_path.resolve())
    # A query error is a runner failure; model-quality failures are reported but do not crash the command.
    return 1 if summary["request_errors"] else 0

if __name__ == "__main__":
    sys.exit(main())
