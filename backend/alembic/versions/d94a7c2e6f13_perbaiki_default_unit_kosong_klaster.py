"""Kolom unit_filled/unit_empty di tenant_clusters jadi nullable, bersihkan (0,0) palsu.

Ditemukan 13 Sep dari laporan Villyan: Kalideres dan Jakarta Kota punya data
tenant di Activity yang tidak muncul di E, karena narasi "dari sepuluh unit,
dua minimarket, satu restoran, sisanya makanan" adalah laporan AREA, bukan
daftar tenant bernama. Skema ekstraksi sudah menampung ini lewat field "lapak",
tetapi kolom `unit_filled`/`unit_empty` sebelumnya default 0, bukan NULL,
sehingga "terisi tidak disebutkan" tertulis sama persis dengan "nol terisi" -
kebalikan dari makna narasinya.

Baris (unit_filled=0, unit_empty=0) dengan unit_total > 0 adalah gejala pasti
dari bug ini: nol terisi DAN nol kosong dari sepuluh unit tidak mungkin benar
sebagai observasi. Baris itu dikosongkan ke NULL, bukan ditebak angkanya -
prinsip yang sama dipakai di seluruh sistem ini untuk data yang tidak disebut.

Revision ID: d94a7c2e6f13
Revises: c3f5e8a1d624
"""

from alembic import op

revision = "d94a7c2e6f13"
down_revision = "c3f5e8a1d624"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tenant_clusters", "unit_filled", nullable=True, server_default=None)
    op.alter_column("tenant_clusters", "unit_empty", nullable=True, server_default=None)

    # Bersihkan baris yang jelas kena bug: (0, 0) padahal total > 0. Baris
    # yang benar-benar terisi 0 dari total kecil (mis. total=1) tidak
    # tersentuh kondisi ini karena ambiguitasnya sama - tetap dikosongkan demi
    # konsistensi, karena kita tidak bisa membedakan "dilaporkan kosong semua"
    # dari "tidak disebutkan" pada data historis ini.
    op.execute(
        """
        UPDATE tenant_clusters
           SET unit_filled = NULL, unit_empty = NULL
         WHERE unit_filled = 0 AND unit_empty = 0 AND unit_total > 0
        """
    )


def downgrade() -> None:
    op.execute("UPDATE tenant_clusters SET unit_filled = 0 WHERE unit_filled IS NULL")
    op.execute("UPDATE tenant_clusters SET unit_empty = 0 WHERE unit_empty IS NULL")
    op.alter_column("tenant_clusters", "unit_filled", nullable=False, server_default="0")
    op.alter_column("tenant_clusters", "unit_empty", nullable=False, server_default="0")
