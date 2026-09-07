"""Penghubung ke model bahasa untuk panel AI Insight.

Sengaja tidak terikat ke satu penyedia. Yang dipakai adalah SDK OpenAI, dan SDK
itu bisa diarahkan ke layanan mana pun yang menyediakan endpoint
OpenAI-compatible — Groq, Gemini, OpenAI sendiri, dan lainnya. Berpindah
penyedia karena itu cukup mengubah tiga nilai di .env (LLM_API_KEY,
LLM_BASE_URL, LLM_MODEL) tanpa menyentuh berkas ini.

Penyedia yang dipakai sekarang: Groq. Riwayat keputusannya di ADJUSTMENT.md
bagian 7.7.
"""

from openai import APIError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.schemas.chat import Message

# Riwayat dipotong supaya percakapan panjang tidak terus membengkak. Konteks
# proyek dan daftar stasiun selalu ikut, jadi yang dibuang cuma basa-basi lama.
MAX_HISTORY = 12


class LLMService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self._model = settings.LLM_MODEL

    def _ensure_client(self) -> AsyncOpenAI:
        """Client dibuat saat pertama dipakai, bukan saat modul diimpor.

        Kalau dibuat di awal, backend gagal start hanya karena LLM_API_KEY
        belum diisi, padahal peta dan API stasiun sebenarnya tidak butuh itu.
        """
        if self._client is None:
            if not settings.LLM_API_KEY:
                raise RuntimeError(
                    "LLM_API_KEY belum diisi di backend/.env, jadi fitur chat "
                    "belum bisa dipakai."
                )

            self._client = AsyncOpenAI(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
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
            raise RuntimeError(
                "Kuota penyedia model sedang habis, coba lagi sebentar."
            ) from e
        except APIError as e:
            # Nama model dan alamat penyedianya ikut disebut karena dua
            # kesalahan paling sering di sini adalah id model yang keliru dan
            # kunci yang tidak cocok dengan alamatnya. Tanpa keduanya, pesan
            # errornya tidak menunjuk ke mana pun.
            raise RuntimeError(
                f"Panggilan ke model gagal (model={self._model}, "
                f"base_url={settings.LLM_BASE_URL}): {e}"
            ) from e

        reply = response.choices[0].message.content

        if not reply:
            raise RuntimeError("Model tidak mengembalikan jawaban.")

        return reply


llm_service = LLMService()
