import sys
from pathlib import Path

import yaml
from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.station import Station
from app.services.mapid import MapidError, extract_features, fetch_layer

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "layers.yml"


def main() -> int:
    catalog = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    stations: dict[tuple[float, float], dict] = {}

    for entry in catalog.get("stations", []):
        try:
            payload = fetch_layer(entry["layer_id"])
        except MapidError as exc:
            print(f"  ! {entry['label']}: {exc}")
            return 1

        features = extract_features(payload)
        print(f"  - {entry['label']}: {len(features)} features")

        for feature in features:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point":
                continue

            lon, lat = geometry["coordinates"][:2]
            props = feature.get("properties") or {}

            # Kunci dedup pakai koordinat, bukan nama — ada dua Stasiun Cawang
            # yang beda lokasi, kalau pakai nama malah kegabung jadi satu.
            station = stations.setdefault(
                (lon, lat),
                {
                    "name": props.get("NAMA") or "TANPA NAMA",
                    "address": props.get("ALAMAT") or None,
                    "kecamatan": props.get("KECAMATAN"),
                    "kabkot": props.get("KABKOT"),
                    "types": [],
                },
            )

            service_type = props.get("TIPE_3")
            if service_type and service_type not in station["types"]:
                station["types"].append(service_type)

    if not stations:
        print("No data retrieved. Database left unchanged.")
        return 1

    # Baru hapus data lama setelah semua layer berhasil diambil, biar satu
    # request yang gagal nggak bikin database kosong.
    session = SessionLocal()
    try:
        session.query(Station).delete()
        for (lon, lat), station in stations.items():
            session.add(
                Station(
                    **station,
                    location=WKTElement(f"POINT({lon} {lat})", srid=4326),
                )
            )
        session.commit()
    finally:
        session.close()

    print(f"{len(stations)} stations stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
