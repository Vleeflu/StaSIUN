"""Perhitungan indikator penyusun SEPI dari data yang sudah ada di database.

Satu berkas ini menjawab pertanyaan "berapa nilai T, E, A, U, C untuk tiap
stasiun" — tetapi hanya untuk bagian yang datanya sudah tersedia. Bagian yang
datanya belum masuk sengaja mengembalikan None, bukan angka asumsi, supaya
ketiadaan data terlihat jelas dan ikut menurunkan confidence, bukan menyamar
jadi nilai nol yang tampak sah.

Status per variabel (7 Sep 2026):

    U  Urban          -> BISA DIHITUNG PENUH dari tabel poi
    T  Transportasi   -> sebagian: moda terhubung dan status interchange bisa,
                         volume penumpang menunggu N4
    A  Aksesibilitas  -> menunggu isochrone (N2)
    E  Ekonomi        -> menunggu Activity (N1)
    C  Komersial      -> menunggu Activity (N1)

Perhitungan dijalankan sebagai SQL, bukan Python, karena jaraknya dihitung
antara 19 ribu titik minat dan 78 stasiun — hampir 1,5 juta pemeriksaan. Itu
pekerjaan indeks GiST, dan memindahkannya ke Python berarti membuang gunanya
indeks itu dibuat.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.geo import SRID_METRIC

# Radius pencarian bawaan, sama dengan radius penarikan POI. Begitu poligon
# isochrone tersedia, batas lingkaran ini diganti batas isochrone sungguhan —
# lihat catatan di hitung_urban().
RADIUS_M = 1200

# Kategori yang benar-benar mewakili FUNGSI LAHAN. Dipakai sebagai pembagi
# entropi Shannon, dan angkanya HARUS jumlah kategori yang mungkin — bukan
# yang kebetulan teramati di satu stasiun. Kalau pembaginya ikut menyusut
# mengikuti kemiskinan data sebuah stasiun, stasiun termiskin justru terlihat
# paling merata.
#
# Mengikat angka ini ke KODE, bukan ke data, juga menjaganya stabil: memperluas
# cakupan ke kota lain tidak boleh mengubah skor stasiun yang sudah dihitung.
JUMLAH_KATEGORI = 11

# Dua kategori dari osm.py yang BUKAN fungsi lahan, jadi tidak boleh ikut
# masuk perhitungan keberagaman:
#
#   fasilitas_jalan  perabot jalan (bangku, tempat sampah, pintu masuk parkir).
#                    Tidak menarik siapa pun datang ke sebuah kawasan, dan
#                    banyaknya yang terpetakan lebih mencerminkan kerajinan
#                    pemeta OSM daripada keadaan kawasannya.
#   lainnya          yang tidak tergolongkan. Ketiadaan penggolongan bukan
#                    sebuah fungsi lahan tersendiri.
#
# fasilitas_jalan juga dikeluarkan dari hitungan KEPADATAN, karena bangku
# bukan "titik minat". `lainnya` tetap dihitung sebagai kepadatan — dia titik
# minat sungguhan, hanya belum tergolongkan.
BUKAN_FUNGSI_LAHAN = ("fasilitas_jalan", "lainnya")
TIDAK_DIHITUNG_SEBAGAI_POI = ("fasilitas_jalan",)

# Titik minat yang menarik perjalanan dalam jumlah besar, bukan sekadar
# melayani orang yang sudah lewat. PRD menyebutnya "pembangkit perjalanan
# berskala besar" pada variabel U. Dikenali dari tag mentah di osm_tags,
# jadi daftar ini bisa diubah tanpa menarik ulang data dari Overpass.
PEMBANGKIT_PERJALANAN = """(
    p.osm_tags->>'shop' IN ('mall', 'department_store')
    OR p.osm_tags->>'amenity' IN ('hospital', 'university', 'college', 'marketplace')
    OR p.osm_tags->>'leisure' IN ('stadium', 'sports_centre')
    OR p.osm_tags->>'tourism' IN ('attraction', 'museum', 'theme_park')
)"""


@dataclass
class IndikatorUrban:
    """Bahan mentah variabel U untuk satu stasiun.

    Semuanya angka mentah, belum dinormalisasi ke 0-1. Normalisasi sengaja
    dikerjakan belakangan oleh mesin skor, karena batas bawah dan atasnya
    ditentukan oleh seluruh stasiun sekaligus, bukan oleh stasiun ini sendiri.
    """

    station_id: int
    station_name: str
    jumlah_poi: int
    kepadatan_per_km2: float
    keberagaman: float  # 0-1, entropi Shannon dinormalisasi
    jumlah_kategori: int
    pembangkit_perjalanan: int


SQL_URBAN = f"""
WITH terdekat AS (
    -- Titik minat yang berada dalam jangkauan tiap stasiun. Satu titik boleh
    -- masuk ke lebih dari satu stasiun: kawasan yang dilayani dua stasiun
    -- memang benar-benar terlayani keduanya.
    SELECT s.id AS station_id, s.name AS station_name,
           p.category,
           CASE WHEN {PEMBANGKIT_PERJALANAN} THEN 1 ELSE 0 END AS pembangkit
    FROM stations s
    JOIN poi p
      ON ST_DWithin(
             ST_Transform(p.location, :srid_metric),
             ST_Transform(s.location, :srid_metric),
             :radius
         )
    WHERE p.category <> ALL(:bukan_poi)
),
per_kategori AS (
    SELECT station_id, station_name, category,
           count(*)::float AS n,
           sum(pembangkit) AS pembangkit
    FROM terdekat
    GROUP BY station_id, station_name, category
),
total AS (
    SELECT station_id,
           sum(n) AS total_poi,
           sum(n) FILTER (WHERE category <> ALL(:bukan_fungsi)) AS total_fungsi,
           sum(pembangkit) AS total_pembangkit
    FROM per_kategori
    GROUP BY station_id
)
SELECT pk.station_id,
       pk.station_name,
       t.total_poi::int                          AS jumlah_poi,
       t.total_pembangkit::int                   AS pembangkit_perjalanan,
       count(*) FILTER (WHERE pk.category <> ALL(:bukan_fungsi))::int
                                                 AS jumlah_kategori,
       -- Entropi Shannon: -sum(p * ln p) atas proporsi tiap kategori.
       -- Dibagi ln(jumlah kategori yang MUNGKIN, bukan yang teramati) supaya
       -- nilai tinggi hanya didapat stasiun yang kategorinya banyak sekaligus
       -- merata. Kalau dibagi jumlah teramati, stasiun berkategori dua yang
       -- terbagi 50/50 akan dapat nilai sempurna — jelas bukan "beragam".
       -- Hanya kategori yang mewakili fungsi lahan yang ikut. Proporsinya
       -- dihitung ulang terhadap total fungsi lahan saja (t.total_fungsi),
       -- bukan terhadap seluruh titik — kalau tidak, jumlah p_i tidak sama
       -- dengan 1 dan hasilnya bukan entropi lagi.
       (-sum(
            CASE WHEN pk.category <> ALL(:bukan_fungsi)
                 THEN (pk.n / t.total_fungsi) * ln(pk.n / t.total_fungsi)
                 ELSE 0 END
        ) / ln(:jumlah_kategori))                 AS keberagaman
