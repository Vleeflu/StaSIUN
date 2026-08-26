# app/services/gemini_service.py
from openai import APIError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.schemas.chat import Message

# Riwayat dipotong supaya percakapan panjang tidak terus membengkak. Konteks
# proyek dan daftar stasiun selalu ikut, jadi yang dibuang cuma basa-basi lama.
MAX_HISTORY = 12


class GeminiService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self._model = settings.GEMINI_MODEL

    def _ensure_client(self) -> AsyncOpenAI:
        """Client dibuat saat pertama dipakai, bukan saat modul diimpor.

        Kalau dibuat di awal, backend gagal start hanya karena GEMINI_API_KEY
        belum diisi, padahal peta dan API stasiun sebenarnya tidak butuh itu.
        """
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise RuntimeError(
                    "GEMINI_API_KEY belum diisi di backend/.env, jadi fitur chat "
                    "belum bisa dipakai."
                )

            self._client = AsyncOpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
            )

        return self._client

    async def chat(
        self,
        message: str,
        history: list[Message],
        context: str | None = None,
    ) -> str:
        client = self._ensure_client()

        messages: list[dict] = []

        if context:
            messages.append({"role": "system", "content": context})

        messages.extend(
            {"role": m.role.value, "content": m.content}
            for m in history[-MAX_HISTORY:]
        )
        messages.append({"role": "user", "content": message})

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except RateLimitError as e:
            raise RuntimeError("Kuota Gemini sedang habis, coba lagi sebentar.") from e
        except APIError as e:
            raise RuntimeError(f"Gemini API error: {e}") from e

        reply = response.choices[0].message.content

        if not reply:
            raise RuntimeError("Gemini tidak mengembalikan jawaban.")

        return reply


gemini_service = GeminiService()
