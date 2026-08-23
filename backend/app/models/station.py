from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    types: Mapped[list[str]] = mapped_column(ARRAY(String))
    lines: Mapped[list[str]] = mapped_column(ARRAY(String))
    address: Mapped[str | None]
    kecamatan: Mapped[str | None]
    kabkot: Mapped[str | None]
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326))
