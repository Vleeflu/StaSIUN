import json
from pathlib import Path

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.station import Station

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

stations: dict[tuple[float, float], dict] = {}

for path in sorted(DATA_DIR.glob("*.geojson")):
    for feat in json.loads(path.read_text(encoding="utf-8"))["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        p = feat["properties"]
        s = stations.setdefault(
            (lon, lat),
            {
                "name": p["NAMA"],
                "address": p.get("ALAMAT") or None,
                "kecamatan": p.get("KECAMATAN"),
                "kabkot": p.get("KABKOT"),
                "types": [],
            },
        )
        if p.get("TIPE_3") and p["TIPE_3"] not in s["types"]:
            s["types"].append(p["TIPE_3"])

db = SessionLocal()
db.query(Station).delete()
for (lon, lat), s in stations.items():
    db.add(Station(**s, location=WKTElement(f"POINT({lon} {lat})", srid=4326)))
db.commit()
print(f"{len(stations)} stasiun dimasukkan")
db.close()
