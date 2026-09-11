import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.isochrone import Isochrone
from app.models.reference import PassengerVolume, Poi
from app.models.score import StationScore
from app.models.station import Station
from app.models.tenant_score import TenantScore
from app.services.scoring.tenant import CATEGORY_LABEL
from app.services.station_areas import area_stasiun

router = APIRouter(tags=["stations"])


@router.get("/stations")
def list_stations(
    db: Session = Depends(get_db),
    service_type: str | None = Query(default=None, alias="type"),
    minutes: int = Query(default=10, ge=5, le=15),
):
    stmt = select(
        Station.id,
        Station.name,
        Station.code,
        Station.types,
        Station.lines,
        Station.served,
        Station.kecamatan,
        Station.address,
        func.ST_AsGeoJSON(Station.location).label("geom"),
        StationScore.sepi,
        StationScore.rank,
    ).outerjoin(
        # Stasiun tanpa skor tetap ikut terkirim; peta butuh titiknya walau
        # skornya belum dihitung untuk pita waktu ini.
        StationScore,
        (StationScore.station_id == Station.id) & (StationScore.minutes == minutes),
    ).order_by(Station.name)

    if service_type:
        stmt = stmt.where(Station.types.any(service_type))

    rows = db.execute(stmt).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r.id,
                "geometry": json.loads(r.geom),
                "properties": {
                    "name": r.name,
                    "code": r.code,
                    "types": r.types,
                    "network": r.types[0] if r.types else None,
                    "lines": r.lines,
                    "primary_line": r.lines[0] if r.lines else None,
                    "is_interchange": len(r.lines) > 1,
                    "line_key": "-".join(r.lines) if r.lines else (r.types[0] if r.types else "none"),
                    "served": r.served,
                    "sepi": r.sepi,
                    "sepi_rank": r.rank,
                    "kecamatan": r.kecamatan,
                    "address": r.address,
                },
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/score")
def station_score(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Rincian skor SEPI satu stasiun, lengkap dengan angka mentahnya."""
    row = db.execute(
        select(StationScore).where(
            StationScore.station_id == station_id,
            StationScore.minutes == minutes,
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Skor pita {minutes} menit belum dihitung untuk stasiun ini",
        )

    total = db.execute(
        select(func.count()).select_from(StationScore).where(StationScore.minutes == minutes)
    ).scalar_one()

    volume = db.execute(
        select(PassengerVolume)
        .where(PassengerVolume.station_id == station_id)
        .order_by(PassengerVolume.accessed_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    return {
        "station_id": row.station_id,
        "minutes": row.minutes,
        "sepi": row.sepi,
        "kelas": row.kelas,
        "keputusan": row.keputusan,
        "rank": row.rank,
        "rank_total": total,
        # Kekokohan peringkat terhadap pilihan pembobotan (ADJUSTMENT 9.30).
        # Peringkat tunggal tanpa ini menyiratkan kepastian yang tidak ada.
        "sensitivity": row.sensitivity,
        # Kedekatan TOPSIS dikirim TERPISAH dan diberi peringatan, supaya panel
        # tidak tergoda memakainya sebagai skor. Nilainya bergantung pada
        # himpunan stasiun yang ikut dinilai (rank reversal), jadi ia hanya sah
        # sebagai pembanding relatif di dalam himpunan yang sama.
        "topsis": row.topsis,
        "topsis_catatan": (
            "Pembanding relatif dalam himpunan yang dinilai. Jangan dipakai "
            "untuk klasifikasi; pakai `sepi`."
        ),
        # Metadata keyakinan (F5-4). WAJIB ikut ditampilkan: skor dari 3
        # variabel tidak sebanding dengan skor 5 variabel.
        "confidence": row.confidence,
        "variabel_terpakai": row.variabel_terpakai,
        "variabel_total": 5,
        "components": {
            "T": row.raw_t,
            "E": row.raw_e,
            "A": row.raw_a,
            "U": row.raw_u,
            "C": row.raw_c,
        },
        "detail": {
            "line_count": row.line_count,
            "halte_count": row.halte_count,
            "other_mode_count": row.other_mode_count,
            "area_km2": row.area_km2,
        },
        # Volume penumpang adalah angka paling nyata yang kita punya, tetapi
        # baru tersedia untuk 10 dari 46 stasiun (22%). Karena di bawah ambang
        # 70%, ia BELUM dipakai sebagai indikator variabel T - jadi dikirim
        # sebagai konteks yang ditampilkan apa adanya, bukan sebagai komponen
        # skor. Membedakan keduanya penting supaya pembaca tidak menyangka
        # peringkatnya sudah memperhitungkan keramaian sebenarnya.
        "passenger_volume": (
            None
            if volume is None
            else {
                "per_day": volume.passengers_per_day,
                "period": volume.period,
                "source": volume.source,
                # Diperbarui 12 Sep: volume SUDAH jadi salah satu indikator T
                # untuk stasiun yang punya datanya (matrix.py), dan sengaja
                # tidak di-shrink. Catatan lama ("bukan komponen skor") keliru.
                "catatan": (
                    "Ikut menghitung indikator T untuk stasiun ini. Cakupannya baru "
                    "10 stasiun; yang lain tidak diberi nol, melainkan dihitung dari "
                    "indikator T lainnya."
                ),
            }
        ),
    }


@router.get("/stations/{station_id}/isochrones")
def station_isochrones(station_id: int, db: Session = Depends(get_db)):
    """Poligon jangkauan jalan kaki satu stasiun, ketiga pita sekaligus.

    Diurutkan dari yang terluas supaya penggambarnya bisa menumpuk begitu saja:
    15 menit di bawah, 5 menit paling atas.
    """
    rows = db.execute(
        select(
            Isochrone.minutes,
            Isochrone.profile,
            func.ST_AsGeoJSON(Isochrone.geom).label("geom"),
        )
        .where(Isochrone.station_id == station_id)
        .order_by(Isochrone.minutes.desc())
    ).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r.minutes,
                "geometry": json.loads(r.geom),
                "properties": {"minutes": r.minutes, "profile": r.profile},
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/tenants")
def station_tenants(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Tenant Survival Index tiap kategori usaha untuk satu stasiun.

    Diurutkan dari yang paling lapang. Angka mentahnya ikut dikirim karena
    skor 0-100 tanpa pembilang penyebutnya tidak bisa dipakai mengambil
    keputusan sewa.
    """
    rows = db.execute(
        select(TenantScore)
        .where(
            TenantScore.station_id == station_id,
            TenantScore.minutes == minutes,
        )
        .order_by(TenantScore.tsi.desc())
    ).scalars().all()

    total = db.execute(
        select(func.count(func.distinct(TenantScore.station_id))).where(
            TenantScore.minutes == minutes
        )
    ).scalar_one()

    return {
        "station_id": station_id,
        "minutes": minutes,
        "station_count": total,
        "categories": [
            {
                "category": r.category,
                "label": CATEGORY_LABEL.get(r.category, r.category),
                "tsi": r.tsi,
                "rank": r.rank,
                "demand": r.demand,
                "connectivity": r.connectivity,
                "supply": r.supply,
                "headroom": r.headroom,
            }
            for r in rows
        ],
    }


@router.get("/stations/{station_id}/pois")
def station_pois(
    station_id: int,
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
    source: str = Query(default="mapid", pattern="^(mapid|overpass)$"),
):
    """Titik minat yang jatuh di dalam isochrone satu stasiun.

    Sengaja per stasiun, bukan seluruh DKI: tabelnya 52 ribu baris, dan yang
    berguna dilihat cuma yang ada di sekitar stasiun yang sedang dibuka.

    `source` WAJIB disaring. Tabel poi menampung dua lajur yang saling tumpang
    tindih secara geografis; tanpa saringan ini satu tempat nyata muncul dua
    kali di peta, sekali dari tiap lajur. Bawaannya "mapid" karena taksonominya
    yang halus (alfamart, apotek, coffee_shop) itulah yang dipakai label peta
    dan sisi pasokan TSI.
    """
    area = (
        select(Isochrone.geom)
        .where(
            Isochrone.station_id == station_id,
            Isochrone.minutes == minutes,
        )
        .scalar_subquery()
    )

    rows = db.execute(
        select(
            Poi.name,
            Poi.category,
            Poi.fungsi,
            func.ST_AsGeoJSON(Poi.location).label("geom"),
        )
        .where(Poi.source == source, func.ST_Contains(area, Poi.location))
        .order_by(Poi.category, Poi.name)
    ).all()

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": index,
                "geometry": json.loads(r.geom),
                "properties": {
                    "name": r.name,
                    "category": r.category,
                    "fungsi": r.fungsi,
                },
            }
            for index, r in enumerate(rows)
        ],
    }


