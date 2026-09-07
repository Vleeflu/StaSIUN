"""Poligon jangkauan berjalan kaki, ditarik dari tools isochrone GeoMAPID.

Alur masuknya dijelaskan di ADJUSTMENT.md bagian 7.6: layer ditarik lewat API
`layers_new/get_layer` oleh skrip importer, tidak pernah dipanggil dari endpoint
yang diakses pengguna. Satu kali generate di GeoMAPID menghasilkan dua layer,
poligon dan titik asal; titik asalnya dipakai untuk mencocokkan tiap poligon ke
stasiun.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.geo import SRID_RENDER
from app.models.mixins import TimestampMixin


class Isochrone(TimestampMixin, Base):
    __tablename__ = "isochrones"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Sengaja boleh kosong. Kalau importer gagal mencocokkan poligon ini ke
    # stasiun mana pun, barisnya tetap disimpan dengan match_method="unmatched"
    # dan bisa diperiksa manual. Data yang hilang tanpa jejak jauh lebih
    # berbahaya daripada data yang ditandai bermasalah.
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )

    # 5, 10, atau 15 menit sesuai PRD hal. 12. Tidak dikunci ke tiga nilai itu
    # lewat constraint supaya durasi lain masih bisa masuk kalau tim
    # membangkitkannya, tetapi tiga itulah yang dipakai perhitungan.
    minutes: Mapped[int]

    # MULTIPOLYGON, bukan POLYGON: hasil isochrone bisa terpecah jadi beberapa
    # kepingan terpisah kalau ada penghalang seperti rel atau sungai. Poligon
    # tunggal dinormalkan dengan ST_Multi saat diimpor supaya tipenya seragam.
    geom: Mapped[str] = mapped_column(
        Geometry("MULTIPOLYGON", srid=SRID_RENDER, spatial_index=True)
    )

    # Titik asal isochrone, berasal dari layer point pasangannya. Ini jangkar
    # pencocokan ke stasiun, jadi disimpan apa adanya untuk bisa diaudit ulang.
    origin_point: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )

    # Luas dalam meter persegi, dihitung setelah diproyeksikan ke EPSG:32748
    # lewat app.core.geo.metric(). Disimpan supaya tidak dihitung ulang di
    # setiap kueri.
    area_m2: Mapped[float | None]

    # Luas isochrone dibagi luas lingkaran setara. Makin kecil, makin besar
    # hambatan fisik yang membatasi jangkauan nyata pejalan kaki.
    permeability_index: Mapped[float | None]

    # Kecepatan berjalan yang dipakai tools GeoMAPID saat membangkitkan poligon
    # ini. Dibutuhkan Permeability Index, karena radius lingkaran pembandingnya
    # = kecepatan x waktu. Kalau tidak diketahui, diisi asumsi dan asumsinya
    # ikut ditampilkan sebagai metadata, bukan disembunyikan.
    walk_speed_kmh: Mapped[float | None]

    # Bagaimana poligon ini dicocokkan ke stasiun: "attribute" (ada atribut
    # eksplisit di layernya), "contains_point" (titik asal jatuh di dalam
    # poligon lalu dicocokkan ke stasiun terdekat), atau "unmatched".
    match_method: Mapped[str | None]
    match_distance_m: Mapped[float | None]

    # Jejak asal-usul: layer mana di GeoMAPID, dan kapan ditarik.
    source_layer_id: Mapped[str | None]
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Satu stasiun hanya boleh punya satu poligon per durasi. Baris yang
        # station_id-nya kosong tidak terkena aturan ini, karena PostgreSQL
        # memperlakukan tiap NULL sebagai nilai yang berbeda — persis yang
        # dibutuhkan supaya banyak baris unmatched tetap bisa disimpan.
        UniqueConstraint("station_id", "minutes", name="uq_isochrone_station_minutes"),
        CheckConstraint("minutes > 0", name="ck_isochrone_minutes_positive"),
    )
