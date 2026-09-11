"""Latih LDA atas korpus naratif Activity, lalu beri label arketipe tiap titik.

Pakai:
    python -m scripts.hitung_arketipe
    python -m scripts.hitung_arketipe --topik 6

Jalankan ulang akan MENGGANTI seluruh label lama, karena nomor topik tidak
bermakna antar-pelatihan: "topik_2" pada satu pelatihan tidak sama dengan
"topik_2" pada pelatihan berikutnya. Menyisakan label lama akan mencampur dua
sistem penomoran yang berbeda tanpa ada yang tahu.
"""

import argparse
import sys

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.nlp_arketipe import hitung_arketipe


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--topik",
        type=int,
        default=5,
        help="jumlah arketipe. Bawaan 5, dipilih konseptual — bukan ditala ke skor",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    session = SessionLocal()
    try:
        lama = session.execute(
            text("DELETE FROM activity_extractions RETURNING 1")
        ).rowcount
        if lama:
            print(f"{lama} label lama dihapus (penomoran topik tidak sebanding antar-pelatihan)\n")

        hasil = hitung_arketipe(session, jumlah_topik=args.topik, seed=args.seed)
    except RuntimeError as exc:
        print(f"! {exc}")
        return 1
    finally:
        session.close()

    print(f"{hasil.dokumen} dokumen, {hasil.topik} topik, {hasil.tersimpan} label tersimpan")
    print(f"perplexity {hasil.perplexity:.1f} — dilaporkan untuk diperiksa, BUKAN dasar pemilihan\n")

    print("kata kunci tiap topik:")
    for i, kata in sorted(hasil.kata_kunci.items()):
        print(f"  topik_{i}  {', '.join(kata)}")

    if hasil.per_stasiun:
        print("\narketipe dominan per stasiun (10 pertama):")
        for nama, arketipe in sorted(hasil.per_stasiun.items())[:10]:
            print(f"  {nama[:26]:26s} {arketipe}")
        print(f"  ... total {len(hasil.per_stasiun)} stasiun")

    print(
        "\nCatatan: topik sengaja TIDAK diberi nama seperti 'perkantoran'.\n"
        "Menamainya adalah tafsir manusia, dan menaruh tafsir itu di database\n"
        "membuatnya terlihat seperti temuan. Kata kuncinya di atas yang dibaca."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
