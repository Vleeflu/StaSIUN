"""Lapis 1 ekstraksi: Topic Modeling (LDA) atas korpus naratif Activity.

PERAN MENURUT PRD TABEL 7
--------------------------
Masukan   : korpus naratif SELURUH Activity, termasuk dari tim lain.
Keluaran  : arketipe stasiun, yang menentukan profil pembobotan yang dipakai
            "sebab kriteria keberhasilan sebuah kategori usaha berbeda antara
            stasiun perkantoran dan permukiman". Arketipe juga menjadi
            **kelompok pembanding** pada mekanisme shrinkage (F3-7).

KENAPA LDA KLASIK, BUKAN MODEL TRANSFORMER
-------------------------------------------
PRD hal. 16 menulis Topic Modeling "bersifat unsupervised sehingga tidak
memerlukan data berlabel", dan menegaskan tim tidak melatih model dari awal.
LDA di scikit-learn memenuhi keduanya apa adanya.

Pertimbangan kedua bersifat operasional dan sama menentukan: image backend
sekarang 709 MB, sementara rencana deploy bertumpu pada free tier. Menambahkan
torch + transformers membawanya ke sekitar 3 GB dan membuat rencana itu gugur.
scikit-learn hanya menambah 47 MB karena numpy dan scipy sudah ada.

BATAS YANG TIDAK BOLEH DILUPAKAN
---------------------------------
PRD hal. 16: output model berbasis teks adalah **modifier dengan kontribusi
maksimal 15 persen** terhadap skor akhir, dan **wajib melalui validasi silang
spasial**. Alasannya ditulis PRD sendiri: "agar output utama produk tetap
bertumpu pada indikator terukur, bukan pada interpretasi teks."

Modul ini karena itu HANYA menghasilkan label arketipe dan sebaran topiknya.
Ia tidak menyentuh skor sama sekali. Penerapan pembatas 15 persen dikerjakan di
mesin skor, bukan di sini.

SOAL MEMILIH JUMLAH TOPIK
--------------------------
Jumlah topik adalah parameter bebas, dan proyek ini sudah pernah tertipu sekali
dengan memilih parameter berdasarkan skor yang paling bagus (M15, overfitting).
Karena itu bawaannya dipilih **secara konseptual**: PRD mencontohkan perbedaan
"stasiun perkantoran dan permukiman", dan survei lapangan menyentuh koridor,
peron, lapak, keluhan fasilitas, serta konektivitas. Lima topik cukup untuk
memisahkan itu tanpa memecah korpus 1.034 dokumen jadi terlalu tipis.

Nilai perplexity tetap dilaporkan supaya bisa diperiksa, TETAPI bukan sebagai
dasar pemilihan.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import numpy as np
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from sqlalchemy import text
from sqlalchemy.orm import Session

# Stopword Bahasa Indonesia, ditulis di sini alih-alih menambah satu dependensi
# lagi hanya untuk sebuah daftar kata. Ditambah kata-kata yang muncul di hampir
# setiap narasi survey ("stasiun", "pengamatan", "terlihat") — kata yang ada di
# mana-mana tidak memisahkan apa pun dan justru mendominasi tiap topik.
STOPWORD = {
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "pada", "untuk", "dengan",
    "ada", "tidak", "juga", "sudah", "saya", "kami", "akan", "atau", "sebagai",
    "dalam", "oleh", "karena", "bisa", "lebih", "masih", "saat", "para", "pun",
    "adalah", "sangat", "hanya", "tetapi", "namun", "sehingga", "agar", "bagi",
    "banyak", "sekitar", "cukup", "beberapa", "seperti", "antara", "setiap",
    "tersebut", "kondisi", "terdapat", "merupakan", "dapat", "selain", "serta",
    "kalau", "jika", "maka", "yaitu", "yakni", "bahwa", "telah", "belum",
    "menurut", "berdasarkan", "informasi", "sedangkan", "hingga", "sampai",
    # Kata yang muncul di hampir semua entri survey:
    "stasiun", "pengamatan", "mengamati", "terlihat", "tampak", "pukul",
    "orang", "area", "tingkat", "waktu", "hari", "pagi", "siang", "sore",
}

# Ambang kemunculan. Kata yang cuma muncul di satu-dua dokumen tidak membentuk
# topik, ia cuma menambah derau; kata yang muncul di lebih dari separuh korpus
# ada di mana-mana sehingga tidak memisahkan apa pun.
MIN_DOKUMEN = 3
MAKS_PROPORSI = 0.5

JUMLAH_TOPIK_BAWAAN = 5
KATA_PER_TOPIK = 8


@dataclass
class HasilArketipe:
    dokumen: int = 0
    topik: int = 0
    perplexity: float | None = None
    kata_kunci: dict[int, list[str]] = field(default_factory=dict)
    per_stasiun: dict[str, str] = field(default_factory=dict)
    tersimpan: int = 0


def _bersihkan(teks: str) -> str:
    """Buang tagar, URL, dan angka sebelum pemodelan.

    Tagar dibuang karena ia menandai TIM, bukan isi. Membiarkannya akan membuat
    LDA menemukan "topik" yang sebenarnya cuma pengelompokan per tim — persis
    kebalikan dari universalitas yang PRD minta.
    """
    teks = re.sub(r"#\w+", " ", teks)
    teks = re.sub(r"https?://\S+", " ", teks)
    teks = re.sub(r"\d+", " ", teks)
    return teks.lower()


def hitung_arketipe(
    session: Session,
    jumlah_topik: int = JUMLAH_TOPIK_BAWAAN,
    seed: int = 42,
) -> HasilArketipe:
    """Latih LDA atas seluruh narasi Activity, lalu beri label tiap titik.

    `seed` dikunci supaya hasilnya bisa direproduksi. LDA punya komponen acak;
    tanpa seed tetap, arketipe sebuah stasiun bisa berubah antar-jalan tanpa
    satu pun datanya berubah — dan itu akan sangat membingungkan saat ditanya.
    """
    hasil = HasilArketipe(topik=jumlah_topik)

    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, s.name AS station_name, ap.narrative
              FROM activity_points ap
              LEFT JOIN stations s ON s.id = ap.station_id
             WHERE ap.narrative IS NOT NULL AND length(ap.narrative) > 0
             ORDER BY ap.id
            """
        )
    ).all()

    if len(baris) < jumlah_topik * 5:
        raise RuntimeError(
            f"korpus cuma {len(baris)} dokumen, terlalu sedikit untuk "
            f"{jumlah_topik} topik. Tarik dan parse Activity dulu."
        )

    korpus = [_bersihkan(r.narrative) for r in baris]
    hasil.dokumen = len(korpus)

    vectorizer = CountVectorizer(
        stop_words=list(STOPWORD),
        min_df=MIN_DOKUMEN,
        max_df=MAKS_PROPORSI,
        token_pattern=r"(?u)\b[a-z]{4,}\b",
    )
    matriks = vectorizer.fit_transform(korpus)

    lda = LatentDirichletAllocation(
        n_components=jumlah_topik,
        random_state=seed,
        learning_method="batch",
        max_iter=30,
    )
    sebaran = lda.fit_transform(matriks)
    hasil.perplexity = float(lda.perplexity(matriks))

    kosakata = np.array(vectorizer.get_feature_names_out())
    for i, komponen in enumerate(lda.components_):
        teratas = komponen.argsort()[: -KATA_PER_TOPIK - 1 : -1]
        hasil.kata_kunci[i] = kosakata[teratas].tolist()

    # Simpan sebaran topik per titik. Label arketipe ditulis sebagai nomor
    # topik plus kata kuncinya, bukan nama karangan seperti "perkantoran" -
    # menamai topik adalah tafsir manusia, dan menaruhnya di database membuat
    # tafsir itu terlihat seperti temuan.
    for r, prob in zip(baris, sebaran):
        dominan = int(np.argmax(prob))
        session.execute(
            text(
                """
                INSERT INTO activity_extractions
                    (activity_point_id, archetype, archetype_probs,
                     spatially_validated, model_versions, created_at, updated_at)
                VALUES
                    (:pid, :arketipe, CAST(:probs AS jsonb),
                     false, CAST(:versi AS jsonb), now(), now())
                """
            ),
            {
                "pid": r.id,
                "arketipe": f"topik_{dominan}",
                "probs": json.dumps(
                    {f"topik_{i}": round(float(p), 4) for i, p in enumerate(prob)}
                ),
                "versi": json.dumps(
                    {"model": "sklearn.LatentDirichletAllocation",
                     "n_components": jumlah_topik, "seed": seed}
                ),
            },
        )
        hasil.tersimpan += 1

    # Arketipe per stasiun: topik yang paling sering dominan di titik-titiknya.
    # Diambil modus, bukan rata-rata sebaran - rata-rata akan menghasilkan
    # profil campuran yang tidak sesuai dengan satu pun topik nyata.
    per_stasiun: dict[str, list[int]] = {}
    for r, prob in zip(baris, sebaran):
        if r.station_name:
            per_stasiun.setdefault(r.station_name, []).append(int(np.argmax(prob)))
    for nama, topik in per_stasiun.items():
        hasil.per_stasiun[nama] = f"topik_{max(set(topik), key=topik.count)}"

    session.commit()
    return hasil
