"""Pembobotan variabel SEPI: entropy dari data, AHP dari penilaian ahli.

Keduanya menjawab pertanyaan berbeda. Entropy melihat variabel mana yang paling
membedakan stasiun satu dari lainnya — murni dari sebaran angka, tanpa pendapat
siapa pun. AHP menangkap kepentingan menurut penilaian manusia. Dipakai
berdua supaya skornya tidak sepenuhnya bergantung pada salah satunya.
"""

import math

# Random Index Saaty, dipakai membagi Consistency Index. Nilainya tergantung
# jumlah kriteria, hasil percobaan pada matriks acak.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32}

# Ambang di proposal. Di atas ini perbandingan berpasangannya dianggap saling
# bertentangan — misalnya T lebih penting dari E, E dari C, tapi C dari T.
MAX_CONSISTENCY_RATIO = 0.10


class AhpError(RuntimeError):
    """Raised when the AHP comparison matrix cannot be used."""


def entropy_weights(matrix: list[list[float]]) -> list[float]:
    """Bobot dari sebaran data. Makin merata sebuah kolom, makin kecil bobotnya.

    Kolom yang nilainya sama untuk semua stasiun tidak membantu membedakan apa
    pun, jadi entropinya maksimum dan bobotnya nol.
    """
    if not matrix:
        raise ValueError("matriks kosong")

    rows = len(matrix)
    cols = len(matrix[0])

    if rows < 2:
        raise ValueError("entropy butuh minimal dua baris")

    scale = 1.0 / math.log(rows)
    diversity: list[float] = []

    for j in range(cols):
        column = [matrix[i][j] for i in range(rows)]
        total = sum(column)

        if total <= 0:
            # Kolom kosong sama sekali: tidak membedakan apa-apa.
            diversity.append(0.0)
            continue

        entropy = 0.0
        for value in column:
            share = value / total
            if share > 0:
                entropy -= share * math.log(share)

        diversity.append(1.0 - scale * entropy)

    spread = sum(diversity)
    if spread <= 0:
        # Semua kolom seragam. Tidak ada dasar membedakan, jadi dibagi rata.
        return [1.0 / cols] * cols

    return [d / spread for d in diversity]


def _expand(pairwise: dict[str, dict[str, float]], order: list[str]) -> list[list[float]]:
    """Susun matriks penuh dari separuh atas yang ditulis di berkas."""
    size = len(order)
    full = [[0.0] * size for _ in range(size)]

    for i, row_key in enumerate(order):
        for j, col_key in enumerate(order):
            if i == j:
                full[i][j] = 1.0
                continue

            direct = (pairwise.get(row_key) or {}).get(col_key)
            if direct is not None:
                full[i][j] = float(direct)
                continue

            mirror = (pairwise.get(col_key) or {}).get(row_key)
            if mirror is None:
                raise AhpError(f"perbandingan {row_key} vs {col_key} belum diisi")
            if float(mirror) == 0:
                raise AhpError(f"perbandingan {col_key} vs {row_key} tidak boleh nol")

            full[i][j] = 1.0 / float(mirror)

    return full


def ahp_weights(
    pairwise: dict[str, dict[str, float]], order: list[str]
) -> tuple[list[float], float]:
    """Bobot AHP beserta consistency ratio-nya.

    Bobotnya dihitung lewat rata-rata geometris tiap baris — hampiran vektor
    eigen utama yang lazim dipakai dan tidak butuh pustaka aljabar linear.
    """
    full = _expand(pairwise, order)
    size = len(order)

    means = []
    for row in full:
        product = 1.0
        for value in row:
            if value <= 0:
                raise AhpError("nilai perbandingan harus lebih besar dari nol")
            product *= value
        means.append(product ** (1.0 / size))

    total = sum(means)
    weights = [m / total for m in means]

    # lambda_max: rata-rata (A.w)_i / w_i. Kalau perbandingannya konsisten
    # sempurna, nilainya persis sama dengan jumlah kriteria.
    lambda_max = 0.0
    for i in range(size):
        weighted = sum(full[i][j] * weights[j] for j in range(size))
        lambda_max += weighted / weights[i]
    lambda_max /= size

    if size < 3:
        return weights, 0.0

    consistency_index = (lambda_max - size) / (size - 1)
    random_index = RANDOM_INDEX.get(size)

    if random_index is None:
        raise AhpError(f"tidak ada random index untuk {size} kriteria")

    return weights, consistency_index / random_index


def combine_weights(
    entropy: list[float], ahp: list[float], lambda_entropy: float
) -> list[float]:
    """Padukan kedua bobot, lalu normalkan lagi supaya jumlahnya tepat satu."""
    if not 0.0 <= lambda_entropy <= 1.0:
        raise ValueError("lambda_entropy harus di antara 0 dan 1")

    blended = [
        lambda_entropy * e + (1.0 - lambda_entropy) * a for e, a in zip(entropy, ahp)
    ]
    total = sum(blended)

    return [b / total for b in blended]
