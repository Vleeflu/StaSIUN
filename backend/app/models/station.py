from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.geo import SRID_RENDER


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    # Kode resmi KAI, misal MRI buat Manggarai. Ada di sebagian besar stasiun.
    code: Mapped[str | None]
    types: Mapped[list[str]] = mapped_column(ARRAY(String))
    lines: Mapped[list[str]] = mapped_column(ARRAY(String))
    # False buat stasiun yang cuma dilewati KRL tanpa berhenti, contohnya Gambir.
    served: Mapped[bool] = mapped_column(default=True)
    address: Mapped[str | None]
    kecamatan: Mapped[str | None]
    kabkot: Mapped[str | None]
    # spatial_index dieksplisitkan, bukan diandalkan ke default GeoAlchemy2:
    # PRD menjadikan indeks GiST syarat performa kueri kedekatan, jadi jangan
    # sampai hilang diam-diam kalau defaultnya berubah.
    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )
