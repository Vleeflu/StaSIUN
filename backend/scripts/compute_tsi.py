"""Hitung Tenant Survival Index tiap kategori usaha di tiap stasiun KRL.

Butuh skor SEPI lebih dulu, karena pengali konektivitasnya diambil dari
komponen T di tabel station_scores.

Pakai:
    python -m scripts.compute_tsi              # pita 10 menit
    python -m scripts.compute_tsi --minutes 5
    python -m scripts.compute_tsi --dry-run    # tampilkan saja, jangan simpan
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.models.tenant_score import TenantScore
from app.services.scoring.tenant import (
    CATEGORY_LABEL,
    TENANT_CATEGORIES,
    TenantError,
    compute_all,
)

COLUMNS = (
    "station_id",
    "minutes",
    "category",
    "tsi",
    "rank",
    "demand",
    "connectivity",
    "supply",
    "headroom",
)


def save(rows: list[dict], minutes: int) -> None:
    session = SessionLocal()
    try:
        session.query(TenantScore).filter(TenantScore.minutes == minutes).delete()
        for row in rows:
            session.add(TenantScore(**{k: row[k] for k in COLUMNS}))
        session.commit()
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=10, choices=(5, 10, 15))
    parser.add_argument("--dry-run", action="store_true", help="jangan simpan ke database")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        rows = compute_all(session, args.minutes)
    finally:
        session.close()

    if not rows:
        print("! tidak ada data. Jalankan dulu ingest_layers dan compute_sepi.")
        return 1

    print(f"pita {args.minutes} menit, {len(TENANT_CATEGORIES)} kategori tenant\n")

    for category in TENANT_CATEGORIES:
        top = [r for r in rows if r["category"] == category][:5]
        if not top:
            continue
        print(f"{CATEGORY_LABEL[category]}")
        print(f"{'':4}{'STASIUN':24}{'TSI':>6}{'CALON':>8}{'PESAING':>9}{'RASIO':>9}")
        for r in top:
            print(
                f"{r['rank']:3} {r['name'][:24]:24}{r['tsi']:6.1f}"
                f"{r['demand']:8}{r['supply']:9}{r['headroom']:9.1f}"
            )
        print()

    if args.dry_run:
        print("(dry run, tidak disimpan)")
        return 0

    save(rows, args.minutes)
    print(f"{len(rows)} skor tenant tersimpan untuk pita {args.minutes} menit")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TenantError as exc:
        print(f"! {exc}")
        sys.exit(1)
