import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.station import Station

router = APIRouter(tags=["stations"])


@router.get("/stations")
def list_stations(
    db: Session = Depends(get_db),
    service_type: str | None = Query(default=None, alias="type"),
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
                    # Dua nilai skalar ini disiapkan di sini karena MapLibre
                    # mengubah properti array jadi string di dalam worker-nya.
                    "primary_line": r.lines[0] if r.lines else None,
                    "is_interchange": len(r.lines) > 1,
                    # Stasiun non-KRL tidak punya lin, jadi ikon dan warnanya
                    # jatuh ke nama jaringannya.
                    "line_key": "-".join(r.lines) if r.lines else (r.types[0] if r.types else "none"),
                    "served": r.served,
                    "kecamatan": r.kecamatan,
                    "address": r.address,
                },
            }
            for r in rows
        ],
    }
