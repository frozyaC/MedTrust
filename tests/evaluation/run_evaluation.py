"""Run MedTrust Golden Set v1 against a live local API."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluator import evaluate_case, summarize

HERE = Path(__file__).resolve().parent
DATASET = HERE / "golden_set_v1.json"
REPORTS = HERE / "reports"


def post_query(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json","Accept":"application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict): raise ValueError("API вернул JSON не в виде объекта")
        return parsed


def validate_dataset(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Fail early when the mandatory Golden Set increment is edited incorrectly."""
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Golden Set должен содержать непустой массив cases")
    if dataset.get("golden_set_id") == "medtrust-registry-golden-set-v1":
        if len(cases) != 49:
            raise ValueError(f"Golden Set v1 должен содержать ровно 49 кейсов, получено {len(cases)}")
    seen: set[str] = set()
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Кейс #{index} должен быть JSON-объектом")
        for required in ("id", "question", "category", "knowledge_coverage"):
            if not case.get(required):
                raise ValueError(f"В кейсе #{index} отсутствует обязательное поле {required}")
        case_id = str(case["id"])
        if case_id in seen:
            raise ValueError(f"Повторяется ID Golden Set: {case_id}")
        seen.add(case_id)
        if case["knowledge_coverage"] not in {"full", "partial", "absent"}:
            raise ValueError(f"Неизвестный knowledge_coverage у {case_id}")
        expected_facts = case.get("expected_facts", [])
        if not isinstance(expected_facts, list) or any(not isinstance(item, str) or not item.strip() for item in expected_facts):
            raise ValueError(f"expected_facts у {case_id} должен быть массивом непустых строк")
        expected_paths = case.get("expected_source_paths", [])
        if not isinstance(expected_paths, list) or any(not isinstance(item, str) or not item.strip() for item in expected_paths):
            raise ValueError(f"expected_source_paths у {case_id} должен быть массивом непустых строк")
        aliases = case.get("expected_fact_aliases", {})
        if not isinstance(aliases, dict):
            raise ValueError(f"expected_fact_aliases у {case_id} должен быть объектом")
        unknown_alias_facts = set(aliases) - set(expected_facts)
        if unknown_alias_facts:
            raise ValueError(f"Алиасы у {case_id} ссылаются на неизвестные факты: {sorted(unknown_alias_facts)}")
        for fact, variants in aliases.items():
            if not isinstance(variants, list) or any(not isinstance(item, str) or not item.strip() for item in variants):
                raise ValueError(f"Алиасы факта {fact!r} у {case_id} должны быть массивом непустых строк")
        if case["knowledge_coverage"] in {"full", "partial"} and not expected_facts:
            raise ValueError(f"Для {case_id} с coverage={case['knowledge_coverage']} нужны expected_facts")
        if case["knowledge_coverage"] == "partial" and not str(case.get("missing_facts") or "").strip():
            raise ValueError(f"Для partial-кейса {case_id} требуется missing_facts")
        if case["knowledge_coverage"] == "absent" and expected_facts:
            raise ValueError(f"Absent-кейс {case_id} не должен содержать expected_facts")
    if dataset.get("golden_set_id") == "medtrust-registry-golden-set-v1":
        expected_ids = {f"Q{number:02d}" for number in range(1, 50)}
        if seen != expected_ids:
            raise ValueError("Golden Set v1 должен содержать ровно ID Q01–Q49")
    declared = dataset.get("categories") or {}
    actual: dict[str, int] = {}
    for case in cases:
        actual[case["category"]] = actual.get(case["category"], 0) + 1
    if declared and actual != declared:
        raise ValueError(
            "Распределение кейсов не совпадает с categories: "
            f"ожидалось {declared}, фактически {actual}"
        )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Ручной запуск оценки MedTrust Golden Set v1")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Адрес MedTrust API")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120.0, help="Таймаут одного запроса, секунд")
    parser.add_argument("--limit", type=int, default=0, help="Ограничить число кейсов для пробного запуска")
    parser.add_argument("--ids", nargs="*", help="Запустить только указанные ID, например Q01 Q25")
    parser.add_argument("--pause", type=float, default=0.2, help="Пауза между запросами, секунд")
    args = parser.parse_args()
    if not 1 <= args.top_k <= 10: parser.error("--top-k должен быть от 1 до 10")
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    try:
        cases = validate_dataset(dataset)
    except ValueError as exc:
        parser.error(f"Некорректный Golden Set: {exc}")
    if args.ids:
        wanted = set(args.ids)
        cases = [case for case in cases if case["id"] in wanted]
        unknown = wanted - {case["id"] for case in cases}
        if unknown: parser.error("Неизвестные ID: " + ", ".join(sorted(unknown)))
    if args.limit < 0: parser.error("--limit не может быть отрицательным")
    if args.limit: cases = cases[:args.limit]
    endpoint = args.base_url.rstrip("/") + "/api/v1/query"
    print(f"Golden Set: {len(cases)} кейсов; endpoint: {endpoint}")
    print("Каждый кейс отправляется в отдельном запросе с conversation_id=null.", flush=True)
    results=[]; raw=[]; started=time.monotonic()
    for index, case in enumerate(cases, 1):
        payload={"question":case["question"],"patient":None,"top_k":args.top_k,"conversation_id":None}
        t0=time.monotonic(); response=None; error=None
        try: response=post_query(endpoint,payload,args.timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc: error=str(exc)
        elapsed=round(time.monotonic()-t0,2)
        result=evaluate_case(case,response,error)
        result["elapsed_seconds"]=elapsed
        results.append(result)
        raw.append({"id":case["id"],"request":payload,"response":response,"error":error,"elapsed_seconds":elapsed})
        print(f"[{index:02d}/{len(cases):02d}] {case['id']} {result['status']} score={result['score']}/{result['max_score']} ({elapsed:.1f}s)",flush=True)
        if args.pause and index < len(cases): time.sleep(args.pause)
    elapsed=round(time.monotonic()-started,2)
    summary=summarize(results)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    REPORTS.mkdir(parents=True,exist_ok=True)
    try:
        git_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=HERE,stderr=subprocess.DEVNULL,text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        git_commit=None
    report={"golden_set_id":dataset["golden_set_id"],"golden_set_version":dataset.get("version"),
            "evaluator_version":dataset.get("evaluator_version", 2),
            "timestamp_utc":stamp,"base_url":args.base_url,
            "git_commit":git_commit,"python_version":platform.python_version(),
            "endpoint":endpoint,"top_k":args.top_k,"elapsed_seconds":elapsed,"case_count":len(cases),
            "declared_categories":dataset.get("categories",{}),
            "summary":summary,"results":results}
    json_path=REPORTS/f"evaluation_{stamp}.json"
    raw_path=REPORTS/f"responses_{stamp}.json"
    md_path=REPORTS/f"evaluation_{stamp}.md"
    json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    raw_path.write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# MedTrust Golden Set v1 — отчёт", "",f"- Дата UTC: {stamp}",f"- API: `{endpoint}`",f"- Кейсов: {len(cases)}",f"- Версия evaluator: {dataset.get('evaluator_version', 2)}",f"- Время: {elapsed:.1f} сек", "",
           "## Сводка", "",f"- Passed: {summary['passed']}",f"- Needs review: {summary['needs_review']}",f"- Ошибки запросов: {summary['request_errors']}",f"- Баллы: {summary['score']} / {summary['max_score']}", "",
           "## По категориям", "", "| Категория | Кейсов | Passed | Needs review | Баллы |", "|---|---:|---:|---:|---:|"]
    for category,item in summary["by_category"].items(): lines.append(f"| {category} | {item['total']} | {item['passed']} | {item['needs_review']} | {item['score']} / {item['max_score']} |")
    lines += ["", "## Результаты по кейсам", "", "| ID | Вопрос | Факты | Источник найден | Источник использован | Статус |", "|---|---|---:|---|---|---|"]
    for item in results:
        facts = "—" if item.get("fact_coverage") is None else f"{item['fact_coverage']:.0%}"
        retrieved = "—" if "expected_sources_retrieved" not in item else ("да" if item["expected_sources_retrieved"] else "нет")
        used = "—" if "expected_sources_used" not in item else ("да" if item["expected_sources_used"] else "нет")
        lines.append(f"| {item['id']} | {item['question'].replace('|', '/')} | {facts} | {retrieved} | {used} | {item['status']} ({item['score']}/{item['max_score']}) |")
    lines += ["", "## Методика оценки", "",
              "Для кейсов full/partial: 3 балла — покрытие ожидаемых фактов; 1 — ожидаемый документ найден в retrieval; 1 — API-проверка источников прошла (для partial также требуется раскрыть пропуск). Статус `passed` требует покрытия не менее 75%, выбора и использования ожидаемого источника, прохождения API-проверки и раскрытия ожидаемых пробелов.",
              "Для кейсов absent: 2 балла — явный отказ от неподтверждённого ответа; 1 — отсутствие использованных источников. Нерелевантные кандидаты retrieval сами по себе не считаются использованием.",
              "Сопоставление фактов детерминированное: точное нормализованное совпадение, явно заданные алиасы/regex или строгое совпадение терминов. Числа и коды не ослабляются. Путь документа нормализуется: убираются корневые префиксы, расширение `.md`, различия слешей и подчёркиваний.",
              "", "## Кейсы, требующие проверки", ""]
    for item in results:
        if item["status"] != "passed":
            extra = ""
            if item.get("missing_expected_facts"):
                extra = "; пропущено фактов: " + str(len(item["missing_expected_facts"]))
            lines.append(f"- **{item['id']} — {item['question']}**: {item['status']}, {item['score']}/{item['max_score']}{extra}")
    lines += ["", "> Golden Set — обязательный регрессионный инкремент проекта. Результат evaluator — воспроизводимый технический сигнал, а не гарантия медицинской корректности; новые/пограничные кейсы требуют ручной проверки эталонов и ответов.", ""]
    md_path.write_text("\n".join(lines),encoding="utf-8")
    print("\nИТОГ")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print(f"\nОтчёты:\n- {md_path}\n- {json_path}\n- {raw_path}")
    # Golden Set is a quality gate: a request error or any unresolved case must
    # fail the process so CI/PowerShell can detect a non-passing evaluation.
    return 1 if summary["request_errors"] or summary["needs_review"] else 0

if __name__ == "__main__": sys.exit(main())
