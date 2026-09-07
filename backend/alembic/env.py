"""Penyambung Alembic ke aplikasi.

Dua hal yang perlu diketahui sebelum mengubah berkas ini:

1. URL database dibaca dari app.core.config.settings, bukan dari alembic.ini,
   supaya kredensial cukup ditulis sekali di .env.
2. PostGIS menaruh tabel dan indeks internalnya di database yang sama
   (spatial_ref_sys dan kawan-kawan). Tanpa penyaringan di include_object,
   autogenerate akan mengusulkan penghapusan tabel-tabel itu. Indeks spasial
   juga disaring karena GeoAlchemy2 membuatnya sendiri lewat event DDL, jadi
   kalau ikut ditulis ke migrasi hasilnya indeks ganda.
"""

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import Geometry
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base

# Impor seluruh model supaya tabelnya terdaftar di Base.metadata. Cukup satu
# baris: pendaftaran berkas per berkas dilakukan di app/models/__init__.py,
# jadi berkas ini tidak perlu diubah lagi setiap ada model baru.
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if not settings.DATABASE_URL:
    raise RuntimeError("DATABASE_URL belum diisi, Alembic tidak tahu harus menyambung ke mana.")

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata

# Tabel bawaan PostGIS. Bukan milik kita, jangan pernah ikut dimigrasikan.
POSTGIS_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
}

# Nama kolom geometri yang dipakai di seluruh model. Dipakai sebagai cadangan
# pengenalan indeks spasial saat tipe kolomnya tidak terbaca — lihat
# _is_spatial_index di bawah. Tambahkan di sini kalau ada nama kolom baru.
GEOMETRY_COLUMN_NAMES = {"location", "geom", "origin_point"}


def _is_spatial_index(object_, name) -> bool:
    """Apakah indeks ini dibuat sendiri oleh GeoAlchemy2?

    GeoAlchemy2 membuat indeks spasialnya lewat event DDL saat tabel dibuat,
    dengan pola nama idx_<tabel>_<kolom>. Kalau indeks itu ikut ditulis ke
    berkas migrasi, hasilnya indeks ganda dan migrasinya gagal.

    Pengenalannya dua lapis. Lapis pertama memeriksa tipe kolomnya: kalau ada
    kolom bertipe Geometry, itu pasti indeks spasial. Lapis kedua memeriksa
    nama, dipakai untuk indeks hasil refleksi dari database yang tipenya
    tidak selalu terbaca sebagai Geometry.
    """
    if not name or not name.startswith("idx_"):
        return False

    columns = getattr(object_, "columns", None)
    if columns is not None:
        for column in columns:
            if isinstance(getattr(column, "type", None), Geometry):
                return True

    return any(name.endswith(f"_{column}") for column in GEOMETRY_COLUMN_NAMES)


def include_object(object_, name, type_, reflected, compare_to):
    """Menyaring objek mana yang boleh masuk ke berkas migrasi.

    Aturan pertama yang paling penting: tabel atau indeks yang dibaca dari
    database tetapi tidak punya padanan di model kita BUKAN milik kita, jadi
    jangan pernah diusulkan untuk dihapus.

    Ini bukan kehati-hatian berlebihan. Image postgis/postgis memasang ekstensi
    postgis_tiger_geocoder yang membawa 36 tabel geocoder ke database yang
    sama. Tanpa aturan ini, autogenerate pertama menghasilkan 42 op.drop_table
    dan menjalankannya akan membongkar ekstensi PostGIS-nya.

    Konsekuensi yang harus diketahui: kalau suatu saat sebuah model memang
    sengaja dihapus, autogenerate tidak akan membuatkan drop_table-nya. Itu
    ditulis manual — sedikit repot, tetapi jauh lebih murah daripada risiko
    kehilangan tabel yang tidak diniatkan.
    """
    if type_ in ("table", "index") and reflected and compare_to is None:
        return False

    if type_ == "table" and name in POSTGIS_TABLES:
        return False

    if type_ == "index" and _is_spatial_index(object_, name):
        return False

    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
        compare_type=True,
        compare_server_default=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            # Dua pembanding ini mati secara bawaan, dan matinya tidak
            # menghasilkan error apa pun — autogenerate hanya menghasilkan
            # migrasi kosong seolah tidak ada yang berubah.
            #   compare_type          : perubahan tipe kolom
            #   compare_server_default: perubahan nilai bawaan sisi database
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
