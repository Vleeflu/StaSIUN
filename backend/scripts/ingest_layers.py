"""Isi tabel stations dari Geoserver MAPID.

Layer yang ditarik didaftar di data/layers.yml. Kredensialnya di backend/.env.
Hasil akhirnya diproses lewat modul yang sama dengan seed lokal.
"""

import sys
from pathlib import Path

import yaml

from app.services.mapid import MapidError, extract_features, fetch_layer
from app.services.station_import import feature_to_station, report, save_stations

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "layers.yml"


def main() -> int:
    catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    rows: list[dict] = []

    for entry in catalog.get("stations", []):
        try:
            payload = fetch_layer(entry["layer_id"])
        except MapidError as exc:
            print(f"  ! {entry['label']}: {exc}")
            return 1

        features = extract_features(payload)
        matched = [s for f in features if (s := feature_to_station(f))]
        print(f"  - {entry['label']}: {len(features)} fitur, {len(matched)} dipakai")
        rows.extend(matched)

    # Satu stasiun bisa muncul di beberapa layer, jadi dikunci pakai koordinat.
    unique: dict[str, dict] = {}
    for row in rows:
        unique.setdefault(str(row["location"]), row)
    rows = list(unique.values())

    if not rows:
        print("Tidak ada data terambil. Database tidak diubah.")
        return 1

    # Penghapusan data lama sengaja setelah semua layer berhasil ditarik.
    save_stations(rows)
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
