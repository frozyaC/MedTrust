from types import SimpleNamespace

from app.services.safety import is_safe_domain
from app.services.web_search import (
    SearXNGWebSearchClient,
    WebSearchResult,
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
                text="<html><body>Source page</body></html>",
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
                text="<html><body>Source page</body></html>",
            )
        query = kwargs["params"]["q"]
        calls.append(query)
        if query.startswith("site:nice.org.uk"):
            payload = {
                "results": [
                    {
                        "title": "Diagnosis | Migraine - CKS - NICE",
                        "url": "https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
                        "content": "Clinical assessment is essential.",
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
        "site:nice.org.uk Какие современные рекомендации по диагностике мигрени у взрослых?",
        "site:pubmed.ncbi.nlm.nih.gov Какие современные рекомендации по диагностике мигрени у взрослых?",
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
                text="<html><body>Source page</body></html>",
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
                            "content": "NICE migraine diagnosis guidance.",
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
        "site:nice.org.uk мигрень диагностика",
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
                text="<html><body>Source page</body></html>",
            )
        query = kwargs["params"]["q"]
        if query == "мигрень":
            payload = {"results": []}
        elif query.startswith("site:nice.org.uk"):
            payload = {"results": [
                {"title": "Migraine NICE 1", "url": "https://cks.nice.org.uk/a", "content": "Migraine guidance"},
                {"title": "Migraine NICE 2", "url": "https://cks.nice.org.uk/b", "content": "Migraine guidance"},
            ]}
        elif query.startswith("site:pubmed.ncbi.nlm.nih.gov"):
            payload = {"results": [
                {"title": "Migraine PubMed 1", "url": "https://pubmed.ncbi.nlm.nih.gov/1", "content": "Migraine study"},
                {"title": "Migraine PubMed 2", "url": "https://pubmed.ncbi.nlm.nih.gov/2", "content": "Migraine study"},
            ]}
        else:
            payload = {"results": [
                {"title": "Migraine WHO 1", "url": "https://www.who.int/1", "content": "Migraine health report"},
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
        "site:nice.org.uk Какие современные рекомендации по диагностике мигрени у взрослых?",
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
