"""rentang skala per penilaian keramaian

Revision ID: 7a4e2c9d1f53
Revises: 5c1d9a7b3e20
Create Date: 2026-09-12 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a4e2c9d1f53"
down_revision: Union[str, None] = "5c1d9a7b3e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Activity universal tidak selalu memakai skala 1-5 ("3 dari 3", "7 dari
    # 10"). Menyimpan rentangnya bersama angka membuat normalisasi
    # (rating - min) / (max - min) bisa dilakukan tanpa menebak (ADJUSTMENT 9.32).
    # Baris lama seluruhnya berskala 1-5, jadi nilai bawaan tepat untuk mereka.
    op.add_column(
        "crowd_ratings",
        sa.Column("scale_min", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "crowd_ratings",
        sa.Column("scale_max", sa.Integer(), nullable=False, server_default=sa.text("5")),
    )
    op.drop_constraint("ck_crowd_rating_range", "crowd_ratings", type_="check")
    op.create_check_constraint(
        "ck_crowd_rating_range", "crowd_ratings", "rating BETWEEN scale_min AND scale_max"
    )
    op.create_check_constraint(
        "ck_crowd_rating_scale",
        "crowd_ratings",
        "scale_min IN (0, 1) AND scale_max BETWEEN 3 AND 10",
    )


def downgrade() -> None:
    op.drop_constraint("ck_crowd_rating_scale", "crowd_ratings", type_="check")
    op.drop_constraint("ck_crowd_rating_range", "crowd_ratings", type_="check")
    op.execute("DELETE FROM crowd_ratings WHERE scale_min <> 1 OR scale_max <> 5")
    op.create_check_constraint(
        "ck_crowd_rating_range", "crowd_ratings", "rating BETWEEN 1 AND 5"
    )
    op.drop_column("crowd_ratings", "scale_max")
    op.drop_column("crowd_ratings", "scale_min")