FROM per_kategori pk
JOIN total t USING (station_id)
GROUP BY pk.station_id, pk.station_name, t.total_poi, t.total_fungsi, t.total_pembangkit
ORDER BY t.total_poi DESC
"""


def hitung_urban(
    session: Session, radius_m: int = RADIUS_M
) -> list[IndikatorUrban]:
    """Hitung bahan variabel U untuk seluruh stasiun.

    Batas jangkauan sekarang berupa lingkaran beradius tetap. Ini pengganti
    sementara: PRD mensyaratkan agregasi dihitung menurut batas isochrone, yang
    bentuknya mengikuti jaringan jalan dan berbeda tiap stasiun. Begitu poligon
    isochrone masuk, klausa ST_DWithin di SQL_URBAN diganti ST_Contains
    terhadap poligonnya — sisa perhitungannya tidak berubah sama sekali.

    Konsekuensi yang harus disadari selama masih memakai lingkaran: stasiun
    yang jangkauan nyatanya terpotong rel atau sungai akan tampak lebih kaya
    daripada sebenarnya, karena lingkaran tidak mengenal hambatan fisik.
    """
    baris = session.execute(
        text(SQL_URBAN),
        {
            "srid_metric": SRID_METRIC,
            "radius": radius_m,
            "jumlah_kategori": JUMLAH_KATEGORI,
            "bukan_fungsi": list(BUKAN_FUNGSI_LAHAN),
            "bukan_poi": list(TIDAK_DIHITUNG_SEBAGAI_POI),
        },
    ).all()

    luas_km2 = 3.141592653589793 * (radius_m / 1000) ** 2

    return [
        IndikatorUrban(
            station_id=r.station_id,
            station_name=r.station_name,
            jumlah_poi=r.jumlah_poi,
            # Dengan radius tetap, kepadatan berbanding lurus dengan jumlah,
            # jadi belum menambah informasi apa pun untuk perankingan. Tetap
            # dihitung supaya rumusnya sudah benar saat luas per stasiun mulai
            # berbeda-beda, yaitu ketika isochrone menggantikan lingkaran.
            kepadatan_per_km2=r.jumlah_poi / luas_km2,
            keberagaman=float(r.keberagaman),
            jumlah_kategori=r.jumlah_kategori,
            pembangkit_perjalanan=r.pembangkit_perjalanan,
        )
        for r in baris
    ]


@dataclass
class IndikatorTransportasi:
    """Bahan variabel T yang sudah bisa dihitung tanpa data volume penumpang.

    volume_penumpang sengaja tidak ada di sini. Selama N4 belum masuk, satu
    dari empat indikator T memang hilang, dan itu harus terlihat sebagai
    ketiadaan — bukan ditambal angka rata-rata yang membuat stasiun sepi dan
    stasiun ramai jadi tampak sama.
    """

    station_id: int
    station_name: str
    jumlah_lin: int
    interchange: bool
    moda_rel: int    # MRT / LRT / kereta cepat dalam radius pertukaran
    moda_jalan: int  # halte bus, TransJakarta, taksi, parkir motor

    @property
    def moda_terhubung(self) -> int:
        """Total titik perpindahan moda di sekitar stasiun.

        KOREKSI 8 SEP. Versi sebelumnya hanya menghitung stasiun REL lain dari
        tabel `stations`, sehingga halte bus, TransJakarta, taksi, dan parkir
        motor tidak pernah ikut — hasilnya cuma 8 dari 78 stasiun yang tercatat
        punya moda terhubung, padahal pengamatan lapangan menunjukkan hampir
        semua stasiun punya. Namanya menjanjikan lebih daripada yang diukur.

        Setelah diperbaiki: 32 dari 46 stasiun KAI. Empat belas sisanya
        kemungkinan besar bukan kenyataan melainkan keterbatasan OSM, yang
        jarang memetakan moda informal seperti pangkalan ojek dan pemberhentian
        angkot. Activity jenis E (Konektivitas Antarmoda) dari survey tim
        justru mencatat persis yang OSM lewatkan, jadi indikator ini akan
        diperbaiki lagi begitu data Activity masuk.
        """
        return self.moda_rel + self.moda_jalan


# Jarak yang masih masuk akal ditempuh jalan kaki saat berpindah moda. Dipakai
# untuk menghitung konektivitas antarmoda, yaitu alasan titik MRT, LRT, dan
# kereta cepat ikut disimpan di tabel stations walau bukan unit analisis.
RADIUS_ANTARMODA_M = 500

# Moda yang dihitung sebagai konektivitas antarmoda. Dikenali dari tag OSM
# mentah, bukan dari tabel stations — inilah koreksi 8 Sep.
MODA_LAIN = """(
    p.osm_tags->>'amenity' IN ('bus_station', 'bus_stop', 'taxi', 'car_rental',
                               'car_pooling', 'bicycle_rental', 'motorcycle_parking')
    OR p.osm_tags->>'highway' = 'bus_stop'
    OR p.osm_tags->>'public_transport' IN ('station', 'platform')
)"""

SQL_TRANSPORTASI = f"""
SELECT s.id   AS station_id,
       s.name AS station_name,
       coalesce(array_length(s.lines, 1), 0) AS jumlah_lin,
       (coalesce(array_length(s.lines, 1), 0) > 1) AS interchange,
       (
         -- Moda REL lain di dekat sini: MRT, LRT, kereta cepat.
         SELECT count(DISTINCT lain.types[1])
         FROM stations lain
         WHERE lain.id <> s.id
           AND lain.types[1] <> s.types[1]
           AND ST_DWithin(
                   ST_Transform(lain.location, :srid_metric),
                   ST_Transform(s.location, :srid_metric),
                   :radius
               )
       )::int AS moda_rel,
       (
         -- Moda JALAN: halte bus, TransJakarta, taksi, parkir motor.
         SELECT count(*)
         FROM poi p
         WHERE p.category = 'transportasi'
           AND {MODA_LAIN}
           AND ST_DWithin(
                   ST_Transform(p.location, :srid_metric),
                   ST_Transform(s.location, :srid_metric),
                   :radius
               )
       )::int AS moda_jalan
FROM stations s
ORDER BY s.name
"""


def hitung_transportasi(
    session: Session, radius_m: int = RADIUS_ANTARMODA_M
) -> list[IndikatorTransportasi]:
    """Hitung bagian variabel T yang tidak bergantung pada data sekunder."""
    baris = session.execute(
        text(SQL_TRANSPORTASI),
        {"srid_metric": SRID_METRIC, "radius": radius_m},
    ).all()

    return [
        IndikatorTransportasi(
            station_id=r.station_id,
            station_name=r.station_name,
            jumlah_lin=r.jumlah_lin,
            interchange=r.interchange,
            moda_rel=r.moda_rel,
            moda_jalan=r.moda_jalan,
        )
        for r in baris
    ]
