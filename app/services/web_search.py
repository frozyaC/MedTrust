from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlparse

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


# A source must match a meaningful topic from the query. These bilingual families
# cover common conditions that often have different names in Russian and English.
# Unknown topics are checked with conservative token overlap below.
_TOPIC_PATTERNS: dict[str, tuple[str, ...]] = {
    "migraine": (r"мигрен\w*", r"migrain\w*"),
    "me_cfs": (
        r"myalgic\s+encephalomyelitis",
        r"chronic\s+fatigue\s+syndrome",
        r"миалгическ\w*\s+энцефаломиелит\w*",
        r"синдром\s+хроническ\w*\s+усталост\w*",
    ),
    "multiple_sclerosis": (
        r"multiple\s+sclerosis",
        r"рассеянн\w*\s+склероз\w*",
    ),
    "hypertension": (
        r"hypertension",
        r"high\s+blood\s+pressure",
        r"гипертенз\w*",
        r"гипертони\w*",
    ),
    "diabetes": (r"diabet\w*", r"диабет\w*"),
    "asthma": (r"asthma\w*", r"астм\w*"),
    "stroke": (r"stroke\w*", r"инсульт\w*"),
    "epilepsy": (r"epilep\w*", r"эпилепс\w*"),
    "depression": (r"depress\w*", r"депресс\w*"),
    "pneumonia": (r"pneumoni\w*", r"пневмони\w*"),
    "osteoarthritis": (r"osteoarthritis", r"остеоартроз\w*"),
    "arthritis": (r"(?<!osteo)arthritis\w*", r"артрит\w*"),
    "heart_failure": (
        r"heart\s+failure",
        r"сердечн\w*\s+недостаточност\w*",
    ),
    "atrial_fibrillation": (
        r"atrial\s+fibrillation",
        r"фибрилляц\w*\s+предсерд\w*",
    ),
    "myocardial_infarction": (
        r"myocardial\s+infarction",
        r"heart\s+attack",
        r"инфаркт\w*\s+миокард\w*",
    ),
    "parkinsons_disease": (
        r"parkinson\w*(?:\s+disease)?",
        r"болезн\w*\s+паркинсон\w*",
    ),
    "alzheimers_disease": (
        r"alzheimer\w*(?:\s+disease)?",
        r"болезн\w*\s+альцгеймер\w*",
    ),
    "copd": (
        r"copd",
        r"chronic\s+obstructive\s+pulmonary\s+disease",
        r"хроническ\w*\s+обструктивн\w*\s+болезн\w*\s+лёгк\w*",
        r"хроническ\w*\s+обструктивн\w*\s+болезн\w*\s+легк\w*",
    ),
    "covid": (r"covid(?:[-\s]?19)?", r"коронавирус\w*", r"ковид\w*"),
    "influenza": (r"influenza\w*", r"грипп\w*"),
    "anemia": (r"anaemia\w*", r"anemia\w*", r"анеми\w*"),
    "kidney_disease": (
        r"chronic\s+kidney\s+disease",
        r"kidney\s+disease",
        r"болезн\w*\s+почек",
        r"почечн\w*\s+недостаточност\w*",
    ),
    "reflux": (
        r"gastro.?oesophageal\s+reflux",
        r"gastro.?esophageal\s+reflux",
        r"гастроэзофагеальн\w*\s+рефлюкс\w*",
    ),
    "appendicitis": (r"appendicit\w*", r"аппендицит\w*"),
    "endometriosis": (r"endometriosis", r"эндометриоз\w*"),
    "rheumatoid_arthritis": (
        r"rheumatoid\s+arthritis",
        r"ревматоидн\w*\s+артрит\w*",
    ),
    "back_pain": (
        r"low\s+back\s+pain",
        r"back\s+pain",
        r"боль\w*\s+в\s+спин\w*",
        r"боль\w*\s+в\s+поясниц\w*",
    ),
    "anxiety_disorder": (
        r"anxiety\s+disorder",
        r"generalized\s+anxiety",
        r"тревожн\w*\s+расстройств\w*",
    ),
}
_COMPILED_TOPIC_PATTERNS = {
    topic: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for topic, patterns in _TOPIC_PATTERNS.items()
}

_INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "diagnosis": (r"diagnos\w*", r"диагност\w*", r"диагноз\w*"),
    "treatment": (
        r"treat\w*", r"therap\w*", r"management", r"лечени\w*", r"терап\w*",
        r"лечебн\w*",
    ),
    "recommendations": (
        r"recommend\w*", r"guideline\w*", r"guidance", r"рекомендац\w*",
        r"клиническ\w*\s+рекомендац\w*",
    ),
    "prevention": (r"prevent\w*", r"prevention", r"профилактик\w*"),
    "symptoms": (r"symptom\w*", r"signs?", r"симптом\w*", r"признак\w*"),
    "tests": (
        r"test\w*", r"screen\w*", r"investigation\w*", r"анализ\w*",
        r"обследован\w*", r"исследован\w*",
    ),
    "dosage": (
        r"dosage", r"dose\w*", r"дозиров\w*", r"доз\w*", r"приём\w*",
        r"прием\w*",
    ),
}
_COMPILED_INTENT_PATTERNS = {
    intent: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for intent, patterns in _INTENT_PATTERNS.items()
}
_TOKEN_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_STOP_WORDS = {
    "а", "без", "бы", "быть", "в", "во", "вот", "все", "всех", "вы", "где",
    "для", "до", "его", "ее", "её", "если", "же", "за", "и", "из", "или",
    "им", "их", "как", "какая", "какие", "какой", "каком", "когда", "кто",
    "ли", "мне", "мы", "на", "над", "не", "него", "нее", "неё", "ни", "но",
    "о", "об", "однако", "он", "она", "они", "оно", "от", "по", "под", "при",
    "про", "с", "со", "так", "также", "то", "того", "тоже", "у", "уже", "что",
    "чтобы", "это", "этот", "эта", "эти", "этом", "я", "the", "a", "an", "and",
    "are", "as", "at", "be", "by", "can", "could", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "should", "that", "the",
    "this", "to", "was", "were", "what", "when", "where", "which", "who", "why",
    "with", "would", "you", "your",
}
_GENERIC_PREFIXES = (
    # Russian query intent and general medical vocabulary.
    "современ", "новейш", "актуальн", "рекомендац", "диагност", "взросл", "пациент",
    "врач", "медицин", "болезн", "заболев", "симптом", "лечени", "лечеб", "лечит",
    "терап", "профилактик", "причин", "клиническ", "оценк", "обследован", "осмотр",
    "исследован", "информац", "помощ", "подход", "руководств", "данн", "методик",
    "признак", "состояни", "проявлен", "эффективн", "безопасн", "обзор", "вопрос",
    # English query intent and general medical vocabulary.
    "modern", "current", "latest", "recommend", "guideline", "diagnos", "adult",
    "patient", "medical", "disease", "symptom", "treat", "therap", "prevent", "cause",
    "clinical", "assess", "examin", "research", "information", "care", "approach",
    "evidence", "method", "sign", "condition", "effective", "safety", "overview",
    "review", "question", "management",
)
_RUSSIAN_SUFFIXES = tuple(sorted((
    "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими", "иях", "ах",
    "ях", "ией", "иям", "ыми", "ими", "ью", "ия", "ие", "ые", "ое", "ая", "яя",
    "ой", "ий", "ый", "ую", "юю", "ов", "ев", "ей", "ам", "ям", "ом", "ем",
    "а", "я", "ы", "и", "у", "ю", "е", "о", "ь",
), key=len, reverse=True))
_ENGLISH_SUFFIXES = ("ization", "ations", "ation", "ments", "ment", "ingly", "edly", "ing", "ed", "es", "s")


