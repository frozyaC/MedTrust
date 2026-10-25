"""Independent manual web-search: broader discovery, no knowledge-gap writes."""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from app.services.gigachat import get_gigachat_client
from app.services.web_search import (
    SearXNGWebSearchClient, WebSearchResult, _broad_search_queries,
    is_relevant_web_result, has_answerable_web_evidence,
)


def _public_https(url: str) -> bool:
    """Exclude local, private and non-HTTPS addresses from user-visible links."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 443):
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host and all(part for part in host.split("."))
    except ValueError:
        return False


def _queries(question: str) -> list[str]:
    cleaned = " ".join(question.split())[:350]
    variants = [cleaned]
    if re.search(r"(?:мрт|магнитно.?резонансн|\bmri\b)", cleaned, re.I):
        if re.search(r"контраст|contrast|gadolinium", cleaned, re.I):
            variants.extend([
                "MRI contrast contraindications gadolinium patient safety kidney pregnancy",
                "MRI gadolinium contrast contraindications radiology patient information",
                "МРТ с контрастом противопоказания почки беременность",
            ])
        else:
            variants.append("MRI contraindications patient safety")
    variants.extend(_broad_search_queries(cleaned)[:3])
    # A shorter query often succeeds where the full question does not.
    simplified = re.sub(r"(?i)^(какие|какова|что такое|перечисли|расскажи|укажи)\s+", "", cleaned)
    simplified = simplified.rstrip("?.! ")
    variants.append(simplified)
    return list(dict.fromkeys(x for x in variants if x))[:7]


def manual_web_answer(question: str, limit: int = 5) -> dict:
    client = SearXNGWebSearchClient()
    if not client.settings.web_search_enabled:
        return {"status": "disabled", "answer": "Веб-поиск отключён.",
                "sources": [], "warning": "Веб-поиск недоступен."}

    attempts = []
    candidates: dict[str, WebSearchResult] = {}
    completed = False
    provider_count = 0
    blocked_count = 0
    for search_query in _queries(question):
        timeout = (client.settings.web_search_timeout_seconds if not attempts
                   else client.settings.web_search_fallback_timeout_seconds)
        raw = client._request(search_query, timeout)
        attempts.append({"query": search_query, "result_count": None if raw is None else len(raw)})
        if raw is None:
            continue
        completed = True
        provider_count += len(raw)
        for rank, entry in enumerate(raw, 1):
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "").strip()
            if not _public_https(url):
                blocked_count += 1
                continue
            if url in candidates:
                continue
            host = urlparse(url).hostname or ""
            candidates[url] = WebSearchResult(
                title=str(entry.get("title") or host)[:300], url=url,
                snippet=str(entry.get("content") or entry.get("snippet") or entry.get("description") or "")[:4000],
                rank=rank, domain=host,
            )
        if len(candidates) >= limit:
            break

    diagnostics = {"attempted_queries": attempts, "provider_results": provider_count,
                   "rejected_unsafe_urls": blocked_count,
                   "usable_results": len(candidates)}
    if not candidates:
        status = "api_error" if not completed else "no_results"
        detail = ("SearXNG не ответил ни на один поисковый запрос." if not completed
                  else "SearXNG вернул 0 результатов." if provider_count == 0
                  else "SearXNG вернул результаты, но ни один URL не прошёл проверку безопасности.")
        return {"status": status, "answer": detail, "sources": [],
                "warning": "Источники отсутствуют; генерировать фактический ответ не из чего.",
                "diagnostics": diagnostics}

    # For public non-allowlisted domains use ONLY the search snippet; never fetch
    # arbitrary URLs (avoids server-side request forgery through redirects/DNS).
    picked = list(candidates.values())[:limit]
    trusted = [item for item in picked if client._parse_safe_results(
        [{"url": item.url, "title": item.title, "content": item.snippet}], limit=1)]
    trusted_urls = {item.url for item in trusted}
    enriched_by_url = {item.url: item for item in client._enrich_results(trusted, query=question)}
    sources = []
    context = []
    for index, item in enumerate(picked, 1):
        item = enriched_by_url.get(item.url, item)
        relevant = is_relevant_web_result(question, item)
        evidence = relevant and has_answerable_web_evidence(question, item)
        sid = f"WEB{index}"
        sources.append({"source_id": sid, "title": item.title, "url": item.url,
                        "domain": item.domain, "relevance": "relevant" if relevant else "low",
                        "evidence_status": "supported_candidate" if evidence else "unverified",
                        "content_type": "page" if item.url in trusted_urls else "search_snippet"})
        context.append(f"[{sid}] {item.title}\nURL: {item.url}\nТекст: {item.snippet[:3500]}")

    prompt = (
        "Ты помощник регистратора MedTrust. Это отдельный РУЧНОЙ веб-поиск, "
        "а не проверенный медицинский справочник. Ответь по текстам ниже, "
        "используя и частично релевантные материалы. Приводи только сведения, "
        "которые действительно содержатся в предоставленном тексте. "
        "Не выдумывай противопоказания, факты, цены, цитаты или URL. "
        "Если данных мало, объясни что установлено, а что не подтверждено. "
        "Каждый существенный факт снабжай ссылкой [WEB1], [WEB2] и т. п. "
        "Не добавляй предупреждение: система добавит его в конце.\n\n"
        f"Вопрос: {question}\n\n" + "\n\n".join(context)
    )
    answer = str(get_gigachat_client().chat(prompt)).strip()
    if not answer:
        answer = "По найденным материалам не удалось сформировать содержательный ответ."
    links = "\n".join(f"- [{s['source_id']}] {s['title']} — {s['url']}" for s in sources)
    warning = (
        "Внимание: расширенный веб-поиск. Некоторые источники могут быть нерелевантными "
        "или содержать неподтверждённые сведения. Поисковые фрагменты не равнозначны "
        "проверенным медицинским рекомендациям. Перед записью пациента сверьте "
        "информацию с инструкциями клиники или профильным специалистом."
    )
    return {"status": "success", "answer": f"{answer}\n\nИсточники:\n{links}\n\n{warning}",
            "sources": sources, "warning": warning, "diagnostics": diagnostics}