@router.get("/stations/{station_id}/areas")
def station_areas(station_id: int, db: Session = Depends(get_db)):
    """Area pengamatan Activity di satu stasiun: iklan, tenant, keramaian, fasilitas.

    Bahan katalog Ad-Space dan Tenant per area. Area dibentuk dari pengelompokan
    titik Activity yang berdekatan - lihat services/station_areas.py.
    """
    if db.get(Station, station_id) is None:
        raise HTTPException(status_code=404, detail="Stasiun tidak ditemukan")
    return area_stasiun(db, station_id)


@router.get("/sepi/kekokohan")
def sepi_kekokohan(
    db: Session = Depends(get_db),
    minutes: int = Query(default=10, ge=5, le=15),
):
    """Peringkat resmi seluruh stasiun beserta rentang peringkatnya lintas skema."""
    rows = db.execute(
        select(Station.id, Station.name, StationScore.sepi, StationScore.kelas,
               StationScore.rank, StationScore.sensitivity)
        .join(StationScore, StationScore.station_id == Station.id)
        .where(StationScore.minutes == minutes)
        .order_by(StationScore.rank)
    ).all()
    return {
        "minutes": minutes,
        "stasiun": [
            {
                "station_id": r.id,
                "nama": r.name,
                "sepi": r.sepi,
                "kelas": r.kelas,
                "rank": r.rank,
                "sensitivity": r.sensitivity,
            }
            for r in rows
        ],
    }
