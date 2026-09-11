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
    station_id: int | None = None


class Aksi(BaseModel):
    """Tombol yang menyertai jawaban asisten.

    Disusun backend dari alat yang benar-benar dipanggil (services/ai_actions.py),
    tidak pernah dari teks bebas model.
    """

    jenis: str  # buka_stasiun | bandingkan | simulasi
    label: str
    station_id: int | None = None
    station_ids: list[int] | None = None
    tab: str | None = None
    bobot: dict[str, float] | None = None


class ChatResponse(BaseModel):
    reply: str
    actions: list[Aksi] = Field(default_factory=list)