_TOPIC_ENGLISH_TERMS: dict[str, str] = {
    "migraine": "migraine",
    "me_cfs": "myalgic encephalomyelitis chronic fatigue syndrome",
    "multiple_sclerosis": "multiple sclerosis",
    "hypertension": "hypertension high blood pressure",
    "diabetes": "diabetes",
    "asthma": "asthma",
    "stroke": "stroke",
    "epilepsy": "epilepsy",
    "depression": "depression",
    "pneumonia": "pneumonia",
    "osteoarthritis": "osteoarthritis",
    "arthritis": "arthritis",
    "heart_failure": "heart failure",
    "atrial_fibrillation": "atrial fibrillation",
    "myocardial_infarction": "myocardial infarction heart attack",
    "parkinsons_disease": "Parkinson disease",
    "alzheimers_disease": "Alzheimer disease",
    "copd": "chronic obstructive pulmonary disease COPD",
    "covid": "COVID-19",
    "influenza": "influenza",
    "anemia": "anemia anaemia",
    "kidney_disease": "chronic kidney disease",
    "reflux": "gastroesophageal reflux",
    "appendicitis": "appendicitis",
    "endometriosis": "endometriosis",
    "rheumatoid_arthritis": "rheumatoid arthritis",
    "back_pain": "back pain low back pain",
    "anxiety_disorder": "anxiety disorder",
}
_INTENT_ENGLISH_TERMS: dict[str, str] = {
    "diagnosis": "diagnosis",
    "treatment": "treatment",
    "recommendations": "guidelines",
    "prevention": "prevention",
    "symptoms": "symptoms",
    "tests": "testing",
    "dosage": "dosage",
}

def _fallback_search_terms(query: str, domain: str | None = None) -> str:
    """Build a concise English search phrase for English-language medical sites.

    Keep the original query for the generic SearXNG pass. For domain-restricted
    fallback searches, explicit English topic and intent terms avoid matching a
    random document merely because common translated words overlap.
    """
    # Russian clinical-guideline catalogs should receive the original Russian
    # query, while English-language sites benefit from an English fallback.
    if domain and domain.lower().endswith(("minzdrav.gov.ru",)):
        return query.strip()

    topics = _topic_ids(query)
    if not topics:
        return query.strip()

    terms: list[str] = []
    for topic in sorted(topics):
        term = _TOPIC_ENGLISH_TERMS.get(topic)
        if term:
            terms.append(term)

    intents = _intent_ids(query)
    for intent in sorted(intents):
        term = _INTENT_ENGLISH_TERMS.get(intent)
        if term:
            terms.append(term)

    if re.search(r"взросл|\badult", query, re.IGNORECASE):
        terms.append("adults")
    if not intents:
        terms.append("clinical guidance")
    # Ordered deduplication keeps search requests short and deterministic.
    return " ".join(dict.fromkeys(" ".join(terms).split()))


def _stem_token(token: str) -> str:
    token = token.lower()
    if re.fullmatch(r"[а-яё]+", token):
        for suffix in _RUSSIAN_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[: -len(suffix)]
        return token
    if re.fullmatch(r"[a-z]+", token):
        for suffix in _ENGLISH_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[: -len(suffix)]
    return token


def _meaningful_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _TOKEN_RE.findall(unquote(text).lower()):
        if raw in _STOP_WORDS or len(raw) < 4:
            continue
        stem = _stem_token(raw)
        if stem in _STOP_WORDS or any(stem.startswith(prefix) for prefix in _GENERIC_PREFIXES):
            continue
        terms.add(stem)
    return terms


def _topic_ids(text: str) -> set[str]:
    normalized = unquote(text).lower().replace("_", " ").replace("-", " ")
    return {
        topic
        for topic, patterns in _COMPILED_TOPIC_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    }


def _intent_ids(text: str) -> set[str]:
    normalized = unquote(text).lower().replace("_", " ").replace("-", " ")
    return {
        intent
        for intent, patterns in _COMPILED_INTENT_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    }


