"""Pydantic request/response shapes for the TMA API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    system_prompt_override: Optional[str] = None


class SetModelRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)


class ConnectKeyRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)


class ProfilePatch(BaseModel):
    language: Optional[str] = Field(default=None, max_length=8)
    persona: Optional[str] = Field(default=None, max_length=4000)
    gender: Optional[str] = Field(default=None, max_length=32)
    age: Optional[int] = Field(default=None, ge=0, le=150)
    location: Optional[str] = Field(default=None, max_length=200)
    occupation: Optional[str] = Field(default=None, max_length=200)
    interests: Optional[list[str]] = None
    timezone: Optional[str] = Field(default=None, max_length=64)


class ProviderLiteral:
    OPENROUTER = "openrouter"
    SERPER = "serper"


class ConnectedProvider(BaseModel):
    provider: str
    created_at: str
