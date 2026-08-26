# app/schemas/chat.py
from enum import Enum

from pydantic import BaseModel, Field


class Role(str, Enum):
    user = "user"
    assistant = "assistant"


class Message(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Message] = Field(default_factory=list)
    # Stasiun yang sedang dibuka di panel kanan, kalau ada. Dipakai supaya
    # pertanyaan seperti "lin apa saja di sini" punya rujukan yang jelas.
    station_id: int | None = None


class ChatResponse(BaseModel):
    reply: str
