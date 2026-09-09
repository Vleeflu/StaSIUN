"""Siapkan skema database.

Proyek ini belum pakai Alembic, jadi perubahan bentuk tabel diurus di sini.
Aman dijalankan berulang: tanpa argumen, cuma tabel yang belum ada yang dibuat.

Pakai:
    python -m scripts.init_db            # buat tabel yang belum ada
    python -m scripts.init_db --reset    # hapus lalu buat ulang tabel proyek

--reset menghapus isi stations, isochrones, pois, station_scores, dan
tenant_scores. Ketiganya bisa diisi
ulang penuh dari MAPID lewat scripts.ingest_layers, jadi tidak ada yang
hilang permanen — tapi tetap perlu diketik sendiri, bukan jalan diam-diam.
"""

import argparse
import sys

from sqlalchemy import inspect, text

from app.core.database import Base, engine

# Diimpor supaya metadata-nya kebaca, walau namanya tidak dipakai langsung.
from app.models import (  # noqa: F401
    Isochrone,
    Poi,
    Station,
    StationScore,
    TenantScore,
)

# Urutannya penting saat --reset: yang mengacu ke tabel lain dihapus dulu.
PROJECT_TABLES = (
    TenantScore.__table__,
    StationScore.__table__,
    Isochrone.__table__,
    Poi.__table__,
    Station.__table__,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="hapus dulu tabel proyek sebelum dibuat ulang",
    )
    args = parser.parse_args()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    if args.reset:
        Base.metadata.drop_all(bind=engine, tables=list(PROJECT_TABLES))
        print("tabel lama dihapus")

    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine, tables=list(PROJECT_TABLES))
    after = set(inspect(engine).get_table_names())

    created = sorted(after - before)
    print(f"tabel dibuat: {', '.join(created)}" if created else "tidak ada tabel baru")

    # create_all tidak pernah mengubah tabel yang sudah ada, jadi kolom baru di
    # tabel lama harus dilaporkan sendiri. Lebih baik ketahuan di sini daripada
    # nanti muncul sebagai UndefinedColumn saat impor.
    columns = {c["name"] for c in inspect(engine).get_columns("stations")}
    missing = {c.name for c in Station.__table__.columns} - columns
    if missing:
        print(f"\n! tabel stations ketinggalan kolom: {', '.join(sorted(missing))}")
        print("  jalankan ulang dengan --reset, lalu isi lagi:")
        print("  python -m scripts.init_db --reset && python -m scripts.ingest_layers")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
