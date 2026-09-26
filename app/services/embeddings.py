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

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            result.extend(item.embedding for item in ordered)
        return result

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
