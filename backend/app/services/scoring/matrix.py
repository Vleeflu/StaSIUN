"""Susun matriks keputusan SEPI dari isi database.

Tiap baris satu stasiun, tiap kolom satu variabel. Angkanya dihitung di dalam
poligon isochrone stasiun itu, bukan lingkaran radius — perbedaan yang penting,
karena rel dan sungai bikin jangkauan jalan kaki jauh dari bundar.

RANCANGAN: berkas ini TIDAK menulis SQL-nya sendiri. Ia memanggil
`indicators.hitung_urban` dan `indicators.hitung_transportasi`. Alasannya bukan
kerapian: pemetaan titik minat ke variabel SEPI adalah tempat salah tafsir PRD
pernah masuk (lihat ADJUSTMENT 8.2), dan menyalin logika itu ke dua tempat
adalah cara paling pasti untuk membuatnya hidup kembali di salah satunya.

E DAN C SENGAJA KOSONG (NaN). PRD Tabel 6 menetapkan keduanya bersumber dari
survey Activity di DALAM stasiun — rentang harga tenant, keterisian lapak,
media iklan terpasang, indeks sentimen fasilitas. Tidak satu pun terbaca dari
titik minat di luar stasiun. Versi sebelumnya mengisinya dengan cacahan POI
`variable IN ('E','C')`, dan itu memberi angka yang terlihat masuk akal untuk
sesuatu yang belum diukur sama sekali.

NaN di sini bukan kegagalan, melainkan pernyataan "belum diukur". `topsis.py`
memperlakukannya sebagai tidak menyumbang jarak, bukan sebagai nol — sebab nol
akan menaruh stasiun di sudut terburuk karena datanya belum masuk, bukan karena
kondisinya memang buruk. Begitu blocker N1 tertutup, dua kolom ini terisi tanpa
mengubah apa pun di sini selain sumbernya.
"""

import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.indicators import hitung_transportasi, hitung_urban

# Urutan kolom. Dipakai juga oleh berkas AHP, jadi keduanya harus sama.
CRITERIA = ["T", "E", "A", "U", "C"]

# Variabel yang sumbernya survey Activity, bukan titik minat. Selama N1 belum
# tertutup, kolomnya NaN.
MENUNGGU_SURVEY = ("E", "C")

# Jaringan yang dinilai. MRT dan LRT tidak ikut diskor — yang dijual KAI adalah
# ruang di stasiunnya sendiri; moda lain masuk hitungan sebagai penyambung.
SCORED_NETWORKS = ("KAI Commuter", "KAI")

SQL_AKSESIBILITAS = text(
    """
    SELECT s.id AS station_id,
           i.area_m2 / 1000000.0 AS area_km2,
           i.permeability_index
      FROM stations s
      JOIN isochrones i ON i.station_id = s.id AND i.minutes = :minutes
     WHERE s.types && CAST(:networks AS varchar[])
    """
)


def _scale(values: list[float]) -> list[float]:
    """Skala 0 sampai 1 dengan membagi nilai tertinggi.

    Sengaja tidak memakai min-max. Entropy kebal terhadap perkalian tapi tidak
    terhadap pergeseran, jadi menggeser nilai terendah ke nol akan menaikkan
    sebaran kolom secara semu — dan bobotnya ikut terkerek, padahal kolom lain
    memakai hitungan mentah. Membagi nilai tertinggi tidak menggeser apa pun,
    sekaligus menjaga perbandingan aslinya: dua lin tetap separuh dari empat.

    Diadopsi apa adanya dari branch main; alasannya benar.
    """
    high = max(values) if values else 0.0
    return [0.0] * len(values) if high == 0 else [v / high for v in values]


def build_matrix(
    db: Session, minutes: int = 10, sumber: str = "overpass"
) -> tuple[list[dict], list[list[float]]]:
    """Kembalikan (rincian per stasiun, matriks keputusan).

    Rinciannya ikut dibawa supaya angka mentahnya bisa ditelusuri — tanpa itu
    skor akhirnya cuma angka yang tidak bisa dipertanggungjawabkan.
    """
    akses = {
        r.station_id: r
        for r in db.execute(
            SQL_AKSESIBILITAS,
            {"minutes": minutes, "networks": list(SCORED_NETWORKS)},
        ).all()
    }
    if not akses:
        raise ValueError(
            f"tidak ada stasiun {'/'.join(SCORED_NETWORKS)} dengan isochrone "
            f"{minutes} menit. Jalankan dulu: python -m scripts.ingest_layers isochrones"
        )

    urban = {u.station_id: u for u in hitung_urban(db, menit=minutes, sumber=sumber)}
    transportasi = {t.station_id: t for t in hitung_transportasi(db)}

    # Hanya stasiun yang lengkap ketiganya. Stasiun tanpa isochrone tidak bisa
    # dinilai variabel A maupun U-nya, dan menyertakannya dengan nol akan
    # menghukumnya karena poligonnya belum dibangkitkan (lihat blocker N13).
    ids = sorted(set(akses) & set(urban) & set(transportasi), key=lambda i: urban[i].station_name)

    details = []
    for sid in ids:
        a, u, t = akses[sid], urban[sid], transportasi[sid]
        details.append(
            {
                "id": sid,
                "name": u.station_name,
                "line_count": t.jumlah_lin,
                "moda_rel": t.moda_rel,
                "moda_jalan": t.moda_jalan,
                "interchange": t.interchange,
                "area_km2": float(a.area_km2),
                "permeability_index": float(a.permeability_index or 0.0),
                "poi_u": u.jumlah_poi,
                "kepadatan_per_km2": u.kepadatan_per_km2,
                "keberagaman": u.keberagaman,
                "pembangkit_perjalanan": u.pembangkit_perjalanan,
            }
        )

    # T tidak punya satu angka alami — ia gabungan tiga hal dengan satuan
    # berbeda: jumlah lin, moda rel terhubung, moda jalan terhubung. Ketiganya
    # diskalakan dulu ke 0-1 lalu dirata-rata, supaya jumlah halte yang bisa
    # puluhan tidak menenggelamkan jumlah lin yang paling banter empat.
    lin = _scale([float(d["line_count"]) for d in details])
    rel = _scale([float(d["moda_rel"]) for d in details])
    jalan = _scale([float(d["moda_jalan"]) for d in details])

    # A juga gabungan: seberapa luas yang terjangkau, dan seberapa efisien
    # jaringan jalannya mengisi luas itu (Permeability Index).
    luas = _scale([d["area_km2"] for d in details])
    pi = _scale([d["permeability_index"] for d in details])

    # U memakai ketiga indikator PRD sekaligus: cacah, keberagaman fungsi lahan,
    # dan pembangkit perjalanan berskala besar.
    cacah = _scale([float(d["poi_u"]) for d in details])
    ragam = _scale([d["keberagaman"] for d in details])
    pembangkit = _scale([float(d["pembangkit_perjalanan"]) for d in details])

    matrix: list[list[float]] = []
    for i, d in enumerate(details):
        d["raw_t"] = (lin[i] + rel[i] + jalan[i]) / 3.0
        d["raw_a"] = (luas[i] + pi[i]) / 2.0
        d["raw_u"] = (cacah[i] + ragam[i] + pembangkit[i]) / 3.0
        d["raw_e"] = math.nan
        d["raw_c"] = math.nan
        d["menunggu_survey"] = list(MENUNGGU_SURVEY)

        matrix.append([d["raw_t"], d["raw_e"], d["raw_a"], d["raw_u"], d["raw_c"]])

    return details, matrix
