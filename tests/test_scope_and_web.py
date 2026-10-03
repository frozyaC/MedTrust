from app.services.safety import QueryScopeValidator, is_safe_domain


def test_medical_query_is_allowed():
    decision = QueryScopeValidator().validate("К кому записать пациента с травмой?")
    assert decision.allowed is True


def test_obvious_unrelated_query_is_blocked():
    decision = QueryScopeValidator().validate("Как написать Python-код для Docker?")
    assert decision.allowed is False


def test_safe_domain_requires_exact_or_subdomain_match():
    allowed = {"pubmed.ncbi.nlm.nih.gov"}
    assert is_safe_domain("https://pubmed.ncbi.nlm.nih.gov/", allowed)
    assert is_safe_domain("https://www.pubmed.ncbi.nlm.nih.gov/", allowed)
    assert not is_safe_domain("https://pubmed.ncbi.nlm.nih.gov.example.com/", allowed)


def test_web_search_example_query_is_allowed():
    decision = QueryScopeValidator().validate(
        "Какие современные рекомендации по диагностике мигрени у взрослых?"
    )
    assert decision.allowed is True
