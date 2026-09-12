"""penanda ekstraksi LLM per titik dan hasil analisis sensitivitas per skor

Revision ID: 5c1d9a7b3e20
Revises: 2fe9c7b6304b
Create Date: 2026-09-12 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "5c1d9a7b3e20"
down_revision: Union[str, None] = "2fe9c7b6304b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sebelum revisi ini, "sudah diekstrak" disimpulkan dari ada-tidaknya baris
    # hasil di ad_spots/tenants/facility_issues. Narasi yang dibaca model tetapi
    # memang tidak memuat apa pun karena itu diproses ULANG setiap kali skrip
    # dijalankan - membakar kuota penyedia model untuk jawaban yang sama.
    op.add_column(
        "activity_points",
        sa.Column("llm_ec_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Pass terpisah untuk kondisi fasilitas (positif maupun negatif). Skema
    # ekstraksi pertama hanya meminta KELUHAN, sehingga indeks sentimen pasti
    # negatif - PRD Tabel 7 meminta "teks keluhan dan catatan kondisi fasilitas".
    op.add_column(
        "activity_points",
        sa.Column("llm_fasilitas_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Titik yang sudah menghasilkan baris jelas pernah diproses skema pertama.
    op.execute(
        """
        UPDATE activity_points ap SET llm_ec_at = now()
         WHERE EXISTS (SELECT 1 FROM ad_spots a WHERE a.activity_point_id = ap.id)
            OR EXISTS (SELECT 1 FROM tenants t WHERE t.activity_point_id = ap.id)
            OR EXISTS (SELECT 1 FROM facility_issues f WHERE f.activity_point_id = ap.id)
        """
    )

    # Hasil analisis sensitivitas peringkat lintas skema pembobotan (B22).
    # JSONB karena isinya ringkasan yang bentuknya bisa bertambah (skema baru,
    # persentil lain) tanpa migrasi.
    op.add_column(
        "station_scores",
        sa.Column("sensitivity", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("station_scores", "sensitivity")
    op.drop_column("activity_points", "llm_fasilitas_at")
    op.drop_column("activity_points", "llm_ec_at")
