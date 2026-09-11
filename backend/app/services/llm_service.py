"""Penghubung ke model bahasa untuk panel AI Insight.

Sengaja tidak terikat ke satu penyedia. Yang dipakai adalah SDK OpenAI, dan SDK
itu bisa diarahkan ke layanan mana pun yang menyediakan endpoint
OpenAI-compatible — Groq, Gemini, OpenAI sendiri, dan lainnya. Berpindah
penyedia karena itu cukup mengubah tiga nilai di .env (LLM_API_KEY,
LLM_BASE_URL, LLM_MODEL) tanpa menyentuh berkas ini.

Penyedia yang dipakai sekarang: Groq. Riwayat keputusannya di ADJUSTMENT.md
bagian 7.7.
"""

import json

from openai import APIError, AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.schemas.chat import Message

# Riwayat dipotong supaya percakapan panjang tidak terus membengkak. Konteks
# proyek dan daftar stasiun selalu ikut, jadi yang dibuang cuma basa-basi lama.
MAX_HISTORY = 12

# Batas putaran tool calling per pertanyaan. Dinaikkan dari 4 ke 6 setelah satu
# pertanyaan berantai menabraknya. Tapi batas itu BUKAN perbaikan sebenarnya:
# penyebabnya model memanggil peringkat_tenant lima kali berturut-turut, satu
# per kategori, karena belum ada alat yang menjawab seluruh kategori untuk satu
# stasiun. Alat itu ditambahkan (tenant_untuk_stasiun); angka ini cuma margin.
MAX_PUTARAN_ALAT = 6


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
        db=None,
    ) -> tuple[str, list[dict]]:
        """Jawab satu pertanyaan, dengan alat kalau `db` diberikan.

        Mengembalikan (jawaban, log alat). Log berisi alat yang benar-benar
        dipanggil beserta hasilnya, dipakai menyusun tombol aksi.

        Tanpa `db` ia bekerja seperti sebelumnya: tanya-jawab di atas konteks
        yang disuntikkan. Dengan `db`, model boleh memanggil alat di
        `ai_tools` untuk MENGHITUNG, bukan menebak.
        """
        client = self._ensure_client()

        messages: list[dict] = []

        if context:
            messages.append({"role": "system", "content": context})

        messages.extend(
            {"role": m.role.value, "content": m.content}
            for m in history[-MAX_HISTORY:]
        )
        messages.append({"role": "user", "content": message})

        if db is not None:
            return await self._chat_dengan_alat(client, messages, db)

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

        return reply, []

    async def _chat_dengan_alat(
        self, client, messages: list[dict], db
    ) -> tuple[str, list[dict]]:
        """Lingkaran tool calling: model memanggil alat, kita jalankan, ulangi.

        Batas putarannya KERAS. Model yang bingung bisa memanggil alat yang sama
        berulang-ulang tanpa pernah menjawab; tanpa batas, satu pertanyaan bisa
        menghabiskan kuota penyedia dan menggantung permintaan pengguna.

        Kalau batas tercapai, yang dikembalikan bukan jawaban karangan melainkan
        pengakuan bahwa pertanyaannya tidak terjawab - lebih berguna daripada
        kalimat meyakinkan yang tidak berdasar hitungan apa pun.
        """
        from app.services import ai_tools

        log: list[dict] = []
        for _ in range(MAX_PUTARAN_ALAT):
            try:
                response = await client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=ai_tools.TOOL_SCHEMAS,
                )
            except RateLimitError as e:
                raise RuntimeError(
                    "Kuota penyedia model sedang habis, coba lagi sebentar."
                ) from e
            except APIError as e:
                raise RuntimeError(
                    f"Panggilan ke model gagal (model={self._model}, "
                    f"base_url={settings.LLM_BASE_URL}): {e}"
                ) from e

            pesan = response.choices[0].message
            panggilan = getattr(pesan, "tool_calls", None)

            if not panggilan:
                if pesan.content:
                    return pesan.content, log
                raise RuntimeError("Model tidak mengembalikan jawaban.")

            # Pesan model WAJIB ikut disisipkan sebelum hasil alat, kalau tidak
            # tool_call_id-nya menggantung dan penyedia menolak permintaan
            # berikutnya.
            messages.append(
                {
                    "role": "assistant",
                    "content": pesan.content or "",
                    "tool_calls": [
                        {
                            "id": p.id,
                            "type": "function",
                            "function": {
                                "name": p.function.name,
                                "arguments": p.function.arguments,
                            },
                        }
                        for p in panggilan
                    ],
                }
            )

            for p in panggilan:
                try:
                    argumen = json.loads(p.function.arguments or "{}")
                except json.JSONDecodeError:
                    argumen = {}

                teks, hasil = ai_tools.jalankan_terekam(db, p.function.name, argumen)
                log.append({"alat": p.function.name, "argumen": argumen, "hasil": hasil})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": p.id,
                        "content": teks,
                    }
                )

        return (
            "Maaf, saya memanggil alat hitung berulang kali tanpa sampai ke "
            "jawaban. Coba persempit pertanyaannya — misalnya sebutkan nama "
            "stasiunnya, atau satu kategori usaha saja."
        ), log


llm_service = LLMService()
