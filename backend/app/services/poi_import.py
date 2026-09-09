"""Ubah layer titik minat MAPID jadi baris database.

Layer POI di GEO MAPID saling tumpang tindih: sebagian kategori adalah bagian
dari kategori lain, dan satu tempat yang sama bisa muncul di dua layer. Kalau
dibiarkan, variabel SEPI yang disuapinya ikut berlipat — jadi semua titik
disaring duplikatnya di sini, lintas kategori maupun lintas wilayah.
"""

from typing import Any

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.poi import Poi

# Pembulatan koordinat buat mengenali titik yang sama dari dua layer berbeda.
# Lima angka di belakang koma kira-kira satu meter di Jakarta — cukup ketat
# untuk tidak menggabung dua toko bersebelahan, cukup longgar untuk memaafkan
# beda pembulatan antar berkas.
COORD_PRECISION = 5

VALID_VARIABLES = {"T", "E", "A", "U", "C"}


class PoiError(RuntimeError):
    """Raised when a POI layer cannot be turned into rows."""


def feature_to_poi(feature: dict[str, Any], category: str, variable: str) -> dict | None:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        return None

    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None

    props = feature.get("properties") or {}
    name = (props.get("NAMA") or props.get("name") or "").strip()
    if not name:
        return None

    lon, lat = coords[0], coords[1]

    return {
        "name": name,
        "category": category,
        "variable": variable,
        "kabkot": props.get("KABKOT") or None,
        "kecamatan": props.get("KECAMATAN") or None,
        "location": WKTElement(f"POINT({lon} {lat})", srid=4326),
        # Bukan kolom database, cuma dipakai buat menyaring duplikat.
        "_key": (
            name.upper(),
            round(lon, COORD_PRECISION),
            round(lat, COORD_PRECISION),
        ),
    }


def dedupe(rows: list[dict]) -> list[dict]:
    """Buang titik yang sudah pernah masuk lewat layer lain.

    Yang menang adalah yang lebih dulu didaftarkan di layers.yml, jadi urutan
    di katalog menentukan kategori mana yang dianggap paling menggambarkan.
    """
    seen: set[tuple] = set()
    unique: list[dict] = []

    for row in rows:
        key = row["_key"]
        if key in seen:
            continue
        seen.add(key)
        unique.append({k: v for k, v in row.items() if k != "_key"})

    return unique


def save_pois(rows: list[dict]) -> None:
    """Ganti seluruh isi tabel pois. Dipanggil hanya kalau rows tidak kosong."""
    session = SessionLocal()
    try:
        session.query(Poi).delete()
        for row in rows:
            session.add(Poi(**row))
        session.commit()
    finally:
        session.close()
