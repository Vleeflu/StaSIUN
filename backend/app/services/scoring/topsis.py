"""TOPSIS: peringkat berdasarkan jarak ke titik terbaik dan terburuk.

Gagasannya sederhana. Bayangkan stasiun khayalan yang unggul di semua variabel,
dan satu lagi yang terburuk di semuanya. Stasiun nyata dinilai dari seberapa
dekat ia ke yang pertama sekaligus seberapa jauh dari yang kedua — jadi
keunggulan di satu variabel tidak otomatis menutupi kelemahan di variabel lain.
"""

import math


def topsis(matrix: list[list[float]], weights: list[float]) -> list[float]:
    """Kedekatan tiap baris ke solusi ideal, 0 sampai 1.

    Semua kriteria dianggap benefit: makin besar makin bagus. Belum ada
    variabel SEPI yang sifatnya sebaliknya.
    """
    if not matrix:
        raise ValueError("matriks kosong")

    rows = len(matrix)
    cols = len(matrix[0])

    if len(weights) != cols:
        raise ValueError("jumlah bobot tidak sama dengan jumlah kriteria")

    # Normalisasi vektor: tiap kolom dibagi panjang vektornya, supaya satuan
    # yang berbeda-beda (jumlah toko, luas km persegi) bisa dibandingkan.
    norms = []
    for j in range(cols):
        length = math.sqrt(sum(matrix[i][j] ** 2 for i in range(rows)))
        norms.append(length if length > 0 else 1.0)

    weighted = [
        [weights[j] * matrix[i][j] / norms[j] for j in range(cols)] for i in range(rows)
    ]

    best = [max(weighted[i][j] for i in range(rows)) for j in range(cols)]
    worst = [min(weighted[i][j] for i in range(rows)) for j in range(cols)]

    scores = []
    for i in range(rows):
        to_best = math.sqrt(sum((weighted[i][j] - best[j]) ** 2 for j in range(cols)))
        to_worst = math.sqrt(sum((weighted[i][j] - worst[j]) ** 2 for j in range(cols)))
        span = to_best + to_worst

        # span nol berarti semua stasiun identik di setiap variabel. Tidak ada
        # yang bisa diperingkat, jadi semuanya ditaruh di tengah.
        scores.append(0.5 if span == 0 else to_worst / span)

    return scores
