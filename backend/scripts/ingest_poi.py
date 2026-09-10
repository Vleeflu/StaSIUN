"""Isi tabel poi dari OpenStreetMap lewat Overpass.

Titik pusat pencariannya adalah seluruh stasiun yang sudah ada di database,
jadi skrip ini wajib dijalankan setelah stasiun ter-seed.

Idempoten: menjalankan ulang tidak menghasilkan baris ganda, karena kunci
(osm_type, osm_id) dipakai untuk memperbarui baris yang sudah ada.

    python -m scripts.ingest_poi                # jalankan sungguhan
    python -m scripts.ingest_poi --dry-run      # tarik dan hitung saja
    python -m scripts.ingest_poi --radius 800   # ubah radius pencarian
"""

import argparse
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from geoalchemy2 import WKTElement
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.core.geo import SRID_RENDER
from app.models.reference import Poi
from app.models.station import Station
from app.services.osm import DEFAULT_RADIUS_M, OverpassError, build_query, element_to_poi, fetch

# Sepuluh stasiun per permintaan. Sekaligus 78 berisiko timeout di sisi
# Overpass; satu per satu berarti 78 permintaan dan berisiko kena pembatasan
# laju. Angka ini jalan tengahnya.
CHUNK = 10

# Jeda antar permintaan. Overpass layanan gratis bersama — memberi jeda itu
# etika pemakaian, sekaligus menurunkan peluang kena pembatasan laju.
# Dinaikkan dari 2 ke 5 detik setelah penarikan pertama kena 429 Too Many
# Requests di rombongan keenam.
JEDA_DETIK = 5.0


def ambil_pusat(session) -> list[tuple[int, str, float, float]]:
    """Koordinat seluruh stasiun, dibaca balik dari kolom geometri."""
    rows = session.execute(
        select(
            Station.id,
            Station.name,
            func.ST_Y(Station.location).label("lat"),
            func.ST_X(Station.location).label("lon"),
        ).order_by(Station.id)
    ).all()
    return [(r.id, r.name, r.lat, r.lon) for r in rows]


def simpan(session, baris: list[dict], waktu: datetime) -> None:
    """Upsert berdasarkan (osm_type, osm_id).

    ON CONFLICT DO UPDATE dipakai, bukan hapus-lalu-isi-ulang, supaya kolom
    created_at baris lama tetap utuh — itu jejak kapan sebuah titik minat
    pertama kali terlihat, dan hilang kalau barisnya dibuat ulang.
    """
    if not baris:
        return

    nilai = [
        {
            # Ditulis eksplisit, tidak diserahkan ke default kolom. Tabel poi
            # sekarang dipakai dua sumber, dan baris tanpa penanda sumber akan
            # ikut terjumlah di lajur yang salah tanpa memicu galat apa pun.
            "source": "overpass",
            "osm_type": b["osm_type"],
            "osm_id": b["osm_id"],
            "name": b["name"],
            "category": b["category"],
            "osm_tags": b["osm_tags"],
            "location": WKTElement(f"POINT({b['lon']} {b['lat']})", srid=SRID_RENDER),
            "fetched_at": waktu,
        }
        for b in baris
    ]

    stmt = insert(Poi).values(nilai)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_poi_osm",
        set_={
            "name": stmt.excluded.name,
            "category": stmt.excluded.category,
            "osm_tags": stmt.excluded.osm_tags,
            "location": stmt.excluded.location,
            "fetched_at": stmt.excluded.fetched_at,
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tarik titik minat OSM di sekitar stasiun.")
    parser.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M)
    parser.add_argument("--chunk", type=int, default=CHUNK)
    parser.add_argument("--dry-run", action="store_true", help="tarik dan hitung, jangan simpan")
    args = parser.parse_args()

    # Peringatan dari lapisan layanan (mis. Overpass berhasil setelah gagal
    # beberapa kali) harus sampai ke layar. Tanpa ini, penarikan yang
    # sebenarnya nyaris gagal akan terlihat mulus.
    logging.basicConfig(level=logging.WARNING, format="  [%(levelname)s] %(message)s")

    session = SessionLocal()
    try:
        stasiun = ambil_pusat(session)
        if not stasiun:
            print("Tabel stations kosong. Jalankan seed stasiun lebih dulu.")
            return 1

        print(f"{len(stasiun)} stasiun jadi titik pusat, radius {args.radius} m.")

        # Kunci dedup di sisi Python: satu titik minat bisa berada dalam
        # jangkauan dua stasiun sekaligus dan terambil dua kali. Tanpa ini,
        # satu perintah INSERT bisa memuat kunci yang sama dua kali dan
        # PostgreSQL menolak seluruh perintahnya.
        terkumpul: dict[tuple[str, int], dict] = {}
        gagal: list[str] = []

        for i in range(0, len(stasiun), args.chunk):
            bagian = stasiun[i : i + args.chunk]
            pusat = [(lat, lon) for _, _, lat, lon in bagian]
            label = f"{i + 1}-{i + len(bagian)}"

            try:
                mulai = time.time()
                elemen = fetch(build_query(pusat, radius_m=args.radius))
            except OverpassError as exc:
                print(f"  ! stasiun {label}: {exc}")
                gagal.append(label)
                continue

            baru = 0
            for el in elemen:
                row = element_to_poi(el)
                if row is None:
                    continue
                kunci = (row["osm_type"], row["osm_id"])
                if kunci not in terkumpul:
                    baru += 1
                terkumpul[kunci] = row

            print(
                f"  stasiun {label:>6s}: {len(elemen):5d} elemen, "
                f"{baru:5d} titik baru ({time.time() - mulai:.1f}s)"
            )

            if i + args.chunk < len(stasiun):
                time.sleep(JEDA_DETIK)

        if gagal:
            print(f"\n{len(gagal)} rombongan gagal ditarik: {', '.join(gagal)}")

        baris = list(terkumpul.values())
        if not baris:
            print("Tidak ada titik minat terambil. Database tidak diubah.")
            return 1

        print(f"\n{len(baris)} titik minat unik terkumpul.")
        sebaran = Counter(b["category"] for b in baris)
        for kat, n in sebaran.most_common():
            print(f"  {n:6d}  {kat}")
        bernama = sum(1 for b in baris if b["name"])
        print(f"  {bernama} bernama, {len(baris) - bernama} tanpa nama")

        if args.dry_run:
            print("\n--dry-run: database tidak disentuh.")
            return 0

        waktu = datetime.now(timezone.utc)
        # Dipotong-potong supaya satu perintah INSERT tidak membawa puluhan
        # ribu baris sekaligus, yang bisa menabrak batas parameter PostgreSQL.
        for i in range(0, len(baris), 500):
            simpan(session, baris[i : i + 500], waktu)
        session.commit()

        total = session.execute(select(func.count()).select_from(Poi)).scalar_one()
        print(f"\nTersimpan. Tabel poi sekarang berisi {total} baris.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
