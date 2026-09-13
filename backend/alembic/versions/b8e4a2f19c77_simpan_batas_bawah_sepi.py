"""Simpan batas bawah SEPI, angka yang sebenarnya dipakai mengurutkan.

Peringkat SEPI sudah lama diurutkan memakai `nilai_bawah` - skor seandainya
tiap variabel yang diestimasi meleset satu simpangan ke arah merugikan - tetapi
angka itu tidak pernah disimpan. Akibatnya halaman peringkat menampilkan skor
mentah di samping peringkat yang disusun dari angka lain, dan daftarnya terbaca
tidak urut: Sudirman 64,5 duduk di atas Pondok Jati 65,4 tanpa penjelasan apa
pun yang bisa dilihat pembaca.

Revision ID: b8e4a2f19c77
Revises: a7d3f81c5b09
"""

from alembic import op
import sqlalchemy as sa

revision = "b8e4a2f19c77"
down_revision = "a7d3f81c5b09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "station_scores",
        sa.Column("sepi_bawah", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("station_scores", "sepi_bawah")
