"""Ubah layer poligon isochrone GEO MAPID jadi baris database.

Alurnya dijelaskan di ADJUSTMENT.md bagian 7.6: layer ditarik lewat
`layers_new/get_layer` oleh skrip importer, tidak pernah dari endpoint yang
diakses pengguna.

Validasinya diambil dari branch main. Alasannya pengetahuan lapangan yang tidak
bisa ditebak dari luar: proyek GEO MAPID memuat beberapa layer isochrone
BERNAMA SAMA PERSIS, sebagian kosong dan sebagian dihitung memakai profil
mobil. Layer yang salah lebih berbahaya daripada impor yang gagal, karena
skornya tetap keluar - hanya saja keliru, dan tidak ada yang memberi tahu.

Yang berbeda dari main: kolomnya `geom` (bukan `area`), dan Permeability Index
ikut dihitung karena PRD mensyaratkannya sebagai kriteria penerimaan.
"""

import math
from datetime import datetime, timezone
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.core.geo import SRID_METRIC, SRID_RENDER
from app.models.isochrone import Isochrone
from app.models.station import Station

# Semua isochrone harus dihitung dengan profil yang sama. Mencampur foot dan
# car membuat wilayah yang kena profil mobil terlihat jauh lebih mudah diakses
# daripada kenyataannya - dan bedanya tidak kelihatan dari bentuk poligonnya.
EXPECTED_PROFILE = "foot"

# Kecepatan berjalan yang dipakai tools isochrone GEO MAPID.
#
# Layernya TIDAK membawa atribut kecepatan - sudah diperiksa, propertinya cuma
# tag OSM stasiun + id_tool + isochrone_profile + time_limit. Jadi angka ini
# tetap asumsi, bukan bacaan, dan disimpan per baris supaya ikut terbawa sebagai
# metadata alih-alih mengendap di kode.
#
# Tapi asumsinya SUDAH DIUJI, bukan sekadar ditebak dari bawaan mesin routing.
# Ujinya lewat Permeability Index sendiri: PI = luas isochrone / luas lingkaran
# setara, dan penyebutnya bergantung langsung pada kecepatan ini. Jaringan jalan
# tidak mungkin mengalahkan garis lurus ke segala arah, jadi PI > 1 adalah bukti
# penyebutnya kekecilan. Dihitung atas 76 stasiun x 3 durasi (10 Sep 2026):
#
#   4 km/jam   PI maks 1,231   -> 4-6 stasiun ber-PI > 1. Mustahil. Tersingkir.
#   5 km/jam   PI maks 0,788   -> stasiun bergrid terbaik mencapai 79% cakram
#                                 teoretis. Persis yang diharapkan.
#   6 km/jam   PI maks 0,547   -> berarti TIDAK ADA stasiun di Jakarta yang
#                                 jaringan jalannya bagus. Tidak masuk akal.
#
# PI-nya juga stabil antar durasi pada 5 km/jam (median 0,465 / 0,456 / 0,495
# untuk 5 / 10 / 15 menit), pertanda tools-nya konsisten secara internal.
DEFAULT_WALK_SPEED_KMH = 5.0


class IsochroneError(RuntimeError):
    """Dilempar kalau sebuah layer isochrone tidak lolos pemeriksaan."""


def _osm_id(props: dict[str, Any]) -> str | None:
    """Kunci sambungan ke stasiun.

    Prefiks n/w/r dibuang supaya bentuknya sama dengan yang disimpan
    stations.osm_id. Layer isochrone membawa keduanya: osm_id (4981870932)
    dan full_id (n4981870932).
    """
    marker = props.get("osm_id") or props.get("full_id")
    return str(marker).lstrip("nwr") if marker else None


def _to_multipolygon(geometry: dict[str, Any]) -> str | None:
    """Samakan Polygon dan MultiPolygon jadi satu bentuk WKT.

    Layer GEO MAPID mengirim Polygon, tapi kolomnya MULTIPOLYGON: hasil
    isochrone bisa terpecah jadi beberapa kepingan kalau ada rel atau sungai
    yang memutus jaringan jalan. Menyeragamkan di sini membuat kolomnya tidak
    perlu menampung dua tipe geometri sekaligus.
    """
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

    # Tanpa osm_id, poligonnya tidak bisa disambungkan ke stasiun mana pun.
    # Dicegah di sini supaya kegagalannya berbunyi, bukan muncul belakangan
    # sebagai tumpukan baris unmatched yang gampang dikira wajar.
    tanpa_id = sum(1 for f in features if not _osm_id(f.get("properties") or {}))
    if tanpa_id:
        raise IsochroneError(
            f"{label}: {tanpa_id} dari {len(features)} poligon tidak punya osm_id"
        )


