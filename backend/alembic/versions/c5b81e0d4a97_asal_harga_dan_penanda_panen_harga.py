"""Asal-usul harga dan penanda panen harga.

Dua kolom, satu tujuan: membuat harga yang dipanen dari narasi bisa ditelusuri
dan bisa dipanen ulang tanpa menggandakan baris.

`price_references.activity_point_id` menyamakan tabel ini dengan saudaranya -
`ad_spots` dan `tenants` sudah menyimpan titik Activity asalnya. Tanpa itu,
sebuah harga Rp15.000 di sebuah stasiun tidak bisa dilacak kembali ke kalimat
yang menyebutkannya, dan panen ulang tidak punya cara menghapus hasil lamanya.
Kolomnya boleh NULL, karena benchmark hasil riset pasar memang tidak berasal
dari narasi mana pun.

`activity_points.llm_harga_at` adalah penanda "sudah dipanen harganya". Ia
dibutuhkan terpisah dari `llm_ec_at` karena 201 narasi terlanjur diekstrak
sebelum skema memuat bagian harga - 45 di antaranya menyebut angka rupiah.
Tanpa penanda sendiri, narasi yang memang tidak menyebut harga akan dipanen
berulang kali setiap perintah dijalankan, membakar kuota untuk hasil kosong.

Revision ID: c5b81e0d4a97
Revises: 7a4e2c9d1f53
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5b81e0d4a97"
down_revision = "7a4e2c9d1f53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "price_references",
        sa.Column("activity_point_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_price_references_activity_point_id",
        "price_references",
        ["activity_point_id"],
    )
    op.create_foreign_key(
        "price_references_activity_point_id_fkey",
        "price_references",
        "activity_points",
        ["activity_point_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "activity_points",
        sa.Column("llm_harga_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activity_points", "llm_harga_at")
    op.drop_constraint(
        "price_references_activity_point_id_fkey", "price_references", type_="foreignkey"
    )
    op.drop_index("ix_price_references_activity_point_id", table_name="price_references")
    op.drop_column("price_references", "activity_point_id")
