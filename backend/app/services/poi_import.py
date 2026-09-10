"""Ubah layer titik minat GEO MAPID jadi baris database.

Lajur kedua di samping Overpass. Bedanya dijelaskan di docstring model Poi;
ringkasnya, layer MAPID lebih rapat untuk kategori komersial tetapi tidak
membawa tag mentah dan tidak punya id stabil.

Ketiadaan id stabil itulah yang membuat modul ini ada. Layer POI di GEO MAPID
saling tumpang tindih - sebagian kategori adalah himpunan bagian dari kategori
lain, dan satu tempat yang sama bisa muncul di dua layer. Tanpa id, satu-satunya
cara mengenali "tempat yang sama" adalah nama plus jarak. Kalau tidak disaring,
variabel yang disuapinya ikut berlipat.

Penyaring duplikatnya diambil dari branch main, termasuk ambang 25 m dan alasan
kenapa pembulatan koordinat tidak dipakai.
"""

import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.core.geo import SRID_RENDER
from app.models.reference import Poi

SOURCE = "mapid"

# Dua titik dianggap tempat yang sama kalau namanya cocok setelah dinormalkan
# DAN jaraknya di bawah ambang ini. Cukup longgar untuk memaafkan beda
# geocoding antar layer, cukup ketat untuk tidak menggabung dua gerai berbeda
# di ruas jalan yang sama.
SAME_PLACE_METERS = 25.0


class PoiError(RuntimeError):
    """Dilempar kalau sebuah layer POI tidak bisa diubah jadi baris."""


def name_key(name: str) -> str:
    """Samakan ejaan supaya nama dari layer berbeda bisa dicocokkan.

    Menyingkirkan semua yang bukan huruf atau angka. Itu sekaligus menjinakkan
    tiga bentuk gangguan yang benar-benar muncul di data MAPID: tanda kurung
    yang kadang ada kadang tidak ("INDOMARET PETOGOGAN TB49" versus "INDOMARET
    PETOGOGAN (TB49)"), pemisah pipa, dan nama yang huruf beraksennya telanjur
    rusak jadi mojibake.
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


def feature_to_poi(feature: dict[str, Any], category: str, fungsi: str) -> dict | None:
    """Satu fitur GeoJSON jadi dict siap-simpan, atau None kalau dilewati.

    Variabel SEPI yang disuapi TIDAK ikut disimpan, walau branch main
    menyimpannya. Alasannya justru bug yang sedang diperbaiki: di main nilainya
    tersimpan sebagai 'C' dan 'E', dan itu bertentangan dengan PRD Tabel 6.
    Nilai turunan yang diatur PRD kalau ikut mengendap di database akan menua
    diam-diam saat PRD-nya dibaca ulang. Pemetaannya karena itu tinggal di satu
    tempat saja: layers.yml, dibaca ulang setiap kali dihitung.
    """
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
        "source": SOURCE,
        "osm_type": None,
        "osm_id": None,
        "name": name,
        "category": category,
        "fungsi": fungsi,
        # Atribut administratif layernya disimpan di osm_tags. Bukan tag OSM,
        # tapi kolom itu sudah JSONB dan berfungsi sama: menyimpan properti
        # asal apa adanya supaya tidak ada yang hilang saat impor.
        "osm_tags": {
            k: v
            for k, v in props.items()
            if k in ("ALAMAT", "DESA", "KECAMATAN", "KABKOT", "ID_DESA", "ID_KEC")
            and v not in (None, "")
        },
        "location": WKTElement(f"POINT({lon} {lat})", srid=SRID_RENDER),
        # Bukan kolom database, cuma dipakai buat menyaring duplikat.
        "_key": (name_key(name), (lon, lat)),
    }


def dedupe(rows: list[dict]) -> list[dict]:
    """Buang titik yang sudah pernah masuk lewat layer lain.

    Sengaja TIDAK memakai koordinat yang dibulatkan sebagai kunci. Pembulatan
    ke kisi tidak pernah bisa menyatukan dua titik yang mengangkangi garis kisi,
    sedekat apa pun jaraknya - Starbucks Cideng sempat lolos dua kali karena dua
    salinannya terpaut 1,1 sentimeter tapi jatuh di sisi kisi yang berbeda.
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


def save_pois(rows: list[dict]) -> int:
    """Ganti baris bersumber MAPID saja, jangan sentuh baris Overpass.

    Ini beda penting dari branch main, yang mengosongkan seluruh tabel. Di sini
    tabelnya dipakai dua sumber, jadi menghapus semuanya berarti membuang 19.792
    baris Overpass beserta tag mentahnya setiap kali impor MAPID dijalankan.
    """
    if not rows:
        return 0

    waktu = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        session.query(Poi).filter(Poi.source == SOURCE).delete(synchronize_session=False)
        for row in rows:
            session.add(Poi(fetched_at=waktu, **row))
        session.commit()
        return len(rows)
    finally:
        session.close()
