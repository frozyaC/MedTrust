from types import SimpleNamespace

from app.services.safety import is_safe_domain
from app.services.web_search import (
    SearXNGWebSearchClient,
    WebSearchResult,
    _fallback_search_terms,
    is_relevant_web_result,
)


def test_safe_domain_requires_https_and_allowlist():
    allowed = {"pubmed.ncbi.nlm.nih.gov", "who.int"}
    assert is_safe_domain("https://pubmed.ncbi.nlm.nih.gov/article", allowed)
    assert is_safe_domain("https://www.who.int/", allowed)
    assert not is_safe_domain("http://www.who.int/", allowed)
    assert not is_safe_domain("https://who.int.example.com/", allowed)


def test_searxng_search_parses_and_filters_results(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 4
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov"
        web_safe_domains = "pubmed.ncbi.nlm.nih.gov,who.int,nice.org.uk"

    payload = {
        "results": [
            {
                "title": "Migraine diagnosis - PubMed",
                "url": "https://pubmed.ncbi.nlm.nih.gov/123",
                "content": "Medical snippet about migraine diagnosis",
            },
            {
                "title": "Unsafe result",
                "url": "https://example.com/article",
                "content": "Should be filtered",
            },
            {
                "title": "Migraine diagnosis overview - WHO",
                "url": "https://www.who.int/news/item",
                "content": "WHO diagnostic overview about migraine",
            },
        ]
    }

    def fake_get(url, **kwargs):
        if url != "http://127.0.0.1:8080/search":
            return SimpleNamespace(
                raise_for_status=lambda: None,
                headers={"content-type": "text/html"},
                text=(
                    "<html><body><main>Migraine diagnosis recommendations for adults include assessment "
                    "of headache characteristics, duration and associated symptoms. Consider the clinical "
                    "context and further assessment when relevant.</main></body></html>"
                ),
            )
        assert kwargs["params"]["format"] == "json"
        assert kwargs["params"]["language"] == "ru"
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: payload,
        )

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search("диагностика мигрени", limit=2)
    assert result.status == "success"
    assert [item.domain for item in result.results] == [
        "pubmed.ncbi.nlm.nih.gov",
        "www.who.int",
    ]


def test_searxng_uses_authority_domain_fallback(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 2
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov"
        web_safe_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov"

    calls: list[str] = []

    def fake_get(url, **kwargs):
        if "params" not in kwargs:
            return SimpleNamespace(
                raise_for_status=lambda: None,
                headers={"content-type": "text/html"},
                text=("<html><body><main>Migraine recommendations and diagnosis in adults include assessing headache "
                      "characteristics, duration, associated symptoms, and need for further investigation.</main></body></html>"),
            )
        query = kwargs["params"]["q"]
        calls.append(query)
        if query.startswith("site:nice.org.uk"):
            payload = {
                "results": [
                    {
                        "title": "Diagnosis | Migraine - CKS - NICE",
                        "url": "https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
                        "content": (
                            "For migraine diagnosis in adults, assess headache characteristics, associated "
                            "symptoms and duration before considering further investigation."
                        ),
                    }
                ]
            }
        elif query.startswith("site:pubmed.ncbi.nlm.nih.gov"):
            payload = {
                "results": [
                    {
                        "title": "Migraine diagnosis in adults - PubMed",
                        "url": "https://pubmed.ncbi.nlm.nih.gov/42322310/",
                        "content": "Updated differential diagnosis review.",
                    }
                ]
            }
        else:
            payload = {
                "results": [
                    {
                        "title": "Wikipedia",
                        "url": "https://ru.wikipedia.org/wiki/%D0%9C%D0%B8%D0%B3%D1%80%D0%B5%D0%BD%D1%8C",
                        "content": "Unsafe generic result.",
                    }
                ]
            }
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        limit=3,
    )

    assert result.status == "success"
    assert len(result.results) == 2
    assert result.results[0].domain == "cks.nice.org.uk"
    assert result.results[1].domain == "pubmed.ncbi.nlm.nih.gov"
    assert calls == [
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        "site:nice.org.uk migraine diagnosis guidelines adults",
        "site:pubmed.ncbi.nlm.nih.gov migraine diagnosis guidelines adults",
    ]


