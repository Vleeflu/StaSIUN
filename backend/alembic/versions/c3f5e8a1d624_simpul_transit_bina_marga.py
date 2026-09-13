"""Simpul transit jalan: halte BRT, halte non-BRT, dan terminal bus.

Sumbernya shapefile Dinas Bina Marga dan data terminal yang diberikan Pak Fabian,
sudah dikonversi sekali dari UTM 48S ke WGS84 menjadi
`data/simpul_transit.geojson`.

KENAPA TABEL SENDIRI, BUKAN TABEL `poi`
----------------------------------------
Tabel `poi` dibaca oleh banyak kueri yang tidak menyaring sumber pada baris yang
sama: variabel U, calon pelanggan TSI, calon sponsor, dan hitungan profil
pengunjung. Memasukkan 1.202 halte ke sana akan menggelembungkan semuanya secara
diam-diam, dan tidak ada satu pun yang akan melempar galat. Tabel terpisah
membuat satu-satunya pembacanya adalah indikator konektivitas antarmoda.

KENAPA DATANYA DIMUAT DI MIGRASI
---------------------------------
Container backend menjalankan `alembic upgrade head` otomatis saat start. Dengan
memuat data di sini, server produksi terisi sendiri pada penempatan berikutnya
tanpa ada yang perlu mengingat skrip impor terpisah. Datanya referensi statis
(lokasi halte), bukan data hasil hitungan, jadi aman diperlakukan sebagai
bagian dari skema.

Revision ID: c3f5e8a1d624
Revises: b8e4a2f19c77
"""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "c3f5e8a1d624"
down_revision = "b8e4a2f19c77"
branch_labels = None
depends_on = None

BERKAS = Path(__file__).resolve().parents[2] / "data" / "simpul_transit.geojson"


def upgrade() -> None:
    op.create_table(
        "transit_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        # halte_brt | halte_non_brt | terminal_bus
        sa.Column("jenis", sa.String(), nullable=False, index=True),
        sa.Column("nama", sa.String()),
        # Isi kolom JENIS_HALT apa adanya, untuk audit pengelompokan di atas.
        sa.Column("jenis_asli", sa.String()),
        sa.Column("sumber", sa.String(), nullable=False),
        sa.Column(
            "location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
            nullable=False,
        ),
    )

    if not BERKAS.exists():
        # Tabel tetap dibuat supaya skema konsisten; tanpa berkasnya konektivitas
        # jalan hanya bersandar pada OpenStreetMap seperti sebelumnya.
        return

    fitur = json.loads(BERKAS.read_text(encoding="utf-8"))["features"]
    tabel = sa.table(
        "transit_nodes",
        sa.column("jenis", sa.String),
        sa.column("nama", sa.String),
        sa.column("jenis_asli", sa.String),
        sa.column("sumber", sa.String),
        sa.column("location", Geometry("POINT", srid=4326)),
    )
    op.bulk_insert(
        tabel,
        [
            {
                "jenis": f["properties"]["jenis"],
                "nama": f["properties"].get("nama"),
                "jenis_asli": f["properties"].get("jenis_asli"),
                "sumber": f["properties"]["sumber"],
                "location": "SRID=4326;POINT({} {})".format(*f["geometry"]["coordinates"]),
            }
            for f in fitur
        ],
    )


def downgrade() -> None:
    op.drop_table("transit_nodes")
