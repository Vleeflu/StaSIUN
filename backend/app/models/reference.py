"""Data pendukung di luar ekosistem MAPID.

Empat tabel yang mengisi variabel SEPI tanpa bergantung pada data Activity:
titik minat OSM (variabel U dan komponen supply GapScore), volume penumpang
(variabel T), profil kawasan (variabel U), dan referensi harga (variabel E dan
variabel R pada TSI).

Tiga di antaranya memakai SourceMixin karena PRD hal. 8-9 mewajibkan pencatatan
sumber dan tanggal akses untuk setiap data eksternal. POI tidak memakainya
karena sumbernya selalu sama, yaitu OpenStreetMap, dan jejaknya sudah tersimpan
lewat osm_type + osm_id yang bisa dibuka ulang kapan saja.
"""

from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.geo import SRID_RENDER
from app.models.mixins import SourceMixin, TimestampMixin


class Poi(TimestampMixin, Base):
    """Titik minat di sekitar stasiun, ditarik dari OpenStreetMap."""

    __tablename__ = "poi"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identitas asli di OSM. Dipakai sebagai kunci idempotensi: menarik ulang
    # data yang sama tidak menghasilkan baris ganda, cukup memperbarui isinya.
    osm_type: Mapped[str]
    osm_id: Mapped[int] = mapped_column(BigInteger)

    name: Mapped[str | None]

    # Kategori versi kita sendiri (misal "makanan", "ritel", "kesehatan"),
    # hasil penyeragaman dari tag OSM yang bentuknya beragam. Diindeks karena
    # GapScore menghitung supply per kategori.
    category: Mapped[str] = mapped_column(index=True)

    # Tag OSM mentah, disimpan apa adanya. Kalau nanti aturan penyeragaman
    # kategori berubah, kategorinya bisa dihitung ulang dari sini tanpa perlu
    # menarik ulang seluruh data dari Overpass.
    osm_tags: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("osm_type", "osm_id", name="uq_poi_osm"),)


class PassengerVolume(SourceMixin, TimestampMixin, Base):
    """Volume penumpang per stasiun. Dasar variabel T dan estimasi paparan."""

    __tablename__ = "passenger_volume"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )

    # Periode data, ditulis sebagai teks supaya bisa menampung dua ketelitian
    # yang berbeda: "2025" untuk data tahunan, "2025-06" untuk data bulanan.
    # Sumber sekunder jarang seragam soal ini.
    period: Mapped[str]

    passengers_per_day: Mapped[float]

    __table_args__ = (
        # Sumber ikut jadi kunci: dua sumber berbeda boleh melaporkan angka
        # berbeda untuk periode yang sama, dan keduanya berhak disimpan.
        UniqueConstraint(
            "station_id", "period", "source", name="uq_passenger_volume_station_period"
        ),
    )


class AreaProfile(SourceMixin, TimestampMixin, Base):
    """Profil kawasan di sekitar stasiun: perkantoran, hunian, atau campuran.

    PRD hal. 10 menegaskan karakterisasi pengunjung disusun dari profil kawasan
    dan pola keramaian antar-rentang waktu, bukan dari penilaian penampilan
    orang. Tabel inilah sisi "profil kawasan"-nya.
    """

    __tablename__ = "area_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), index=True
    )

    # "perkantoran", "hunian", atau "campuran".
    profile: Mapped[str]

    # Porsi tiap fungsi lahan, 0-1, kalau sumbernya memang memberi angka.
    # Boleh kosong: sebagian sumber hanya memberi label tanpa proporsi.
    office_share: Mapped[float | None]
    residential_share: Mapped[float | None]

    __table_args__ = (
        UniqueConstraint("station_id", "source", name="uq_area_profile_station_source"),
    )


class PriceReference(SourceMixin, TimestampMixin, Base):
    """Harga menu dan harga sewa hasil riset sumber terbuka.

    Menggantikan jalur OCR yang dikeluarkan dari lingkup PRD. Karena angkanya
    tidak diukur sendiri di lapangan, sumber dan tanggal aksesnya adalah bagian
    dari datanya, bukan pelengkap — itu sebabnya kolom itu wajib lewat
    SourceMixin.
    """

    __tablename__ = "price_references"

    id: Mapped[int] = mapped_column(primary_key=True)

    # "menu" untuk harga makanan/minuman, "sewa" untuk listing ruang komersial.
    kind: Mapped[str] = mapped_column(index=True)

    # Kategori usaha, dipakai untuk mengagregasi harga pada tingkat klaster
    # tenant sesuai PRD hal. 12, bukan pada tingkat tenant satuan.
    category: Mapped[str] = mapped_column(index=True)

    item_name: Mapped[str | None]

    # Numeric, bukan float. Uang tidak boleh disimpan sebagai bilangan pecahan
    # biner karena pembulatannya menumpuk; Numeric menyimpan angka desimal
    # persis seperti tertulis.
    price_idr: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    # Satuan harganya, misal "per porsi" atau "per m2 per bulan". Tanpa ini
    # dua angka yang tidak sebanding bisa ikut dirata-ratakan.
    unit: Mapped[str]

    # Boleh kosong: sebagian referensi harga terikat ke satu stasiun, sebagian
    # lagi berlaku untuk kawasan yang lebih luas.
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="SET NULL"), index=True
    )
    location: Mapped[str | None] = mapped_column(
        Geometry("POINT", srid=SRID_RENDER, spatial_index=True)
    )
