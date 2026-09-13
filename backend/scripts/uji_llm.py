"""Uji satu penyedia model bahasa: kuncinya sah, modelnya apa saja, jalan atau tidak.

KENAPA BERKAS INI ADA
----------------------
Menambahkan penyedia ke `LLM_FALLBACKS` tanpa mengujinya lebih dulu berarti
kegagalannya baru ketahuan saat ekstraksi sedang berjalan, dan pada saat itu
yang terlihat cuma "rantai penyedia habis" tanpa petunjuk penyedia mana yang
sebenarnya bermasalah.

Berkas ini memisahkan tiga pertanyaan yang sering tercampur:

1. Apakah kuncinya diterima sama sekali?
2. Nama model apa yang benar-benar tersedia di akun itu?
3. Apakah model itu mau menjawab, atau ditolak karena tagihan belum aktif?

Ketiganya perlu dipisah karena gejalanya mirip. Pada 13 Sep, kunci Cerebras
DITERIMA dan daftar modelnya keluar, tetapi setiap permintaan jawaban dibalas
402: alokasi gratisnya belum aktif. Kalau ketiga pertanyaan itu diuji sekaligus,
kesimpulannya akan keliru jadi "kuncinya salah".

Pakai:
    python -m scripts.uji_llm --base-url https://api.cerebras.ai/v1 --kunci csk-...
    python -m scripts.uji_llm --base-url https://api.mistral.ai/v1 --kunci ... --model mistral-small-latest
    python -m scripts.uji_llm --dari-env      # uji seluruh rantai yang sedang terpasang
"""

from __future__ import annotations

import argparse
import sys

from openai import OpenAI


def uji(nama: str, base_url: str, kunci: str, model: str | None) -> bool:
    print(f"\n=== {nama}")
    print(f"    {base_url}")

    klien = OpenAI(api_key=kunci, base_url=base_url, timeout=60.0)

    tersedia: list[str] = []
    try:
        tersedia = [m.id for m in klien.models.list().data]
        print(f"    kunci diterima. {len(tersedia)} model tersedia.")
        for m in tersedia[:15]:
            print(f"      - {m}")
    except Exception as exc:  # noqa: BLE001 - pesan penyedia beragam bentuknya
        # Sebagian penyedia tidak membuka daftar model sama sekali. Itu bukan
        # kegagalan; yang menentukan tetap uji jawaban di bawah.
        print(f"    daftar model tidak bisa dibaca: {type(exc).__name__}")

    kandidat = [model] if model else (tersedia[:1] or [None])
    if kandidat == [None]:
        print("    ! tidak ada model yang bisa dicoba. Sebutkan lewat --model.")
        return False

    for m in kandidat:
        try:
            balasan = klien.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Balas satu kata saja: SIAP"}],
                max_tokens=16,
            )
            isi = (balasan.choices[0].message.content or "").strip()
            print(f"    BISA DIPAKAI. model={m} balasan={isi[:40]!r}")
            print(f"    entri untuk LLM_FALLBACKS:\n      {nama}|{base_url}|{m}|<kunci>")
            return True
        except Exception as exc:  # noqa: BLE001
            pesan = str(exc)
            petunjuk = ""
            if "402" in pesan or "payment" in pesan.lower():
                petunjuk = " -> alokasi gratis belum aktif, buka tab billing penyedia"
            elif "401" in pesan or "invalid" in pesan.lower():
                petunjuk = " -> kunci ditolak, periksa salinannya"
            elif "404" in pesan:
                petunjuk = " -> nama model tidak dikenal di akun ini"
            print(f"    GAGAL. model={m}: {pesan[:140]}{petunjuk}")

    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url")
    p.add_argument("--kunci")
    p.add_argument("--model", default=None)
    p.add_argument("--nama", default="uji")
    p.add_argument(
        "--dari-env",
        action="store_true",
        help="uji seluruh penyedia yang sudah terpasang di LLM_FALLBACKS",
    )
    args = p.parse_args()

    if args.dari_env:
        from app.services.llm_penyedia import daftar_penyedia

        rantai = daftar_penyedia()
        if not rantai:
            print("! tidak ada penyedia terpasang.")
            return 1
        hasil = [uji(pen.nama, pen.base_url, pen.api_key or "", pen.model) for pen in rantai]
        print(f"\n{sum(hasil)} dari {len(hasil)} penyedia siap dipakai.")
        return 0 if any(hasil) else 1

    if not args.base_url or not args.kunci:
        print("! sebutkan --base-url dan --kunci, atau pakai --dari-env.")
        return 2

    return 0 if uji(args.nama, args.base_url, args.kunci, args.model) else 1


if __name__ == "__main__":
    sys.exit(main())
