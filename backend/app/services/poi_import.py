"""Ubah layer titik minat MAPID jadi baris database.

Layer POI di GEO MAPID saling tumpang tindih: sebagian kategori adalah bagian
dari kategori lain, dan satu tempat yang sama bisa muncul di dua layer. Kalau
dibiarkan, variabel SEPI yang disuapinya ikut berlipat — jadi semua titik
disaring duplikatnya di sini, lintas kategori maupun lintas wilayah.
"""

import math
import re
from collections import defaultdict
from typing import Any

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.poi import Poi

# Dua titik dianggap tempat yang sama kalau namanya cocok setelah dinormalkan
# DAN jaraknya di bawah ambang ini. Cukup longgar untuk memaafkan beda
# geocoding antar layer, cukup ketat untuk tidak menggabung dua gerai berbeda
# di ruas jalan yang sama.
SAME_PLACE_METERS = 25.0

VALID_VARIABLES = {"T", "E", "A", "U", "C"}


class PoiError(RuntimeError):
    """Raised when a POI layer cannot be turned into rows."""


def name_key(name: str) -> str:
    """Samakan ejaan supaya nama dari layer berbeda bisa dicocokkan.

    Menyingkirkan semua yang bukan huruf atau angka. Itu sekaligus menjinakkan
    tiga bentuk gangguan yang benar-benar muncul di data MAPID: tanda kurung
    yang kadang ada kadang tidak ("INDOMARET PETOGOGAN TB49" versus
    "INDOMARET PETOGOGAN (TB49)"), pemisah pipa, dan nama yang huruf beraksennya
    telanjur rusak jadi mojibake.
    """
    cleaned = re.sub(r"[^A-Z0-9]", "", (name or "").upper())
    # Nama yang tidak menyisakan satu pun huruf latin dipulangkan apa adanya,
    # supaya dua tempat berbeda tidak tergabung cuma karena sama-sama kosong.
    return cleaned or (name or "").strip().upper()


def meters_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Jarak perkiraan dua koordinat, dalam meter.

    Pakai perataan bidang datar, bukan haversine. Pada jarak puluhan meter di
    lintang Jakarta galatnya jauh di bawah satu meter, dan ini dipanggil puluhan
    ribu kali saat impor.
    """
    lon1, lat1 = a
    lon2, lat2 = b
    dx = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * 110540.0
    return math.hypot(dx, dy)


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
        "_key": (name_key(name), (lon, lat)),
    }


def dedupe(rows: list[dict]) -> list[dict]:
    """Buang titik yang sudah pernah masuk lewat layer lain.

    Sengaja TIDAK memakai koordinat yang dibulatkan sebagai kunci. Pembulatan
    ke kisi tidak pernah bisa menyatukan dua titik yang mengangkangi garis kisi,
    sedekat apa pun jaraknya - Starbucks Cideng sempat lolos dua kali karena
    dua salinannya terpaut 1,1 sentimeter tapi jatuh di sisi kisi yang berbeda.
    Jaraknya diuji sungguhan supaya kasus seperti itu tertangkap.

    Yang menang adalah yang lebih dulu didaftarkan di layers.yml, jadi urutan
    kategori di katalog menentukan label mana yang dianggap paling menggambarkan.
    """
    kept: dict[str, list[tuple[float, float]]] = defaultdict(list)
    unique: list[dict] = []

    for row in rows:
        key, point = row["_key"]
        seen = kept[key]

        if any(meters_between(point, other) <= SAME_PLACE_METERS for other in seen):
            continue

        seen.append(point)
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
