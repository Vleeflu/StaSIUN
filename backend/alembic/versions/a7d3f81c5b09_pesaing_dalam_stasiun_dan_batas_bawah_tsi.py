"""Pisahkan pesaing dalam/luar stasiun dan simpan batas bawah TSI.

PRD hal. 13 mewajibkan komponen supply mencakup "titik minat di luar stasiun
maupun tenant yang telah beroperasi di dalam stasiun". Selama ini hanya sisi
luar yang terhitung. Menambah sisi dalam menimbulkan masalah baru: survei
lapangan hanya mencakup 14 dari 45 stasiun, jadi 31 stasiun lain akan tampak
tidak punya pesaing dalam stasiun padahal sebetulnya belum diperiksa.

Karena itu sisi dalam disimpan terpisah dari sisi luar, lengkap dengan penanda
apakah ia terukur atau diestimasi, dan TSI mendapat batas bawah - skor
seandainya estimasi itu meleset ke arah yang merugikan. Peringkat memakai batas
bawah, sehingga stasiun yang datanya belum lengkap tidak bisa menang hanya
karena pesaingnya belum sempat dihitung.

Revision ID: a7d3f81c5b09
Revises: f3a91c7b2e45
"""

from alembic import op
import sqlalchemy as sa

revision = "a7d3f81c5b09"
down_revision = "f3a91c7b2e45"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Server default dipasang supaya baris lama tetap valid saat kolomnya
    # ditambahkan; skor berikutnya menulis nilainya sendiri.
    op.add_column(
        "tenant_scores",
        sa.Column("supply_luar", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenant_scores",
        sa.Column("supply_dalam", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenant_scores",
        sa.Column("dalam_terukur", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "tenant_scores",
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "tenant_scores",
        sa.Column("tsi_bawah", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    for kolom in (
        "tsi_bawah",
        "confidence",
        "dalam_terukur",
        "supply_dalam",
        "supply_luar",
    ):
        op.drop_column("tenant_scores", kolom)
