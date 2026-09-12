"""Hitung ulang kolom `category` pada tabel poi dari `osm_tags` yang tersimpan.

Dipakai setiap kali aturan penggolongan di app/services/osm.py berubah.

Inilah alasan `osm_tags` disimpan mentah sejak awal: mengubah aturan kategori
tidak menuntut penarikan ulang 19 ribu titik dari Overpass — cukup baca ulang
tag yang sudah ada di database. Satu keputusan penyimpanan kemarin menghemat
satu penarikan penuh hari ini.

    python -m scripts.reclassify_poi --dry-run   # lihat apa yang akan berubah
    python -m scripts.reclassify_poi             # jalankan
"""

import argparse
import sys
from collections import Counter

from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.models.reference import Poi
from app.services.osm import kategori


def main() -> int:
    parser = argparse.ArgumentParser(description="Hitung ulang kategori titik minat.")
    parser.add_argument("--dry-run", action="store_true", help="tampilkan perubahan, jangan simpan")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        baris = session.execute(select(Poi.id, Poi.category, Poi.osm_tags)).all()
        print(f"{len(baris)} titik minat diperiksa.\n")

        perubahan: list[tuple[int, str]] = []
        pindah = Counter()
        for r in baris:
            baru = kategori(r.osm_tags or {})
            if baru != r.category:
                perubahan.append((r.id, baru))
                pindah[(r.category, baru)] += 1

        if not perubahan:
            print("Tidak ada yang berubah. Aturan penggolongan sudah sesuai isi tabel.")
            return 0

        print(f"{len(perubahan)} titik berpindah kategori:\n")
        print(f"  {'dari':>18s} -> {'ke':<18s} {'jumlah':>7s}")
        for (lama, baru), n in pindah.most_common():
            print(f"  {lama:>18s} -> {baru:<18s} {n:7d}")

        sesudah = Counter()
        for r in baris:
            sesudah[kategori(r.osm_tags or {})] += 1
        print(f"\n  Sebaran sesudah:")
        for kat, n in sesudah.most_common():
            print(f"    {n:6d}  {kat}")

        if args.dry_run:
            print("\n--dry-run: database tidak disentuh.")
            return 0

        # Dikelompokkan menurut kategori tujuan supaya jumlah perintah UPDATE
        # sebanyak kategori, bukan sebanyak baris yang berubah.
        per_kategori: dict[str, list[int]] = {}
        for poi_id, baru in perubahan:
            per_kategori.setdefault(baru, []).append(poi_id)

        for baru, id_list in per_kategori.items():
            for i in range(0, len(id_list), 1000):
                session.execute(
                    update(Poi).where(Poi.id.in_(id_list[i : i + 1000])).values(category=baru)
                )
        session.commit()
        print(f"\n{len(perubahan)} baris diperbarui.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
