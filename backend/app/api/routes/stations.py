import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.isochrone import Isochrone
from app.models.score import StationScore
from app.models.station import Station
from app.models.tenant_score import TenantScore
from app.services.scoring.tenant import CATEGORY_LABEL

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

    return {
        "station_id": row.station_id,
        "minutes": row.minutes,
        "sepi": row.sepi,
        "rank": row.rank,
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
            func.ST_AsGeoJSON(Isochrone.area).label("geom"),
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
