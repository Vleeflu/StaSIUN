"""Objek di dalam stasiun: zona, tenant, klaster, spot iklan, keluhan fasilitas.

Kelimanya berasal dari survey lapangan lewat Activity, kecuali zona indoor yang
didigitasi manual. Semuanya menunjuk balik ke `activity_points` supaya setiap
baris bisa ditelusuri ke entri survey asalnya — tanpa itu, angka di panel tidak
bisa dipertanggungjawabkan saat ditanya "dari mana ini".
"""

from geoalchemy2 import Geometry
from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.geo import SRID_RENDER
from app.models.mixins import TimestampMixin


class StationZone(TimestampMixin, Base):
    """Poligon zona di dalam stasiun, hasil digitasi manual dari survey.

    PRD menaruh indoor mapping penuh dan routing di dalam gedung DI LUAR
    lingkup. Yang dipetakan hanya batas zona dan keberadaan tenant, bukan jalur
    berjalan — jadi tabel ini sengaja tidak punya kolom topologi atau tetangga.
    """

    __tablename__ = "station_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str]
    # "peron", "concourse", "gerbang", "koridor", atau "lapak".
    zone_type: Mapped[str] = mapped_column(index=True)

    geom: Mapped[str] = mapped_column(
        Geometry("MULTIPOLYGON", srid=SRID_RENDER, spatial_index=True)
    )
    area_m2: Mapped[float | None]

    __table_args__ = (
        UniqueConstraint("station_id", "name", name="uq_station_zone_name"),
    )


class TenantCluster(TimestampMixin, Base):
    """Klaster tenant, satuan analisis ekonomi mikro.

    PRD hal. 12 tegas: analisis dilakukan pada tingkat klaster, bukan pada
    tenant satuan maupun stasiun. Kriteria pembentukannya harus eksplisit —
    kedekatan spasial dalam radius tertentu ditambah kesamaan kategori — dan
    disimpan di kolom radius_m serta criteria_note supaya bisa diaudit, bukan
    jadi keputusan tak tercatat.
    """

    __tablename__ = "tenant_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("station_zones.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str]
    dominant_category: Mapped[str | None]

    unit_total: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    unit_filled: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    unit_empty: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    # Kriteria pembentukan klaster, ditulis apa adanya.
    radius_m: Mapped[float | None]
    criteria_note: Mapped[str | None] = mapped_column(Text)

    geom: Mapped[str | None] = mapped_column(
        Geometry("MULTIPOLYGON", srid=SRID_RENDER, spatial_index=True)
    )


class Tenant(TimestampMixin, Base):
    """Tenant yang sudah beroperasi di dalam stasiun.

    Dua fungsi sekaligus: sisi permintaan untuk profil pembeli, dan sisi
    penawaran pada GapScore — PRD hal. 13 mewajibkan komponen supply mencakup
    tenant di dalam stasiun, supaya kategori yang sebenarnya sudah tersedia
    tidak muncul sebagai kesenjangan semu.

    Rentang harga sengaja TIDAK ada di sini. PRD hal. 9 menyatakan harga tidak
    dicatat di lapangan, melainkan dilengkapi lewat riset sumber terbuka pada
    tahap pengolahan — tempatnya tabel price_references.
    """

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("station_zones.id", ondelete="SET NULL"), index=True
    )
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenant_clusters.id", ondelete="SET NULL"), index=True
    )
    activity_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("activity_points.id", ondelete="SET NULL")
    )

    name: Mapped[str]
    category: Mapped[str] = mapped_column(index=True)
    # "aktif", "tutup", atau "kosong" untuk unit yang tersedia.
    status: Mapped[str] = mapped_column(default="aktif", server_default="aktif")

    # Posisi relatif terhadap gerbang dan peron, sesuai objek survey PRD hal. 9.
    # Jadi bahan komponen visibilitas dan arus pengunjung pada GapScore mikro.
    distance_to_gate_m: Mapped[float | None]
    distance_to_platform_m: Mapped[float | None]

    location: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('aktif', 'tutup', 'kosong')", name="ck_tenant_status"
        ),
    )


class AdSpot(TimestampMixin, Base):
    """Titik media iklan beserta status pemakaiannya.

    Menyumbang ke variabel C pada SEPI (jumlah media terpasang dan statusnya),
    sekaligus jadi objek utama fitur Ad-Space Opportunity.
    """

    __tablename__ = "ad_spots"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("station_zones.id", ondelete="SET NULL"), index=True
    )
    activity_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("activity_points.id", ondelete="SET NULL")
    )

    # "billboard", "digital", "poster", dan sejenisnya.
    media_type: Mapped[str | None]
    media_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))

    # "terpakai" atau "kosong". Rasio keduanya adalah indikator langsung tingkat
    # pemanfaatan ruang iklan sebuah stasiun.
    status: Mapped[str] = mapped_column(default="kosong", server_default="kosong")

    visibility_note: Mapped[str | None] = mapped_column(Text)

    location: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('terpakai', 'kosong')", name="ck_ad_spot_status"
        ),
        CheckConstraint("media_count >= 0", name="ck_ad_spot_media_count"),
    )


class FacilityIssue(TimestampMixin, Base):
    """Keluhan fasilitas yang berpotensi jadi peluang Facility Sponsorship.

    Dua kolom validasi di sini bukan pelengkap. PRD hal. 12 mewajibkan keluhan
    diuji terhadap kondisi spasial, dan keluhan lama divalidasi ulang ke
    pengamatan terkini karena fasilitasnya bisa saja sudah diperbaiki. Keluhan
    yang belum lolos keduanya tidak boleh tampil sebagai penanda di peta.
    """

    __tablename__ = "facility_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("station_zones.id", ondelete="SET NULL"), index=True
    )
    activity_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("activity_points.id", ondelete="SET NULL")
    )

    issue_type: Mapped[str] = mapped_column(index=True)
    description: Mapped[str] = mapped_column(Text)

    # Polaritas dari Sentiment Analysis, jadi penalti kenyamanan pada zona.
    sentiment_score: Mapped[float | None]

    spatially_validated: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )
    validation_note: Mapped[str | None] = mapped_column(Text)

    # Hasil pemeriksaan ulang ke pengamatan terkini. None berarti belum
    # diperiksa — dan itu berbeda dari False, yang berarti sudah diperiksa dan
    # ternyata fasilitasnya sudah diperbaiki.
    still_present: Mapped[bool | None]

    location: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )
