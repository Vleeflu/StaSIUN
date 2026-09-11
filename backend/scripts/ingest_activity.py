"""Tarik data Activity hasil survey lapangan dari Community MAPS GEO MAPID.

Pakai:
    python -m scripts.ingest_activity                    # rentang bawaan
    python -m scripts.ingest_activity --dry-run          # tarik dan hitung, jangan simpan
    python -m scripts.ingest_activity --hashtag StaSIUN  # saring dari deskripsi
    python -m scripts.ingest_activity --mulai 2026-08-01 --selesai 2026-09-05

Rentang tanggalnya SELALU dicetak sebelum menarik. Itu disengaja: API memotong
balasan di 60 baris kalau rentang tanggal tidak dikirim, tanpa penanda apa pun,
sehingga rentang yang salah menghasilkan data yang terlihat lengkap. Angka yang
dipakai harus selalu terlihat, bukan tersembunyi sebagai nilai bawaan.
"""

import argparse
import sys
from datetime import date, datetime

from app.core.database import SessionLocal
from app.services.activity import ActivityError, tarik_semua

# Periode survey lapangan tim, ditetapkan Villyan 11 Sep 2026.
MULAI_BAWAAN = date(2026, 8, 1)
SELESAI_BAWAAN = date(2026, 9, 5)


def _tanggal(teks: str) -> date:
    try:
        return datetime.strptime(teks, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"tanggal harus YYYY-MM-DD, dapat {teks!r}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mulai", type=_tanggal, default=MULAI_BAWAAN)
    p.add_argument("--selesai", type=_tanggal, default=SELESAI_BAWAAN)
    p.add_argument(
        "--menit",
        type=int,
        default=15,
        choices=(5, 10, 15),
        help="cincin isochrone yang dipakai sebagai gate spasial",
    )
    p.add_argument(
        "--hashtag",
        action="append",
        help="saring deskripsi (boleh diulang). Panduan Lapangan mewajibkan #NamaTim",
    )
    p.add_argument("--dry-run", action="store_true", help="tarik dan hitung, jangan simpan")
    args = p.parse_args()

    print(f"rentang tanggal : {args.mulai} sampai {args.selesai}")
    print(f"gate spasial    : cincin isochrone {args.menit} menit")
    print(f"hashtag         : {args.hashtag or '(tidak disaring)'}")
    print(f"mode            : {'dry-run, tidak disimpan' if args.dry_run else 'simpan'}")
    print()

    session = SessionLocal()
    try:
        hasil = tarik_semua(
            session,
            args.mulai,
            args.selesai,
            menit=args.menit,
            hashtag=args.hashtag,
            simpan=not args.dry_run,
        )
    except ActivityError as exc:
        print(f"! {exc}")
        return 1
    finally:
        session.close()

    print(f"{hasil.diminta} permintaan poligon, {hasil.diterima} Activity diterima")
    print(f"{hasil.tersimpan} tersimpan, {hasil.duplikat} duplikat dilewati")

    if hasil.ditolak:
        print("\nditolak gate:")
        for alasan, jumlah in sorted(hasil.ditolak.items(), key=lambda x: -x[1]):
            print(f"  {jumlah:5d}  {alasan}")

    if hasil.kena_batas_60:
        nama = ", ".join(sorted(set(hasil.kena_batas_60))[:5])
        print(
            f"\n!! {len(hasil.kena_batas_60)} poligon mengembalikan TEPAT 60 Activity "
            f"({nama}...).\n"
            "   60 adalah batas keras API. Walau rentang tanggal sudah dikirim, "
            "angka persis 60\n"
            "   patut dicurigai sebagai balasan terpotong, bukan jumlah sebenarnya. "
            "Persempit\n"
            "   rentang tanggalnya lalu tarik ulang untuk memastikan."
        )

    if hasil.diterima == 0:
        print(
            "\nTidak ada Activity sama sekali pada rentang ini. Yang perlu diperiksa,\n"
            "berurutan dari yang paling sering: rentang tanggalnya benar, survey memang\n"
            "sudah diunggah ke Community MAPS, dan stasiunnya punya poligon isochrone."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
