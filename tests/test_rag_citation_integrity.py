from types import SimpleNamespace

from app.services.rag import RagService
from app.services.web_search import WebSearchResult


def _doc() -> dict:
    return {
        "title": "Нерелевантная Wiki статья",
        "wiki_path": "Регистратура/Обзвон/example",
        "section": "Раздел",
        "path_segments": ["Регистратура", "Обзвон", "example"],
        "source_url": None,
        "content": "Список врачей.",
    }


def _web() -> WebSearchResult:
    return WebSearchResult(
        title="NICE migraine diagnosis",
        url="https://cks.nice.org.uk/topics/migraine/diagnosis/diagnosis/",
        snippet="Clinical assessment is essential in diagnosis of migraine.",
        rank=1,
        domain="cks.nice.org.uk",
    )


def test_build_prompt_excludes_wiki_citations_when_wiki_is_insufficient(monkeypatch):
    class Settings:
        memory_follow_up_max_chars = 300
        web_min_wiki_dense_similarity = 0.62

    monkeypatch.setattr("app.services.rag.get_settings", lambda: Settings())

    prompt = RagService._build_prompt(
        "Какие современные рекомендации по диагностике мигрени у взрослых?",
        None,
        [_doc()],
        [_web()],
        {"summary": "нет", "messages": []},
        wiki_sufficient=False,
    )

    assert "WEB1" in prompt
    assert "Нерелевантная Wiki статья" not in prompt
    assert "[W1]" not in prompt
    assert "[WEB1]" in prompt


def test_collect_sources_excludes_wiki_when_wiki_is_insufficient():
    sources = RagService._collect_sources([_doc()], [_web()], wiki_sufficient=False)

    assert [source["source_id"] for source in sources] == ["WEB1"]


def test_filter_used_sources_rejects_citation_not_in_prompt_sources():
    sources = RagService._collect_sources([], [_web()], wiki_sufficient=False)

    assert RagService._filter_used_sources("Ответ [W1].", sources) == []
    assert RagService._filter_used_sources("Ответ [WEB1].", sources)[0]["source_id"] == "WEB1"
