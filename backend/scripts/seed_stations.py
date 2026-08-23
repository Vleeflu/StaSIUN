import json
from pathlib import Path

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.station import Station

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Semua berkas di folder ini isinya stasiun KRL, jadi jenis layanannya seragam.
DEFAULT_SERVICE_TYPE = "COMMUTER"

stations: dict[tuple[float, float], dict] = {}

for path in sorted(DATA_DIR.glob("*.geojson")):
    for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue

        lon, lat = geometry["coordinates"][:2]
        props = feature.get("properties") or {}

        name = (props.get("STASIUN") or "").strip().upper()
        if not name:
            continue

        # Satu stasiun bisa muncul di beberapa berkas kalau dilewati lebih dari
        # satu jalur, jadi dikunci pakai koordinat lalu jalurnya dikumpulkan.
        station = stations.setdefault(
            (lon, lat),
            {
                "name": name,
                "address": None,
                "kecamatan": None,
                "kabkot": None,
                "types": [DEFAULT_SERVICE_TYPE],
                "lines": [],
            },
        )

        line = props.get("JALUR")
        if line and line not in station["lines"]:
            station["lines"].append(line)

for station in stations.values():
    station["lines"].sort()

session = SessionLocal()
try:
    session.query(Station).delete()
    for (lon, lat), station in stations.items():
        session.add(
            Station(**station, location=WKTElement(f"POINT({lon} {lat})", srid=4326))
        )
    session.commit()
finally:
    session.close()

print(f"{len(stations)} stations stored")
