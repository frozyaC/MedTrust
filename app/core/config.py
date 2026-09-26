from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gigachat_auth_data: str
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2"
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_verify_ssl: bool = True
    gigachat_token_safety_seconds: int = 60

    embedding_api_key: str
    embedding_base_url: str = "https://foundation-models.api.cloud.ru/v1"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dimension: int = 1024

    postgres_dsn: str = "postgresql://medtrust:medtrust@localhost:5432/medtrust"

    chunk_size_chars: int = 2200
    chunk_overlap_chars: int = 250
    embedding_batch_size: int = 32
    search_candidates: int = 20

    dense_rrf_weight: float = 1.0
    lexical_rrf_weight: float = 1.0
    path_rrf_weight: float = 1.25


@lru_cache
def get_settings() -> Settings:
    return Settings()