def is_relevant_web_result(query: str, result: WebSearchResult) -> bool:
    """Conservatively reject safe-but-off-topic pages before answer generation.

    Domain allowlisting only establishes source safety, not subject relevance.
    Recognized medical-topic families must occur in both query and source. For
    other topics, require overlap between meaningful non-boilerplate terms.
    """
    if not query.strip():
        return False

    source_text = f"{result.title}\n{unquote(result.url)}\n{result.snippet}"
    query_topics = _topic_ids(query)
    query_intents = _intent_ids(query)
    source_topics = _topic_ids(source_text)
    source_intents = _intent_ids(source_text)
    if query_topics:
        if not query_topics.intersection(source_topics):
            return False
        # Topic similarity alone can still surface a broad overview instead of
        # the requested kind of guidance (for example symptoms instead of diagnosis).
        if query_intents and not query_intents.intersection(source_intents):
            return False
        return True

    query_terms = _meaningful_terms(query)
    source_terms = _meaningful_terms(source_text)
    if not query_terms:
        return False
    overlap = query_terms & source_terms
    required = 2 if len(query_terms) >= 5 else 1
    if len(overlap) < required:
        return False
    if query_intents and not query_intents.intersection(source_intents):
        return False
    return True


def _metadata_may_be_relevant(query: str, result: WebSearchResult) -> bool:
    """Pre-filter only obvious mismatches before fetching the safe page.

    Metadata is often just a short search snippet. For recognized conditions,
    absence of the condition or requested intent in metadata is ambiguous, not a
    rejection: the full page may still contain the relevant section. A different
    explicitly identified condition or a clearly different intent is a mismatch.
    """
    source_text = f"{result.title}\n{unquote(result.url)}\n{result.snippet}"
    query_topics = _topic_ids(query)
    source_topics = _topic_ids(source_text)
    query_intents = _intent_ids(query)
    source_intents = _intent_ids(source_text)

    if query_topics:
        if source_topics and not query_topics.intersection(source_topics):
            return False
        if (
            query_topics.intersection(source_topics)
            and query_intents
            and source_intents
            and not query_intents.intersection(source_intents)
        ):
            return False
        return True

    query_terms = _meaningful_terms(query)
    source_terms = _meaningful_terms(source_text)
    if query_terms and source_terms and not (query_terms & source_terms):
        return False
    if (
        query_intents
        and source_intents
        and not query_intents.intersection(source_intents)
    ):
        return False
    return True


class _HTMLTextExtractor(HTMLParser):
    """Extract page text while preferring the main/article content over site chrome."""

    _SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "aside"}
    _CONTENT_IDS = {
        "main-content", "main-content-wrapper", "content", "page-content",
        "primary-content", "article-content",
    }

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._tag_stack: list[tuple[str, bool]] = []
        self.parts: list[str] = []
        self.content_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        attr_map = {key.lower(): (value or "").lower() for key, value in attrs}
        is_content = (
            normalized_tag in {"main", "article"}
            or attr_map.get("role") == "main"
            or attr_map.get("id") in self._CONTENT_IDS
        )
        if normalized_tag in self._SKIP_TAGS:
            self._skip_depth += 1
        # Keep all tags (not just content containers), so a nested <div> closing
        # cannot accidentally terminate an outer id="main-content" region.
        self._tag_stack.append((normalized_tag, is_content))

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        # Pop the matching element and its descendants. This is resilient to
        # malformed HTML while preserving the actual main-content boundary.
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index][0] == normalized_tag:
                del self._tag_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(text)
                if any(is_content for _, is_content in self._tag_stack):
                    self.content_parts.append(text)


def _extract_html_text(html: str, max_chars: int) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    # A main/article region is substantially more useful for medical evidence
    # than a page's navigation, cookie notices, footer, and overview boilerplate.
    preferred_parts = parser.content_parts if parser.content_parts else parser.parts
    text = " ".join(preferred_parts)
    return text[:max_chars].strip()


