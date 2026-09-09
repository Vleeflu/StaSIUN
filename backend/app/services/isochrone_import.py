"""Ubah layer poligon isochrone MAPID jadi baris database.

Proyek GEO MAPID menyimpan beberapa layer isochrone dengan nama yang sama
persis, dan sebagian di antaranya salah — ada yang kosong, ada yang dihitung
pakai profil mobil. Karena dari luar tidak ada bedanya, tiap layer diperiksa
dulu di sini dan impornya dihentikan kalau ada yang tidak lolos.
"""

from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.isochrone import Isochrone
from app.models.station import Station

# Semua isochrone harus dihitung dengan profil yang sama. Mencampur foot dan
# car bikin wilayah yang kena profil mobil kelihatan jauh lebih mudah diakses.
EXPECTED_PROFILE = "foot"


class IsochroneError(RuntimeError):
    """Raised when an isochrone layer fails validation."""


def _osm_id(props: dict[str, Any]) -> str | None:
    marker = props.get("osm_id") or props.get("full_id")
    return str(marker).lstrip("nwr") if marker else None


def _to_multipolygon(geometry: dict[str, Any]) -> str | None:
    """Samakan Polygon dan MultiPolygon jadi satu bentuk WKT."""
    kind = geometry.get("type")
    coords = geometry.get("coordinates")

    if not coords:
        return None

    if kind == "Polygon":
        rings = [coords]
    elif kind == "MultiPolygon":
        rings = coords
    else:
        return None

    parts = []
    for polygon in rings:
        loops = [
            "(" + ", ".join(f"{pt[0]} {pt[1]}" for pt in loop) + ")"
            for loop in polygon
            if loop
        ]
        if loops:
            parts.append("(" + ", ".join(loops) + ")")

    return f"MULTIPOLYGON({', '.join(parts)})" if parts else None


def validate_layer(features: list[dict], minutes: int, label: str) -> None:
    """Tolak layer yang salah sebelum isinya sempat masuk database."""
    if not features:
        raise IsochroneError(f"{label}: layernya kosong, nol fitur")

    expected_limit = minutes * 60
    profiles = {(f.get("properties") or {}).get("isochrone_profile") for f in features}
    limits = {(f.get("properties") or {}).get("time_limit") for f in features}

    if profiles != {EXPECTED_PROFILE}:
        raise IsochroneError(
            f"{label}: profilnya {sorted(map(str, profiles))}, harusnya {EXPECTED_PROFILE!r}"
        )

    if limits != {expected_limit}:
        raise IsochroneError(
            f"{label}: time_limit-nya {sorted(map(str, limits))}, harusnya {expected_limit} detik"
        )


def features_to_rows(features: list[dict], minutes: int) -> list[dict]:
    rows: list[dict] = []

    for feature in features:
        area = _to_multipolygon(feature.get("geometry") or {})
        if not area:
            continue

        props = feature.get("properties") or {}
        rows.append(
            {
                "station_osm_id": _osm_id(props),
                "station_name": props.get("name"),
                "minutes": minutes,
                "profile": props.get("isochrone_profile") or EXPECTED_PROFILE,
                "area": WKTElement(area, srid=4326),
            }
        )

    return rows


def save_isochrones(rows: list[dict]) -> tuple[int, int]:
    """Ganti seluruh isi tabel, lalu sambungkan tiap poligon ke stasiunnya.

    Mengembalikan (jumlah tersimpan, jumlah yang tidak ketemu stasiunnya).
    """
    session = SessionLocal()
    try:
        lookup = {
            osm_id: station_id
            for station_id, osm_id in session.execute(
                select(Station.id, Station.osm_id).where(Station.osm_id.is_not(None))
            )
        }

        session.query(Isochrone).delete()

        orphans = 0
        for row in rows:
            station_id = lookup.get(row["station_osm_id"])
            if station_id is None:
                orphans += 1
            session.add(Isochrone(station_id=station_id, **row))

        session.commit()
        return len(rows), orphans
    finally:
        session.close()
