"""Isi tabel stations dari berkas GeoJSON lokal.

Sumbernya data OpenStreetMap stasiun kereta di DKI Jakarta. Cuma jaringan KAI
yang diambil; MRT, LRT, dan Whoosh dilewati.
"""

import json
import sys
from pathlib import Path

from app.services.station_import import feature_to_station, report, save_stations

SOURCE = Path(__file__).resolve().parents[1] / "data" / "railway_station_DKI.geojson"


def main() -> int:
    if not SOURCE.exists():
        print(f"Berkas tidak ditemukan: {SOURCE}")
        return 1

    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = [s for f in payload.get("features", []) if (s := feature_to_station(f))]

    if not rows:
        print("Tidak ada stasiun yang cocok. Database tidak diubah.")
        return 1

    save_stations(rows)
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
