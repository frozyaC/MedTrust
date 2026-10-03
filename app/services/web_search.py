from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from app.core.config import get_settings
from app.services.safety import DEFAULT_SAFE_DOMAINS, is_safe_domain


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    rank: int
    domain: str


@dataclass(frozen=True)
class WebSearchResponse:
    status: str
    results: list[WebSearchResult]
    error: str | None = None




class _HTMLTextExtractor(HTMLParser):
    """Small stdlib-only HTML-to-text extractor for trusted web pages."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)


def _extract_html_text(html: str, max_chars: int) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    text = " ".join(parser.parts)
    return text[:max_chars].strip()


class SearXNGWebSearchClient:
    """Local web-search adapter backed by SearXNG.

    The client first performs a normal search. If the returned pages do not
    contain enough trusted medical sources, it retries with ``site:``
    restrictions for a small set of authoritative domains. This keeps the
    allowlist as a final security boundary while making the fallback useful
    when generic search ranks commercial or encyclopedic pages first.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        configured = {
            x.strip().lower()
            for x in self.settings.web_safe_domains.split(",")
            if x.strip()
        }
        self.allowed_domains = configured or DEFAULT_SAFE_DOMAINS
        self.authority_domains = tuple(
            x.strip().lower()
            for x in self.settings.web_fallback_domains.split(",")
            if x.strip()
        )

    def _request(self, query: str, timeout: int) -> list[dict] | None:
        try:
            response = requests.get(
                f"{self.settings.searxng_url.rstrip('/')}/search",
                params={
                    "q": query[:600],
                    "format": "json",
                    "language": self.settings.web_search_language,
                    "safesearch": 1,
                    "categories": "general",
                },
                headers={"Accept": "application/json"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException:
            return None
        except ValueError:
            return None

        raw = payload.get("results", [])
        if not isinstance(raw, list):
            return []
        return raw

    def _parse_safe_results(
        self, raw: list[dict], start_rank: int = 1, limit: int = 3
    ) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        seen_urls: set[str] = set()

        for provider_rank, item in enumerate(raw, start=start_rank):
            if not isinstance(item, dict):
                continue

            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls or not is_safe_domain(url, self.allowed_domains):
                continue

            domain = (urlparse(url).hostname or "").lower()
            results.append(
                WebSearchResult(
                    title=str(item.get("title") or domain),
                    url=url,
                    snippet=str(
                        item.get("content")
                        or item.get("snippet")
                        or item.get("description")
                        or ""
                    ),
                    rank=provider_rank,
                    domain=domain,
                )
            )
            seen_urls.add(url)
            if len(results) >= limit:
                break

        return results

    def _enrich_results(self, results: list[WebSearchResult]) -> list[WebSearchResult]:
        enriched: list[WebSearchResult] = []
        for result in results:
            # Only fetch URLs that already passed the HTTPS + allowlist checks.
            # This keeps source enrichment inside the same SSRF/security boundary.
            try:
                response = requests.get(
                    result.url,
                    headers={
                        "Accept": "text/html,application/xhtml+xml",
                        "User-Agent": "MedTrust/1.0 local research client",
                    },
                    timeout=self.settings.web_search_fallback_timeout_seconds,
                    verify=True,
                    allow_redirects=False,
                )
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "html" in content_type or not content_type:
                    page_text = _extract_html_text(
                        response.text, self.settings.web_source_max_chars
                    )
                    if page_text:
                        result = WebSearchResult(
                            title=result.title,
                            url=result.url,
                            snippet=page_text,
                            rank=result.rank,
                            domain=result.domain,
                        )
            except (requests.RequestException, UnicodeError):
                # A blocked or malformed page must not remove an otherwise safe
                # search result; the original search snippet remains usable.
                pass
            enriched.append(result)
        return enriched

    def search(self, query: str, limit: int = 3) -> WebSearchResponse:
        if not self.settings.web_search_enabled:
            return WebSearchResponse("disabled", [])

        requested_limit = max(1, min(limit, 3))
        raw = self._request(query, self.settings.web_search_timeout_seconds)
        if raw is None:
            return WebSearchResponse("api_error", [])
        results = self._parse_safe_results(raw or [], limit=requested_limit)
        if len(results) >= requested_limit:
            return WebSearchResponse("success", self._enrich_results(results))

        # Generic search may return useful-looking but untrusted pages first.
        # Retry with explicit authoritative-domain queries, then apply the same
        # HTTPS + allowlist checks again. We deliberately take at most one result
        # from each authority domain during the first fallback pass so that a
        # single domain (for example NICE) cannot consume all WEB1-WEB3 slots.
        seen_urls = {item.url for item in results}
        max_domains = max(1, self.settings.web_fallback_max_domains)
        fallback_batches: list[list[WebSearchResult]] = []

        for domain in self.authority_domains[:max_domains]:
            fallback_query = f"site:{domain} {query}"
            fallback_raw = self._request(
                fallback_query, self.settings.web_search_fallback_timeout_seconds
            )
            if fallback_raw is None:
                continue
            parsed = self._parse_safe_results(fallback_raw, start_rank=1, limit=requested_limit)
            if parsed:
                fallback_batches.append(parsed)

        # First pass: diversify authoritative sources.
        for batch in fallback_batches:
            if len(results) >= requested_limit:
                break
            candidate = next((item for item in batch if item.url not in seen_urls), None)
            if candidate is None:
                continue
            results.append(candidate)
            seen_urls.add(candidate.url)

        # Second pass: if fewer than requested_limit remain, fill the slots with
        # additional safe results from the same authoritative-domain searches.
        if len(results) < requested_limit:
            for batch in fallback_batches:
                for item in batch:
                    if len(results) >= requested_limit:
                        break
                    if item.url in seen_urls:
                        continue
                    results.append(item)
                    seen_urls.add(item.url)

        if results:
            return WebSearchResponse("success", self._enrich_results(results))
        return WebSearchResponse("no_safe_results", [])


# Keep a stable service name for future provider swaps.
WebSearchClient = SearXNGWebSearchClient
