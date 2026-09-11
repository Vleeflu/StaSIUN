"""Ubah `activity_raw` yang sudah lolos gate menjadi titik dan skala keramaian.

Pakai:
    python -m scripts.parse_activity
    python -m scripts.parse_activity --menit 10
    python -m scripts.parse_activity --hanya-rating   # bangun ulang crowd_ratings saja

Menjalankan ulang aman: baris yang sudah punya titik dilewati.
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.services.activity_parse import bangun_ulang_rating, parse_semua


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--menit",
        type=int,
        default=15,
        choices=(5, 10, 15),
        help="cincin isochrone yang dipakai menautkan titik ke stasiun",
    )
    p.add_argument(
        "--hanya-rating",
        action="store_true",
        help="hapus dan isi ulang crowd_ratings dari activity_points yang ada; "
        "titik dan hasil ekstraksi LLM tidak disentuh",
    )
    args = p.parse_args()

    session = SessionLocal()
    try:
        if args.hanya_rating:
            hasil = bangun_ulang_rating(session)
        else:
            hasil = parse_semua(session, menit=args.menit)
    finally:
        session.close()

    print(f"{hasil.titik} titik Activity tersimpan")
    print(f"{hasil.berpola_narasumber} berpola penilaian narasumber (lapis 2)")
    print(f"{hasil.rating} skala keramaian terambil")

    if hasil.provenance:
        print("\nasal entri (untuk pelaporan saja, tidak dipakai bercabang):")
        for asal, jumlah in sorted(hasil.provenance.items(), key=lambda x: -x[1]):
            print(f"  {jumlah:5d}  {asal}")

    if hasil.terbuang:
        print("\nskala beratribusi yang TIDAK tersimpan, menurut sebabnya:")
        for sebab, jumlah in sorted(hasil.terbuang.items(), key=lambda x: -x[1]):
            print(f"  {jumlah:5d}  {sebab}")
        print(
            "Tidak dipaksakan masuk pagi/siang/sore: memilihkan rentang atau angka\n"
            "untuk narasumber sama saja mengarang."
        )

    if hasil.tanpa_stasiun:
        print(
            f"\n{hasil.tanpa_stasiun} titik tidak jatuh di isochrone stasiun mana pun.\n"
            "Tetap disimpan — titik di luar kawasan tangkapan masih berguna untuk\n"
            "korpus naratif lapis 1, cuma tidak menyumbang ke indikator per stasiun."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