def test_searxng_uses_domain_fallback_when_generic_search_has_no_results(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    calls: list[str] = []

    def fake_get(url, **kwargs):
        if "params" not in kwargs:
            return SimpleNamespace(
                raise_for_status=lambda: None,
                headers={"content-type": "text/html"},
                text=("<html><body><main>Migraine recommendations and diagnosis in adults include assessing headache "
                      "characteristics, duration, associated symptoms, and need for further investigation.</main></body></html>"),
            )
        query = kwargs["params"]["q"]
        calls.append(query)
        if query.startswith("site:nice.org.uk"):
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "results": [
                        {
                            "title": "Migraine - CKS - NICE",
                            "url": "https://cks.nice.org.uk/topics/migraine/",
                            "content": (
                                "NICE guidance on migraine diagnosis: assess headache characteristics, "
                                "duration and associated symptoms in adults."
                            ),
                        }
                    ]
                },
            )
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": []})

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search("мигрень диагностика", limit=3)

    assert result.status == "success"
    assert len(result.results) == 1
    assert result.results[0].domain == "cks.nice.org.uk"
    assert calls == [
        "мигрень диагностика",
        "site:nice.org.uk migraine diagnosis",
    ]


def test_searxng_fallback_diversifies_authoritative_domains(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 3
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov,who.int"
        web_safe_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov,who.int"

    def fake_get(url, **kwargs):
        if "params" not in kwargs:
            return SimpleNamespace(
                raise_for_status=lambda: None,
                headers={"content-type": "text/html"},
                text=("<html><body><main>Migraine recommendations and diagnosis in adults include assessing headache "
                      "characteristics, duration, associated symptoms, and need for further investigation.</main></body></html>"),
            )
        query = kwargs["params"]["q"]
        if query == "мигрень":
            payload = {"results": []}
        elif query.startswith("site:nice.org.uk"):
            payload = {"results": [
                {"title": "Migraine NICE 1", "url": "https://cks.nice.org.uk/a", "content": "Migraine guidance for adults: assess headache duration, associated symptoms and clinical warning signs in diagnosis."},
                {"title": "Migraine NICE 2", "url": "https://cks.nice.org.uk/b", "content": "Migraine guidance for adults: assess headache duration, associated symptoms and clinical warning signs in diagnosis."},
            ]}
        elif query.startswith("site:pubmed.ncbi.nlm.nih.gov"):
            payload = {"results": [
                {"title": "Migraine PubMed 1", "url": "https://pubmed.ncbi.nlm.nih.gov/1", "content": "Study of migraine symptoms and headache duration in adult patients, including clinical diagnosis and assessment."},
                {"title": "Migraine PubMed 2", "url": "https://pubmed.ncbi.nlm.nih.gov/2", "content": "Study of migraine symptoms and headache duration in adult patients, including clinical diagnosis and assessment."},
            ]}
        else:
            payload = {"results": [
                {"title": "Migraine WHO 1", "url": "https://www.who.int/1", "content": "Migraine health report for adults discussing symptoms, duration, diagnosis and clinical assessment."},
            ]}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search("мигрень", limit=3)

    assert [item.domain for item in result.results] == [
        "cks.nice.org.uk",
        "pubmed.ncbi.nlm.nih.gov",
        "www.who.int",
    ]


def test_searxng_disabled(monkeypatch):
    class Settings:
        web_search_enabled = False
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 4
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk,pubmed.ncbi.nlm.nih.gov"
        web_safe_domains = "pubmed.ncbi.nlm.nih.gov"

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    result = SearXNGWebSearchClient().search("диагностика мигрени")
    assert result.status == "disabled"
    assert result.results == []




def test_searxng_enriches_safe_results_with_page_text(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"
        web_source_max_chars = 6000

    class Response:
        def __init__(self, payload=None, html=None, content_type="application/json"):
            self._payload = payload
            self.text = html or ""
            self.headers = {"content-type": content_type}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if url == "http://127.0.0.1:8080/search":
            return Response({"results": [{
                "title": "NICE migraine diagnosis",
                "url": "https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
                "content": "Short search snippet.",
            }]})
        return Response(
            html="<html><head><script>ignore()</script></head>"
                 "<body><h1>Migraine diagnosis</h1><p>Clinical assessment is essential.</p></body></html>",
            content_type="text/html",
        )

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search("мигрень диагностика", limit=1)

    assert result.status == "success"
    assert "Clinical assessment is essential." in result.results[0].snippet
    assert "Search result snippet: Short search snippet." in result.results[0].snippet


def test_relevance_filter_rejects_safe_but_off_topic_nice_document():
    query = "Какие современные рекомендации по диагностике мигрени у взрослых?"
    irrelevant = WebSearchResult(
        title="Myalgic encephalomyelitis / chronic fatigue syndrome - NICE",
        url=(
            "https://www.nice.org.uk/guidance/ng206/resources/"
            "myalgic-encephalomyelitis-chronic-fatigue-syndrome-pdf"
        ),
        snippet=(
            "Recommendations on diagnosis, assessment and care planning for ME/CFS; "
            "these recommendations were developed based on reviewed evidence."
        ),
        rank=1,
        domain="www.nice.org.uk",
    )
    relevant = WebSearchResult(
        title="Migraine: diagnosis - NICE CKS",
        url="https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
        snippet="Clinical assessment and diagnosis of migraine in adults.",
        rank=2,
        domain="cks.nice.org.uk",
    )

    assert is_relevant_web_result(query, relevant)
    assert not is_relevant_web_result(query, irrelevant)


def test_searxng_returns_no_relevant_results_for_mismatched_medical_topic(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    calls: list[str] = []
    bad_result = {
        "title": "Myalgic encephalomyelitis / chronic fatigue syndrome - NICE",
        "url": (
            "https://www.nice.org.uk/guidance/ng206/resources/"
            "myalgic-encephalomyelitis-chronic-fatigue-syndrome-pdf"
        ),
        "content": "Recommendations on diagnosis and management of ME/CFS.",
    }

    def fake_get(url, **kwargs):
        query = kwargs["params"]["q"]
        calls.append(query)
        if query.startswith("site:nice.org.uk"):
            payload = {"results": [bad_result]}
        else:
            payload = {"results": [bad_result]}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        limit=3,
    )

    assert result.status == "no_relevant_results"
    assert result.results == []
    assert calls == [
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        "site:nice.org.uk migraine diagnosis guidelines adults",
    ]


def test_search_does_not_need_full_page_fetch_for_obviously_unrelated_result(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    calls: list[str] = []
    bad_result = {
        "title": "ME/CFS diagnosis and management - NICE",
        "url": "https://www.nice.org.uk/guidance/ng206",
        "content": "Diagnosis and management of chronic fatigue syndrome.",
    }

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"]["q"])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"results": [bad_result]})

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    response = SearXNGWebSearchClient().search("мигрень диагностика", limit=3)
    assert response.status == "no_relevant_results"
    assert response.results == []
    assert len(calls) == 2


def test_relevance_filter_checks_requested_type_of_information():
    query = "Какие современные рекомендации по диагностике мигрени у взрослых?"
    general_migraine_page = WebSearchResult(
        title="Migraine triggers and lifestyle - NICE",
        url="https://www.nice.org.uk/topics/migraine/lifestyle",
        snippet="Migraine triggers, sleep patterns and lifestyle adjustments.",
        rank=1,
        domain="www.nice.org.uk",
    )
    diagnosis_page = WebSearchResult(
        title="Migraine diagnosis - NICE CKS",
        url="https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
        snippet="Recommendations and clinical diagnosis of migraine in adults.",
        rank=2,
        domain="cks.nice.org.uk",
    )

    assert not is_relevant_web_result(query, general_migraine_page)
    assert is_relevant_web_result(query, diagnosis_page)


def test_search_finds_relevant_page_beyond_first_three_off_topic_candidates(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    good_url = "https://cks.nice.org.uk/topics/headache/diagnosis/"
    bad_results = [
        {
            "title": "ME/CFS diagnosis and management - NICE",
            "url": f"https://www.nice.org.uk/guidance/ng206?page={idx}",
            "content": "Diagnosis and management of chronic fatigue syndrome.",
        }
        for idx in range(1, 4)
    ]
    payload = {"results": bad_results + [{
        "title": "Adult headache disorders: assessment - NICE CKS",
        "url": good_url,
        "content": "Assessment of headache disorders in adults.",
    }]}
    page_fetches: list[str] = []

    class Response:
        def __init__(self, payload=None, html="", content_type="application/json"):
            self._payload = payload
            self.text = html
            self.headers = {"content-type": content_type}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if url == "http://127.0.0.1:8080/search":
            return Response(payload=payload)
        page_fetches.append(url)
        return Response(
            html=(
                "<html><body><h1>Headache diagnosis</h1>"
                "<p>Clinical recommendations for diagnosis of migraine in adults.</p>"
                "</body></html>"
            ),
            content_type="text/html",
        )

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", limit=1
    )

    assert result.status == "success"
    assert len(result.results) == 1
    assert result.results[0].url == good_url
    assert page_fetches == [good_url]


def test_search_fetches_ambiguous_headache_page_before_final_relevance_decision(monkeypatch):
    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    page_url = "https://cks.nice.org.uk/topics/headache/assessment/"

    class Response:
        def __init__(self, payload=None, html="", content_type="application/json"):
            self._payload = payload
            self.text = html
            self.headers = {"content-type": content_type}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if url == "http://127.0.0.1:8080/search":
            return Response(payload={"results": [{
                "title": "Headache disorders: assessment in adults",
                "url": page_url,
                "content": "Guidance for assessing headache disorders.",
            }]})
        return Response(
            html=(
                "<html><body><h1>Diagnosis and assessment</h1>"
                "<p>For adults with migraine, diagnosis is based on clinical features.</p>"
                "<p>Recommendations for migraine assessment.</p></body></html>"
            ),
            content_type="text/html",
        )

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", limit=1
    )

    assert result.status == "success"
    assert result.results[0].url == page_url
    assert "diagnosis and assessment" in result.results[0].snippet.lower()


def test_fallback_query_terms_are_language_aware_by_domain():
    query = "Какие современные рекомендации по диагностике мигрени у взрослых?"
    assert _fallback_search_terms(query, "nice.org.uk") == "migraine diagnosis guidelines adults"
    assert _fallback_search_terms(query, "cr.minzdrav.gov.ru") == query


def test_nice_guideline_overview_is_resolved_to_recommendations_and_main_text(monkeypatch):
    """A NICE landing page should not be used as evidence when its recommendation chapter exists."""

    class Settings:
        web_search_enabled = True
        searxng_url = "http://127.0.0.1:8080"
        web_search_language = "ru"
        web_search_timeout_seconds = 15
        web_search_fallback_timeout_seconds = 8
        web_fallback_max_domains = 1
        # Simulates an existing .env file with the old limit.
        web_source_max_chars = 6000
        web_fallback_domains = "nice.org.uk"
        web_safe_domains = "nice.org.uk"

    overview_url = "https://www.nice.org.uk/Guidance/CG150"
    recommendations_url = "https://www.nice.org.uk/guidance/cg150/chapter/recommendations"
    page_fetches: list[str] = []

    class Response:
        def __init__(self, payload=None, html="", content_type="application/json"):
            self._payload = payload
            self.text = html
            self.headers = {"content-type": content_type}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        if url == "http://127.0.0.1:8080/search":
            return Response(payload={"results": [{
                "title": "Headaches in over 12s: diagnosis and management - NICE",
                "url": overview_url,
                "content": "Overview of headache diagnosis and management in young people and adults.",
            }]})
        page_fetches.append(url)
        assert url == recommendations_url
        # The page chrome contains no criteria; only the main-content region is
        # evidence-bearing and must be passed to RAG for content review.
        return Response(
            html=(
                "<html><body><nav>COOKIE NOTICE AND SITE NAVIGATION</nav>"
                "<div class='sidebar'>Generic guideline overview only.</div>"
                "<main id='main-content'><h1>Recommendations</h1>"
                "<h2>Diagnosis of migraine</h2>"
                "<p>For adults, a migraine headache typically lasts from 4 to 72 hours.</p>"
                "<p>Consider using a headache diary for at least 8 weeks.</p>"
                "<p>Migraine with aura may occur with or without headache.</p>"
                "</main><footer>Cookie policy and site information</footer></body></html>"
            ),
            content_type="text/html",
        )

    monkeypatch.setattr("app.services.web_search.get_settings", lambda: Settings())
    monkeypatch.setattr("app.services.web_search.requests.get", fake_get)

    result = SearXNGWebSearchClient().search(
        "Какие современные рекомендации по диагностике мигрени у взрослых?", limit=1
    )

    assert result.status == "success"
    assert len(result.results) == 1
    assert result.results[0].url == recommendations_url
    assert page_fetches == [recommendations_url]
    text = result.results[0].snippet.casefold()
    assert "diagnosis of migraine" in text
    assert "4 to 72 hours" in text
    assert "headache diary" in text
    assert "without headache" in text
    assert "cookie notice and site navigation" not in text
    assert "cookie policy and site information" not in text
    assert len(result.results[0].snippet) <= 14000


def test_answerable_web_evidence_requires_body_content_not_only_title():
    from app.services.web_search import has_answerable_web_evidence

    query = "Какие современные рекомендации по диагностике мигрени у взрослых?"
    title_only = WebSearchResult(
        title="Migraine diagnosis and recommendations - NICE",
        url="https://www.nice.org.uk/guidance/migraine",
        snippet=(
            "NICE guideline overview. Information about our service, page navigation, related resources, "
            "publishing history, cookies and site policies."
        ),
        rank=1,
        domain="www.nice.org.uk",
    )
    evidence_bearing = WebSearchResult(
        title="Headaches in over 12s: diagnosis and management - NICE",
        url="https://www.nice.org.uk/guidance/cg150/chapter/recommendations",
        snippet=(
            "Recommendations for the diagnosis of migraine in adults. Migraine headache lasts 4 to 72 hours. "
            "Consider a headache diary and assessment for headache warning signs."
        ),
        rank=2,
        domain="www.nice.org.uk",
    )

    assert not has_answerable_web_evidence(query, title_only)
    assert has_answerable_web_evidence(query, evidence_bearing)
