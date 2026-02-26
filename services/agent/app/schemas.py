"""Request and response schemas for chat endpoints."""

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict] = Field(default_factory=list)
    debug: dict | None = None