def _preferred_evidence_url(query: str, result: WebSearchResult) -> WebSearchResult:
    """Prefer the actual NICE recommendations chapter over a generic guideline landing page.

    NICE landing pages mainly describe the scope and update history. Those pages
    often pass topical filtering but do not contain the diagnostic thresholds needed
    for a clinically grounded answer. The chapter URL stays on the same allowlisted
    HTTPS host; redirects remain disabled during fetching.
    """
    parsed = urlparse(result.url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.rstrip("/")
    match = re.fullmatch(r"/guidance/([a-z]+\d+)", path, re.IGNORECASE)
    requested_intents = _intent_ids(query)
    needs_detail = bool(
        requested_intents.intersection(
            {"diagnosis", "recommendations", "symptoms", "tests", "treatment", "prevention", "dosage"}
        )
    )
    if (
        hostname in {"nice.org.uk", "www.nice.org.uk"}
        and match
        and needs_detail
    ):
        preferred_path = f"/guidance/{match.group(1).lower()}/chapter/recommendations"
        preferred_url = parsed._replace(path=preferred_path, params="", query="", fragment="").geturl()
        return WebSearchResult(
            title=result.title,
            url=preferred_url,
            snippet=result.snippet,
            rank=result.rank,
            domain=result.domain,
        )
    return result


class SearXNGWebSearchClient:
    """Local SearXNG adapter with both safety and query-relevance filtering."""

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
        self, raw: list[dict], start_rank: int = 1, limit: int = 15
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

    def _enrich_results(
        self, results: list[WebSearchResult], query: str = ""
    ) -> list[WebSearchResult]:
        enriched: list[WebSearchResult] = []
        for result in results:
            # Prefer a content-bearing NICE chapter when search returns its overview.
            # This keeps clinical evidence rather than guideline metadata in the prompt.
            result = _preferred_evidence_url(query, result)
            # Only fetch URLs that already passed the HTTPS + allowlist checks.
            # Never follow redirects; this prevents redirect-based allowlist bypasses.
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
                    page_limit = max(1, int(self.settings.web_source_max_chars))
                    parsed_url = urlparse(result.url)
                    if (
                        (parsed_url.hostname or "").lower() in {"nice.org.uk", "www.nice.org.uk"}
                        and "/chapter/recommendations" in parsed_url.path.lower()
                    ):
                        # Existing .env files may still specify 6000 characters. A
                        # recommendation chapter needs more room than a landing page
                        # to retain assessment, diagnosis, aura and red-flag sections.
                        page_limit = max(page_limit, 14000)
                    page_text = _extract_html_text(response.text, page_limit)
                    if page_text:
                        # Keep page content first and reserve space for a focused
                        # SearXNG snippet. Always cap the final evidence block, even
                        # when the search provider returns an unusually long snippet.
                        search_snippet = result.snippet.strip()
                        marker = "\n\nSearch result snippet: "
                        if search_snippet and search_snippet.casefold() not in page_text.casefold():
                            snippet_budget = min(
                                len(search_snippet), max(0, page_limit - len(marker)), page_limit // 3
                            )
                            body_budget = max(0, page_limit - len(marker) - snippet_budget)
                            combined_text = (
                                page_text[:body_budget].rstrip()
                                + marker
                                + search_snippet[:snippet_budget]
                            )[:page_limit]
                        else:
                            combined_text = page_text[:page_limit]
                        result = WebSearchResult(
                            title=result.title,
                            url=result.url,
                            snippet=combined_text,
                            rank=result.rank,
                            domain=result.domain,
                        )
            except (requests.RequestException, UnicodeError):
                # If the page cannot be fetched, use the SearXNG snippet, but it
                # still has to pass the exact same relevance check afterwards.
                pass
            enriched.append(result)
        return enriched

    def _relevant_and_enriched(
        self,
        query: str,
        candidates: list[WebSearchResult],
        max_fetch: int = 10,
    ) -> list[WebSearchResult]:
        # First remove only explicit contradictions. Do not reject an otherwise
        # safe page merely because its short title/snippet omits the query topic
        # or intent; fetch a bounded shortlist and verify its full text instead.
        viable = [item for item in candidates if _metadata_may_be_relevant(query, item)]
        viable = [_preferred_evidence_url(query, item) for item in viable]
        viable.sort(
            key=lambda item: (not is_relevant_web_result(query, item), item.rank)
        )
        enriched = self._enrich_results(viable[:max(1, max_fetch)], query=query)
        relevant = [item for item in enriched if is_relevant_web_result(query, item)]
        # Restore provider order among equally relevant results for predictable output.
        return sorted(relevant, key=lambda item: item.rank)

    def search(self, query: str, limit: int = 3) -> WebSearchResponse:
        if not self.settings.web_search_enabled:
            return WebSearchResponse("disabled", [])

        requested_limit = max(1, min(limit, 3))
        # Collect more than the final output size. Early truncation caused valid
        # sources just below irrelevant top-ranked results to be lost.
        candidate_limit = min(30, max(15, requested_limit * 10))
        generic_raw = self._request(query, self.settings.web_search_timeout_seconds)
        if generic_raw is None:
            return WebSearchResponse("api_error", [])

        provider_returned_results = bool(generic_raw)
        generic_candidates = self._parse_safe_results(
            generic_raw, limit=candidate_limit
        )
        safe_results_seen = bool(generic_candidates)
        seen_urls = {item.url for item in generic_candidates}
        results = self._relevant_and_enriched(
            query, generic_candidates, max_fetch=max(12, requested_limit * 4)
        )[:requested_limit]
        if len(results) >= requested_limit:
            return WebSearchResponse("success", results)

        # English query terms materially improve recall on English-language
        # authoritative sites (e.g. NICE and PubMed) for Russian questions.
        max_domains = max(1, self.settings.web_fallback_max_domains)
        fallback_batches: list[list[WebSearchResult]] = []
        for domain in self.authority_domains[:max_domains]:
            fallback_terms = _fallback_search_terms(query, domain)
            fallback_query = f"site:{domain} {fallback_terms}"
            fallback_raw = self._request(
                fallback_query, self.settings.web_search_fallback_timeout_seconds
            )
            if fallback_raw is None:
                continue
            provider_returned_results = provider_returned_results or bool(fallback_raw)
            parsed = self._parse_safe_results(
                fallback_raw, start_rank=1, limit=candidate_limit
            )
            if parsed:
                safe_results_seen = True
            unique_candidates = [item for item in parsed if item.url not in seen_urls]
            seen_urls.update(item.url for item in parsed)
            relevant = self._relevant_and_enriched(
                query, unique_candidates, max_fetch=max(3, requested_limit)
            )
            if relevant:
                fallback_batches.append(relevant)

        # Keep the final source set both topically relevant and diverse by domain.
        selected_urls = {item.url for item in results}
        for batch in fallback_batches:
            if len(results) >= requested_limit:
                break
            candidate = next(
                (item for item in batch if item.url not in selected_urls), None
            )
            if candidate is not None:
                results.append(candidate)
                selected_urls.add(candidate.url)

        if len(results) < requested_limit:
            for batch in fallback_batches:
                for candidate in batch:
                    if len(results) >= requested_limit:
                        break
                    if candidate.url not in selected_urls:
                        results.append(candidate)
                        selected_urls.add(candidate.url)

        if results:
            return WebSearchResponse("success", results[:requested_limit])
        if safe_results_seen:
            return WebSearchResponse("no_relevant_results", [])
        if provider_returned_results:
            return WebSearchResponse("no_safe_results", [])
        return WebSearchResponse("no_provider_results", [])


# Keep a stable service name for future provider swaps.
WebSearchClient = SearXNGWebSearchClient
