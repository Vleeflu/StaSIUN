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
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base

# Impor seluruh model supaya tabelnya terdaftar di Base.metadata. Tambahkan
# baris baru di sini setiap kali ada berkas model baru, kalau tidak tabelnya
# tidak akan pernah muncul di autogenerate.
import app.models.station  # noqa: F401

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


def include_object(object_, name, type_, reflected, compare_to):
    if type_ == "table" and name in POSTGIS_TABLES:
        return False

    # Indeks spasial dibuat GeoAlchemy2 sendiri saat tabelnya dibuat.
    if type_ == "index" and name and name.startswith("idx_") and name.endswith("_location"):
        return False

    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
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
            # Perubahan tipe kolom tidak terdeteksi tanpa ini.
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
