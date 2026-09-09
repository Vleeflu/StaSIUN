from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Poi(Base):
    __tablename__ = "pois"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    # Kategori dari katalog, misal "alfamart". Dipakai buat pelaporan per jenis.
    category: Mapped[str] = mapped_column(String, index=True)
    # Variabel SEPI yang disuapi kategori ini: E, U, atau C.
    variable: Mapped[str] = mapped_column(String(1), index=True)
    kabkot: Mapped[str | None]
    kecamatan: Mapped[str | None]
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
