"""Mesin skor SEPI.

Alurnya, mengikuti PRD hal. 13:

    indikator mentah
        |  normalize.normalisasi_matriks   -> 0..1 per kolom
        |  normalize.gabung_indikator      -> satu nilai per variabel
        v
    matriks variabel (stasiun x T,E,A,U,C)
        |  weights.bobot_entropy           <- dari variabilitas data
        |  weights.bobot_ahp               <- dari penilaian ahli, CR < 0,10
        |  weights.gabung_bobot            -> w = lam*w_ent + (1-lam)*w_ahp
        v
    bobot
        |  sepi.hitung_sepi                -> skor 0-100 + klasifikasi
        |  topsis.topsis                   -> peringkat relatif
        v
    hasil

Seluruh modul di sini bekerja pada array numpy dan tidak menyentuh database
sama sekali. Itu disengaja: mesin skornya bisa diuji dengan data sintetis tanpa
PostGIS hidup, dan matematikanya bisa diperiksa terpisah dari cara datanya
diambil.
"""

from app.services.scoring.matrix import CRITERIA, build_matrix
from app.services.scoring.normalize import (
    Arah,
    gabung_indikator,
    minmax,
    normalisasi_matriks,
)
from app.services.scoring.sepi import (
    NAMA_VARIABEL,
    VARIABEL,
    SkorSepi,
    hitung_sepi,
    klasifikasi,
)
from app.services.scoring.topsis import HasilTopsis, topsis
from app.services.scoring.uncertainty import (
    Interval,
    estimasi_k,
    interval_bca,
    shrinkage,
)
from app.services.scoring.weights import (
    AHPTidakKonsisten,
    AMBANG_CR,
    bobot_ahp,
    bobot_entropy,
    gabung_bobot,
)

__all__ = [
    "AHPTidakKonsisten",
    "CRITERIA",
    "AMBANG_CR",
    "Arah",
    "HasilTopsis",
    "Interval",
    "NAMA_VARIABEL",
    "SkorSepi",
    "VARIABEL",
    "build_matrix",
    "bobot_ahp",
    "bobot_entropy",
    "gabung_bobot",
    "estimasi_k",
    "gabung_indikator",
    "hitung_sepi",
    "interval_bca",
    "klasifikasi",
    "minmax",
    "normalisasi_matriks",
    "shrinkage",
    "topsis",
]
