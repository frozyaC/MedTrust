import uuid
import json

from app.db.repository import KnowledgeRepository
from app.services.embeddings import EmbeddingClient
from app.services.gigachat import GigaChatClient


class RagService:
    def __init__(self) -> None:
        self.repository = KnowledgeRepository()
        self.embeddings = EmbeddingClient()
        self.gigachat = GigaChatClient()

    @staticmethod
    def _retrieval_query(question: str, patient: dict | None) -> str:
        parts = [question]
        if patient:
            if patient.get("age") is not None:
                parts.append(f"Возраст пациента: {patient['age']}")
            if patient.get("sex"):
                parts.append(f"Пол пациента: {patient['sex']}")
            if patient.get("contraindications"):
                parts.append("Противопоказания: " + ", ".join(patient["contraindications"]))
            if patient.get("anamnesis"):
                parts.append(f"Анамнез: {patient['anamnesis']}")
        return "\n".join(parts)

    def search(self, question: str, patient: dict | None, top_k: int) -> list[dict]:
        retrieval_query = self._retrieval_query(question, patient)
        query_vector = self.embeddings.embed_one(retrieval_query)
        return self.repository.hybrid_search(retrieval_query, query_vector, top_k)

    @staticmethod
    def _build_prompt(question: str, patient: dict | None, docs: list[dict]) -> str:
        source_blocks = []
        for idx, doc in enumerate(docs, start=1):
            source_blocks.append(
                f"[Источник {idx}]\n"
                f"Название: {doc['title']}\n"
                f"Путь: {doc['wiki_path']}\n"
                f"Раздел: {doc['section'] or 'Корень статьи'}\n"
                f"Фрагмент:\n{doc['content']}"
            )

        patient_text = json.dumps(patient, ensure_ascii=False) if patient else "не передан"
        return (
            f"Вопрос регистратора:\n{question}\n\n"
            f"Контекст пациента:\n{patient_text}\n\n"
            "Источники базы знаний:\n\n"
            + "\n\n".join(source_blocks)
            + "\n\nСформируй ответ только по источникам. "
              "Если данных недостаточно — так и скажи. "
              "Не интерпретируй медицинские данные сверх текста источников. "
              "Ссылайся на источники в формате [Источник N]."
        )

    def answer(self, question: str, patient: dict | None, top_k: int) -> dict:
        docs = self.search(question, patient, top_k)
        query_id = str(uuid.uuid4())

        if not docs:
            return {
                "query_id": query_id,
                "answer": "В базе знаний не найден подтверждающий источник.",
                "sources": [],
                "retrieval": [],
            }

        prompt = self._build_prompt(question, patient, docs)
        answer = self.gigachat.chat(prompt)

        sources = [
            {
                "source_number": idx,
                "chunk_id": str(doc["chunk_id"]),
                "document_id": str(doc["document_id"]),
                "title": doc["title"],
                "section": doc["section"],
                "path": doc["wiki_path"],
                "path_segments": doc["path_segments"],
                "url": doc["source_url"],
                "snippet": doc["content"][:700],
            }
            for idx, doc in enumerate(docs, start=1)
        ]

        return {
            "query_id": query_id,
            "answer": answer,
            "sources": sources,
            "retrieval": [
                {
                    "chunk_id": str(doc["chunk_id"]),
                    "title": doc["title"],
                    "path": doc["wiki_path"],
                    "section": doc["section"],
                    "rrf_score": float(doc["rrf_score"]),
                    "dense_similarity": float(doc["dense_similarity"]),
                    "dense_rank": doc["dense_rank"],
                    "lexical_rank": doc["lexical_rank"],
                    "path_rank": doc["path_rank"],
                }
                for doc in docs
            ],
        }
