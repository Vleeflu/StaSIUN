"""Rantai penyedia model bahasa: habis kuota di satu penyedia, pindah ke berikutnya.

MASALAH YANG DIJAWAB
--------------------
Tier gratis Groq memberi 200 ribu token per hari untuk `openai/gpt-oss-120b`.
Itu habis setelah sekitar 200 narasi, dua hari berturut-turut, dan begitu habis
SELURUH fitur AI ikut mati - termasuk asisten yang akan dicoba juri. Menaikkan
tier berbayar bukan pilihan karena dananya memang tidak ada.

Jalan keluarnya bukan satu penyedia yang lebih besar, melainkan BEBERAPA
penyedia gratis yang dipakai bergantian. Semua penyedia di bawah ini berbicara
protokol yang sama (OpenAI-compatible), jadi yang berbeda hanya tiga nilai:
alamat, model, dan kunci.

CARA MENGATURNYA
----------------
`.env` di root:

    LLM_API_KEY=kunci_groq
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_MODEL=openai/gpt-oss-120b

    # Cadangan, dipisah titik koma. Bentuk tiap entri:
    #   nama|base_url|model|kunci
    LLM_FALLBACKS=gemini|https://generativelanguage.googleapis.com/v1beta/openai/|gemini-flash-lite-latest|KUNCI;cerebras|https://api.cerebras.ai/v1|llama-3.3-70b|KUNCI

Urutannya adalah urutan pemakaian. Penyedia pertama dipakai sampai kuota
HARIANNYA habis, baru pindah - bukan diacak - supaya hasil ekstraksi sedapat
mungkin berasal dari satu model yang sama, dan perpindahannya tercatat.

YANG TIDAK DILAKUKAN
--------------------
Tidak ada penggabungan hasil dari beberapa model dalam satu penarikan tanpa
penanda. Penyedia yang sedang dipakai dilaporkan di keluaran skrip, sehingga
kalau setengah data diekstrak model lain, itu terlihat - bukan tersembunyi.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from openai import APIError, AsyncOpenAI, OpenAI, RateLimitError

from app.core.config import settings

# Batas HARIAN (atau kuota habis sama sekali) - pindah penyedia.
PENANDA_HARIAN = re.compile(r"per\s+day|\bTPD\b|\bRPD\b|quota|exhausted", re.IGNORECASE)
# Batas per menit - tunggu sebentar, penyedia yang sama masih bisa dipakai.
TUNGGU = re.compile(r"try again in\s+(?:(\d+)m)?\s*([\d.]+)(ms|s)", re.IGNORECASE)

MAKS_COBA_PER_MENIT = 6
TUNGGU_BAWAAN_DETIK = 15.0


class SemuaPenyediaHabis(RuntimeError):
    """Seluruh penyedia dalam rantai kehabisan kuota harian."""


@dataclass(frozen=True)
class Penyedia:
    nama: str
    base_url: str
    model: str
    api_key: str


def _dari_fallbacks(teks: str | None) -> list[Penyedia]:
    hasil: list[Penyedia] = []
    for bagian in (teks or "").split(";"):
        bagian = bagian.strip()
        if not bagian:
            continue
        potong = [x.strip() for x in bagian.split("|")]
        if len(potong) != 4 or not all(potong):
            # Baris yang bentuknya salah DILEWATI dengan diam-diam? Tidak.
            # Ia dilewati, tetapi namanya ikut muncul di daftar sebagai catatan
            # supaya salah ketik di .env tidak menyamar sebagai "tidak ada
            # cadangan".
            hasil.append(Penyedia("(entri LLM_FALLBACKS salah bentuk)", "", "", ""))
            continue
        nama, base_url, model, kunci = potong
        hasil.append(Penyedia(nama, base_url, model, kunci))
    return [p for p in hasil if p.base_url]


def daftar_penyedia() -> list[Penyedia]:
    """Penyedia utama diikuti cadangannya, urut pemakaian."""
    utama: list[Penyedia] = []
    if settings.LLM_API_KEY:
        utama.append(
            Penyedia(
                nama="utama",
                base_url=settings.LLM_BASE_URL,
                model=settings.LLM_MODEL,
                api_key=settings.LLM_API_KEY,
            )
        )
    return utama + _dari_fallbacks(getattr(settings, "LLM_FALLBACKS", None))


def _lama_tunggu(pesan: str) -> float:
    m = TUNGGU.search(pesan)
    if not m:
        return TUNGGU_BAWAAN_DETIK
    menit = int(m.group(1) or 0)
    angka = float(m.group(2))
    detik = angka / 1000 if m.group(3).lower() == "ms" else angka
    return menit * 60 + detik + 1.0


class Rantai:
    """Pemanggil yang berpindah penyedia saat kuota harian habis.

    Dipakai dua tempat dengan jalur berbeda: ekstraksi (sinkron, ratusan
    panggilan) dan asisten (asinkron, satu panggilan per pertanyaan).
    """

    def __init__(self, penyedia: list[Penyedia] | None = None):
        self.penyedia = penyedia if penyedia is not None else daftar_penyedia()
        if not self.penyedia:
            raise RuntimeError(
                "Tidak ada penyedia model. Isi LLM_API_KEY di .env, dan kalau mau "
                "cadangan, isi LLM_FALLBACKS."
            )
        self.indeks = 0
        self._klien: dict[int, OpenAI] = {}
        self._klien_async: dict[int, AsyncOpenAI] = {}
        # Penyedia yang sudah dipakai dalam sesi ini, untuk dilaporkan.
        self.terpakai: list[str] = []

    @property
    def sekarang(self) -> Penyedia:
        return self.penyedia[self.indeks]

    def _catat(self) -> None:
        if not self.terpakai or self.terpakai[-1] != self.sekarang.nama:
            self.terpakai.append(self.sekarang.nama)

    def _pindah(self) -> None:
        if self.indeks + 1 >= len(self.penyedia):
            raise SemuaPenyediaHabis(
                f"seluruh {len(self.penyedia)} penyedia kehabisan kuota harian: "
                f"{', '.join(p.nama for p in self.penyedia)}"
            )
        self.indeks += 1

    def klien(self) -> OpenAI:
        if self.indeks not in self._klien:
            self._klien[self.indeks] = OpenAI(
                api_key=self.sekarang.api_key, base_url=self.sekarang.base_url
            )
        return self._klien[self.indeks]

    def klien_async(self) -> AsyncOpenAI:
        if self.indeks not in self._klien_async:
            self._klien_async[self.indeks] = AsyncOpenAI(
                api_key=self.sekarang.api_key, base_url=self.sekarang.base_url
            )
        return self._klien_async[self.indeks]

    def panggil(self, **kwargs):
        """Satu panggilan chat completion, sinkron.

        `model` diisi dari penyedia yang sedang dipakai - pemanggil tidak perlu
        tahu penyedia mana yang aktif.
        """
        while True:
            self._catat()
            for _ in range(MAKS_COBA_PER_MENIT):
                try:
                    return self.klien().chat.completions.create(
                        model=self.sekarang.model, **kwargs
                    )
                except RateLimitError as exc:
                    pesan = str(exc)
                    if PENANDA_HARIAN.search(pesan):
                        break  # kuota harian penyedia ini habis
                    time.sleep(_lama_tunggu(pesan))
                except APIError:
                    return None
            self._pindah()

    async def panggil_async(self, **kwargs):
        while True:
            self._catat()
            try:
                return await self.klien_async().chat.completions.create(
                    model=self.sekarang.model, **kwargs
                )
            except RateLimitError as exc:
                if not PENANDA_HARIAN.search(str(exc)):
                    raise
                self._pindah()
