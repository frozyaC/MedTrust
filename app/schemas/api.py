from typing import Literal
from uuid import UUID

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
    conversation_id: UUID | None = None


class ManualWebSearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=3000)
    limit: int = Field(default=5, ge=1, le=8)


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class GapStatusRequest(BaseModel):
    status: Literal["open", "in_review", "resolved", "dismissed"]
    note: str | None = Field(default=None, max_length=2000)
    author: str | None = Field(default=None, max_length=200)


class GapCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    author: str = Field(min_length=1, max_length=200)


class FeedbackRequest(BaseModel):
    query_id: str
    rating: Literal["positive", "negative"]
    comment: str | None = Field(default=None, max_length=4000)
    reason_code: str | None = Field(default=None, max_length=64)
    question: str | None = Field(default=None, max_length=4000)
    conversation_id: UUID | None = None
