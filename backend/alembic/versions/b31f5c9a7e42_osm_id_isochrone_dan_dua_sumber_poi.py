"""osm_id stasiun, metadata isochrone, dan dua sumber POI

Menyatukan hasil resolusi konflik main <-> adjustment_prd_dimms (10 Sep 2026).
Tiga kelompok perubahan, semuanya sudah diuji lebih dulu terhadap API GEO MAPID
yang sungguhan sebelum migrasi ini ditulis:

1. stations.osm_id
   Kunci sambungan ke poligon isochrone. Nama TIDAK bisa dipakai: "Cawang" dan
   "Halim" masing-masing dipakai dua stasiun dari moda berbeda (osm_id
   2334098791/12260707174 dan 5851224882/9761865798). Terbukti dari data lokal
   sendiri, bukan dugaan.

2. isochrones.station_osm_id / station_name / profile
   Jejak asal-usul, supaya poligon yang tidak ketemu stasiunnya tetap bisa
   ditelusuri. `profile` disimpan karena proyek GEO MAPID memuat layer isochrone
   bernama sama yang sebagian dihitung memakai profil mobil; menyimpannya
   membuat kekeliruan itu ketahuan setelah impor, bukan cuma dicegah sebelumnya.

3. poi.source / poi.fungsi, dan osm_type/osm_id jadi boleh kosong
   Tabel poi sekarang menampung dua sumber. Layer POI MAPID terbukti tidak
   membawa osm_id sama sekali (0 dari 1.714 titik pada layer makanan Jakpus),
   jadi kolomnya harus boleh kosong. `fungsi` memisahkan fungsi lahan dari
   nama layer, supaya "alfamart" dan "indomaret" tidak terhitung sebagai dua
   fungsi lahan berbeda di entropi Shannon.

Revision ID: b31f5c9a7e42
Revises: 0883f21f1e5d
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b31f5c9a7e42"
down_revision: Union[str, None] = "0883f21f1e5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. stasiun ---------------------------------------------------------
    op.add_column("stations", sa.Column("osm_id", sa.String(), nullable=True))
    # Unik sekaligus terindeks. Boleh kosong, dan itu disengaja: PostgreSQL
    # memperlakukan tiap NULL sebagai nilai berbeda, jadi stasiun yang sumbernya
    # tidak membawa osm_id tetap bisa disimpan tanpa saling bertabrakan.
    op.create_index("ix_stations_osm_id", "stations", ["osm_id"], unique=True)

    # --- 2. isochrone -------------------------------------------------------
    op.add_column("isochrones", sa.Column("station_osm_id", sa.String(), nullable=True))
    op.add_column("isochrones", sa.Column("station_name", sa.String(), nullable=True))
    op.add_column("isochrones", sa.Column("profile", sa.String(), nullable=True))
    op.create_index(
        "ix_isochrones_station_osm_id", "isochrones", ["station_osm_id"], unique=False
    )

    # --- 3. titik minat -----------------------------------------------------
    # server_default dipasang supaya 19.792 baris Overpass yang sudah ada ikut
    # tertandai saat kolomnya dibuat. Tanpa itu kolomnya lahir NULL semua dan
    # setiap kueri yang menyaring per sumber diam-diam mengembalikan nol baris.
    op.add_column(
        "poi",
        sa.Column(
            "source", sa.String(), nullable=False, server_default=sa.text("'overpass'")
        ),
    )
    op.create_index("ix_poi_source", "poi", ["source"], unique=False)

    op.add_column("poi", sa.Column("fungsi", sa.String(), nullable=True))
    op.create_index("ix_poi_fungsi", "poi", ["fungsi"], unique=False)

    op.alter_column("poi", "osm_type", existing_type=sa.String(), nullable=True)
    op.alter_column("poi", "osm_id", existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    # Membalik nullable pada poi.osm_type/osm_id akan GAGAL kalau baris MAPID
    # sudah masuk, karena baris itu memang tidak punya nilainya. Barisnya
    # dihapus lebih dulu — aman, karena baris MAPID selalu bisa ditarik ulang
    # dari layernya, sedangkan baris Overpass tidak disentuh sama sekali.
    op.execute("DELETE FROM poi WHERE source = 'mapid'")

    op.alter_column("poi", "osm_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("poi", "osm_type", existing_type=sa.String(), nullable=False)

    op.drop_index("ix_poi_fungsi", table_name="poi")
    op.drop_column("poi", "fungsi")
    op.drop_index("ix_poi_source", table_name="poi")
    op.drop_column("poi", "source")

    op.drop_index("ix_isochrones_station_osm_id", table_name="isochrones")
    op.drop_column("isochrones", "profile")
    op.drop_column("isochrones", "station_name")
    op.drop_column("isochrones", "station_osm_id")

    op.drop_index("ix_stations_osm_id", table_name="stations")
    op.drop_column("stations", "osm_id")
