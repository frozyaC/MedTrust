from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gigachat_auth_data: str
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2"
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_verify_ssl: bool = False
    gigachat_token_safety_seconds: int = 60

    embedding_api_key: str
    embedding_base_url: str = "https://foundation-models.api.cloud.ru/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024

    postgres_dsn: str = "postgresql://medtrust:medtrust@localhost:5433/medtrust"

    chunk_size_chars: int = 2200
    chunk_overlap_chars: int = 250
    embedding_batch_size: int = 32
    search_candidates: int = 20
    dense_rrf_weight: float = 1.0
    lexical_rrf_weight: float = 1.0
    path_rrf_weight: float = 1.25

    memory_recent_messages: int = 12
    memory_summary_trigger_messages: int = 12
    memory_follow_up_max_chars: int = 300

    web_search_enabled: bool = True
    searxng_url: str = "http://127.0.0.1:8080"
    web_search_timeout_seconds: int = 15
    web_search_fallback_timeout_seconds: int = 8
    web_search_language: str = "ru"
    web_fallback_max_domains: int = 4
    web_source_max_chars: int = 6000
    web_fallback_domains: str = (
        "nice.org.uk,pubmed.ncbi.nlm.nih.gov,cr.minzdrav.gov.ru,who.int"
    )
    web_min_wiki_dense_similarity: float = 0.62
    web_safe_domains: str = (
        "pubmed.ncbi.nlm.nih.gov,ncbi.nlm.nih.gov,nih.gov,who.int,cdc.gov,"
        "fda.gov,ema.europa.eu,nice.org.uk,nhs.uk,medlineplus.gov,"
        "mayoclinic.org,msdmanuals.com,minzdrav.gov.ru,cr.minzdrav.gov.ru,"
        "cochranelibrary.com,bmj.com,nejm.org,jamanetwork.com,theLancet.com"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
