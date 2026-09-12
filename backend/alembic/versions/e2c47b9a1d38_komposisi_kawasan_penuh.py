"""Komposisi kawasan penuh, bukan satu label.

`area_profile` sebelumnya hanya menyimpan `profile` (satu kata) beserta
`office_share` dan `residential_share`. Dua kelas lain - niaga dan industri -
ikut dihitung tetapi dibuang sebelum disimpan, dan satu label tunggal
menyembunyikan bahwa "campuran 55/45" dan "campuran 90/10" adalah dua keadaan
yang sangat berbeda.

Kolom `komposisi` menyimpan proporsi SELURUH kelas apa adanya, plus metadata
cara ia dihitung. Label tetap ada sebagai turunan yang gampang dibaca, tetapi
bukan lagi satu-satunya yang tersimpan.

Revision ID: e2c47b9a1d38
Revises: c5b81e0d4a97
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2c47b9a1d38"
down_revision = "c5b81e0d4a97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "area_profile",
        sa.Column(
            "komposisi",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("area_profile", "komposisi")
