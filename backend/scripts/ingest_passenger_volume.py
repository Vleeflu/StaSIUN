"""Isi tabel passenger_volume dari data/passenger_volume.csv (blocker N4).

Volume penumpang adalah indikator terpenting variabel T, dan satu-satunya yang
memberi T variasi kontinu. Tanpa data ini T hanya punya lima nilai unik dan
seri di 38 dari 46 stasiun KAI — lihat ADJUSTMENT.md bagian 7.13.

    python -m scripts.ingest_passenger_volume --dry-run
    python -m scripts.ingest_passenger_volume

Idempoten lewat kunci (station_id, period, source): menjalankan ulang
memperbarui baris yang sama, tidak menggandakannya. Sumber ikut jadi kunci
karena dua sumber berbeda boleh melaporkan angka berbeda untuk periode yang
sama, dan keduanya berhak disimpan.
"""

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal
from app.models.reference import PassengerVolume
from app.models.station import Station
from app.services.station_import import normalize

BERKAS = Path(__file__).resolve().parents[1] / "data" / "passenger_volume.csv"

WAJIB = ("station_name", "period", "passengers_per_day", "source", "accessed_at")


def peta_stasiun(session) -> dict[str, list[tuple[int, str, str]]]:
    """Nama ternormalisasi -> daftar (id, nama asli, jaringan).

    Sengaja mengembalikan DAFTAR, bukan satu id. Nama stasiun bukan kunci unik
    di proyek ini: "Cawang" ada dua (KAI Commuter dan LRT Jabodebek, terpisah
    1.437 m) dan "Halim" ada dua (Whoosh dan LRT Jabodebek). Mengembalikan satu
    id akan diam-diam memilih salah satunya — persis jenis kesalahan yang
    tidak memunculkan error tetapi menaruh angka di stasiun yang keliru.
    """
    peta: dict[str, list[tuple[int, str, str]]] = {}
    for r in session.execute(select(Station.id, Station.name, Station.types)).all():
        jaringan = r.types[0] if r.types else ""
        peta.setdefault(normalize(r.name), []).append((r.id, r.name, jaringan))
    return peta


def baca_csv() -> tuple[list[dict], list[str]]:
    """Baca CSV, buang baris komentar, laporkan baris yang cacat."""
    if not BERKAS.exists():
        raise FileNotFoundError(BERKAS)

    baris, keluhan = [], []
    with BERKAS.open(encoding="utf-8-sig", newline="") as f:
        for nomor, row in enumerate(csv.DictReader(f), start=2):
            nama = (row.get("station_name") or "").strip()
            # Baris penjelasan di template diawali '#'.
            if not nama or nama.startswith("#"):
                continue

            kosong = [k for k in WAJIB if not (row.get(k) or "").strip()]
            if kosong:
                keluhan.append(f"baris {nomor} ({nama}): kolom wajib kosong: {', '.join(kosong)}")
                continue

            try:
                row["passengers_per_day"] = float(row["passengers_per_day"].replace(".", "").replace(",", "."))
                row["accessed_at"] = date.fromisoformat(row["accessed_at"].strip())
            except ValueError as exc:
                keluhan.append(f"baris {nomor} ({nama}): {exc}")
                continue

            row["station_name"] = nama
            row["network"] = (row.get("network") or "").strip()
            row["period"] = row["period"].strip()
            row["source"] = row["source"].strip()
            row["source_url"] = (row.get("source_url") or "").strip() or None
            baris.append(row)
    return baris, keluhan


def main() -> int:
    parser = argparse.ArgumentParser(description="Impor volume penumpang stasiun.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        baris, keluhan = baca_csv()
    except FileNotFoundError:
        print(f"Berkas tidak ditemukan: {BERKAS}")
        return 1

    session = SessionLocal()
    try:
        peta = peta_stasiun(session)

        siap, gagal = [], list(keluhan)
        for row in baris:
            kandidat = peta.get(normalize(row["station_name"]), [])
            if not kandidat:
                gagal.append(f"{row['station_name']!r}: tidak ada stasiun bernama itu di database")
                continue

            if len(kandidat) > 1:
                if not row["network"]:
                    jaringan = ", ".join(j for _, _, j in kandidat)
                    gagal.append(
                        f"{row['station_name']!r}: ada {len(kandidat)} stasiun dengan nama ini "
                        f"({jaringan}). Isi kolom network untuk menentukan yang mana."
                    )
                    continue
                cocok = [k for k in kandidat if k[2].lower() == row["network"].lower()]
                if len(cocok) != 1:
                    gagal.append(
                        f"{row['station_name']!r} + network={row['network']!r}: "
                        f"cocok dengan {len(cocok)} stasiun, harus tepat 1"
                    )
                    continue
                kandidat = cocok

            siap.append((kandidat[0][0], kandidat[0][1], row))

        if gagal:
            print(f"{len(gagal)} baris ditolak:")
            for g in gagal:
                print(f"  ! {g}")
            print()

        if not siap:
            print("Tidak ada baris yang bisa diimpor. Database tidak diubah.")
            return 1

        print(f"{len(siap)} baris siap diimpor:")
        for sid, nama, row in siap[:15]:
            print(f"  {nama[:28]:29s} {row['period']:8s} {row['passengers_per_day']:>12,.0f} /hari  ({row['source'][:24]})")
        if len(siap) > 15:
            print(f"  ... dan {len(siap) - 15} lainnya")

        total_stasiun = session.execute(select(func.count()).select_from(Station)).scalar_one()
        print(f"\nCakupan: {len({s for s, _, _ in siap})} dari {total_stasiun} stasiun.")

        if args.dry_run:
            print("\n--dry-run: database tidak disentuh.")
            return 0

        nilai = [
            {
                "station_id": sid,
                "period": row["period"],
                "passengers_per_day": row["passengers_per_day"],
                "source": row["source"],
                "source_url": row["source_url"],
                "accessed_at": row["accessed_at"],
            }
            for sid, _, row in siap
        ]
        stmt = insert(PassengerVolume).values(nilai)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_passenger_volume_station_period",
            set_={
                "passengers_per_day": stmt.excluded.passengers_per_day,
                "source_url": stmt.excluded.source_url,
                "accessed_at": stmt.excluded.accessed_at,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)
        session.commit()

        total = session.execute(select(func.count()).select_from(PassengerVolume)).scalar_one()
        print(f"\nTersimpan. Tabel passenger_volume sekarang berisi {total} baris.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
