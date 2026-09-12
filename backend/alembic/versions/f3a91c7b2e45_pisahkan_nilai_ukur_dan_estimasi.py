"""Pisahkan nilai hasil ukur dari nilai yang dipakai skor.

MASALAH YANG DIPERBAIKI
----------------------
`station_scores.raw_e` dan `raw_c` selama ini diisi nilai HASIL UKUR
(`detail["ukur_e"]`), sehingga NULL untuk 38 dari 45 stasiun. Panel lalu
menulis "belum diukur" dan "3 dari 5 variabel".

Padahal skornya TIDAK dihitung dari tiga variabel. `scoring/matrix.py` memakai
nilai setelah shrinkage - mekanisme PRD hal. 15 - sehingga stasiun tanpa survey
tetap mendapat estimasi rata-rata arketipenya, dan peringkat antar-stasiun tetap
sebanding. Yang keliru hanya apa yang disimpan dan ditampilkan.

Bedanya menentukan cara orang membaca peringkat. "Skor 67,7 dari 3 variabel"
terdengar seperti angka yang kurang bahan, dan itu keliru. Yang benar: "skor
67,7 dari 5 variabel, dua di antaranya estimasi" - lengkap, dan kejujurannya
justru pada penandaan estimasinya.

Empat kolom ditambahkan:
  ukur_e, ukur_c   nilai HASIL UKUR, NULL kalau stasiunnya belum disurvey
  e_terukur        apakah E berasal dari pengukuran atau estimasi
  c_terukur        idem untuk C

`raw_e` dan `raw_c` mulai sekarang diisi nilai yang BENAR-BENAR dipakai skor,
sesuai namanya.

Revision ID: f3a91c7b2e45
Revises: e2c47b9a1d38
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3a91c7b2e45"
down_revision = "e2c47b9a1d38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("station_scores", sa.Column("ukur_e", sa.Float(), nullable=True))
    op.add_column("station_scores", sa.Column("ukur_c", sa.Float(), nullable=True))
    op.add_column(
        "station_scores",
        sa.Column("e_terukur", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "station_scores",
        sa.Column("c_terukur", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Nilai lama `raw_e`/`raw_c` sebenarnya hasil ukur - pindahkan ke kolom yang
    # namanya benar, supaya skor yang sudah tersimpan tidak salah dibaca sampai
    # compute_sepi dijalankan ulang.
    op.execute(
        "UPDATE station_scores SET ukur_e = raw_e, ukur_c = raw_c, "
        "e_terukur = (raw_e IS NOT NULL), c_terukur = (raw_c IS NOT NULL)"
    )


def downgrade() -> None:
    op.drop_column("station_scores", "c_terukur")
    op.drop_column("station_scores", "e_terukur")
    op.drop_column("station_scores", "ukur_c")
    op.drop_column("station_scores", "ukur_e")
