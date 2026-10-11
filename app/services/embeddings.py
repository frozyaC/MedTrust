from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


class EmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.embedding_model
        self.batch_size = settings.embedding_batch_size
        self.client = OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
        self.last_usage: dict = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Avoid reporting token usage from a previous request if this response
        # does not include usage metadata.
        self.last_usage = {}
        result: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                if hasattr(usage, "model_dump"):
                    self.last_usage = usage.model_dump()
                elif isinstance(usage, dict):
                    self.last_usage = dict(usage)
                else:
                    self.last_usage = {
                        key: value for key in ("prompt_tokens", "total_tokens")
                        if (value := getattr(usage, key, None)) is not None
                    }
            ordered = sorted(response.data, key=lambda item: item.index)
            result.extend(item.embedding for item in ordered)
        return result

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
