# app/schemas/chat.py
from pydantic import BaseModel, Field
from enum import Enum

class Role(str, Enum):
    user = "user"
    assistant = "assistant"

class Message(BaseModel):
    role: Role
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = Field(default_factory=list)

class ChatResponse(BaseModel):
    reply: str