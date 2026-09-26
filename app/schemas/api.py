from typing import Literal
from pydantic import BaseModel, Field


class PatientContext(BaseModel):
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = None
    contraindications: list[str] = Field(default_factory=list)
    anamnesis: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    patient: PatientContext | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    patient: PatientContext | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class FeedbackRequest(BaseModel):
    query_id: str
    rating: Literal["positive", "negative"]
    comment: str | None = Field(default=None, max_length=4000)