def features_to_rows(
    features: list[dict], minutes: int, layer_id: str | None = None
) -> list[dict]:
    """Ubah fitur GeoJSON jadi dict siap-simpan. Fitur tanpa geometri dilewati."""
    waktu = datetime.now(timezone.utc)
    rows: list[dict] = []

    for feature in features:
        geom = _to_multipolygon(feature.get("geometry") or {})
        if not geom:
            continue

        props = feature.get("properties") or {}
        rows.append(
            {
                "station_osm_id": _osm_id(props),
                "station_name": props.get("name"),
                "minutes": minutes,
                "profile": props.get("isochrone_profile") or EXPECTED_PROFILE,
                "geom": WKTElement(geom, srid=SRID_RENDER),
                "walk_speed_kmh": DEFAULT_WALK_SPEED_KMH,
                "source_layer_id": layer_id,
                "fetched_at": waktu,
            }
        )

    return rows


def lingkaran_setara_m2(minutes: int, speed_kmh: float = DEFAULT_WALK_SPEED_KMH) -> float:
    """Luas lingkaran yang bisa dicapai kalau tidak ada hambatan sama sekali.

    Jadi penyebut Permeability Index. Radiusnya kecepatan dikali waktu, jadi
    5 km/jam selama 5 menit memberi radius 416,7 m dan luas 545.415 m2.
    """
    radius_m = (speed_kmh * 1000.0 / 3600.0) * (minutes * 60)
    return math.pi * radius_m**2


def save_isochrones(rows: list[dict]) -> tuple[int, int]:
    """Simpan poligon, sambungkan ke stasiun lewat osm_id, hitung turunannya.

    Mengembalikan (jumlah tersimpan, jumlah yang tidak ketemu stasiunnya).

    Baris yang tidak ketemu stasiunnya TIDAK dibuang. Disimpan dengan
    station_id kosong dan match_method "unmatched" supaya bisa diperiksa
    manual - data yang hilang tanpa jejak jauh lebih berbahaya daripada data
    yang ditandai bermasalah.
    """
    if not rows:
        return 0, 0

    session = SessionLocal()
    try:
        lookup = {
            osm_id: station_id
            for station_id, osm_id in session.execute(
                select(Station.id, Station.osm_id).where(Station.osm_id.is_not(None))
            )
        }

        # Hapus hanya durasi yang sedang diimpor. Kalau suatu saat hanya layer
        # 5 menit yang ditarik ulang, poligon 10 dan 15 menit tidak ikut hilang.
        durasi = sorted({r["minutes"] for r in rows})
        session.query(Isochrone).filter(Isochrone.minutes.in_(durasi)).delete(
            synchronize_session=False
        )

        orphans = 0
        for row in rows:
            station_id = lookup.get(row["station_osm_id"])
            if station_id is None:
                orphans += 1
            session.add(
                Isochrone(
                    station_id=station_id,
                    match_method="osm_id" if station_id else "unmatched",
                    **row,
                )
            )

        session.flush()

        # Luas dan Permeability Index dihitung di SQL, bukan di Python: luas
        # yang benar mensyaratkan proyeksi ke EPSG:32748, dan PostGIS sudah
        # punya ST_Transform. Menghitungnya di Python berarti menulis ulang
        # proyeksi peta sendiri.
        session.execute(
            text(
                f"""
                UPDATE isochrones
                   SET area_m2 = ST_Area(ST_Transform(geom, {SRID_METRIC})),
                       permeability_index = ST_Area(ST_Transform(geom, {SRID_METRIC}))
                           / (pi() * POWER(walk_speed_kmh * 1000.0 / 3600.0 * minutes * 60, 2))
                 WHERE minutes = ANY(:durasi)
                """
            ),
            {"durasi": durasi},
        )

        session.commit()
        return len(rows), orphans
    finally:
        session.close()
