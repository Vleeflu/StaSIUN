"""Perhitungan indikator penyusun SEPI dari data yang sudah ada di database.

Satu berkas ini menjawab pertanyaan "berapa nilai T, E, A, U, C untuk tiap
stasiun" — tetapi hanya untuk bagian yang datanya sudah tersedia. Bagian yang
datanya belum masuk sengaja mengembalikan None, bukan angka asumsi, supaya
ketiadaan data terlihat jelas dan ikut menurunkan confidence, bukan menyamar
jadi nilai nol yang tampak sah.

Status per variabel (10 Sep 2026):

    U  Urban          -> BISA DIHITUNG PENUH, dan sejak 10 Sep batasnya poligon
                         isochrone sungguhan, bukan lagi lingkaran 1.200 m
    T  Transportasi   -> sebagian: moda terhubung dan status interchange bisa,
                         volume penumpang menunggu N4
    A  Aksesibilitas  -> poligonnya sudah masuk (N2 terjawab), rumus indeksnya
                         belum ditulis di berkas ini
    E  Ekonomi        -> menunggu Activity (N1)
    C  Komersial      -> menunggu Activity (N1)

Variabel E dan C TIDAK boleh disuapi titik minat di luar stasiun. PRD Tabel 6
menetapkan keduanya bersumber dari kondisi di dalam stasiun lewat survey
Activity: E dari daftar tenant dan rentang harga, C dari media iklan, keterisian
lapak, dan indeks sentimen. Titik minat di luar stasiun menyuapi U, dan halte
menyuapi T. Penjagaannya ada di scripts/ingest_layers.py lewat VARIABEL_SAH.

Perhitungan dijalankan sebagai SQL, bukan Python, karena jaraknya dihitung
antara 19 ribu titik minat dan 78 stasiun — hampir 1,5 juta pemeriksaan. Itu
pekerjaan indeks GiST, dan memindahkannya ke Python berarti membuang gunanya
indeks itu dibuat.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.geo import SRID_METRIC

# Cincin isochrone yang dipakai sebagai batas kawasan variabel U.
#
# PRD hal. 12 menetapkan tiga cincin: 5, 10, dan 15 menit. Untuk variabel U
# dipilih 10 menit sebagai bawaan, tapi ini KEPUTUSAN, bukan keharusan — dan
# ketiganya harus diuji terhadap korelasi dengan volume penumpang sebelum
# dikunci. Parameternya dibiarkan terbuka supaya pengujian itu tinggal
# mengganti argumen, bukan menyunting SQL.
MENIT_CATCHMENT = 10

# Radius lingkaran lama, 1.200 m. Tidak lagi dipakai menghitung apa pun;
# disimpan sebagai pembanding saat menguji seberapa jauh batas isochrone
# menggeser hasil dibanding batas lingkaran.
RADIUS_LAMA_M = 1200

# Pembagi entropi Shannon: jumlah fungsi lahan yang MUNGKIN, bukan yang
# kebetulan teramati di satu stasiun. Kalau pembaginya ikut menyusut mengikuti
# kemiskinan data sebuah stasiun, stasiun termiskin justru terlihat paling
# merata.
#
# Mengikat angka ini ke KODE, bukan ke data, juga menjaganya stabil: memperluas
# cakupan ke kota lain tidak boleh mengubah skor stasiun yang sudah dihitung.
#
# Angkanya beda per sumber karena sistem kategorinya memang partisi yang
# berbeda, dan justru itu sebabnya dua sumber tidak boleh dilebur jadi satu
# entropi:
#   overpass  11 kategori dari osm.py
#   mapid      8 fungsi lahan dari layers.yml, setelah merek disatukan
#              (alfamart + indomaret -> ritel) dan transportasi dikeluarkan
JUMLAH_KATEGORI = {"overpass": 11, "mapid": 8}

# Kategori yang BUKAN fungsi lahan, jadi tidak boleh ikut perhitungan
# keberagaman:
#
#   fasilitas_jalan  perabot jalan (bangku, tempat sampah, pintu masuk parkir).
#                    Tidak menarik siapa pun datang ke sebuah kawasan, dan
#                    banyaknya yang terpetakan lebih mencerminkan kerajinan
#                    pemeta OSM daripada keadaan kawasannya.
#   lainnya          yang tidak tergolongkan. Ketiadaan penggolongan bukan
#                    sebuah fungsi lahan tersendiri.
#   transportasi     halte pada lajur MAPID. Menurut PRD Tabel 6 halte menyuapi
#                    variabel T, bukan U, jadi tidak boleh dihitung dua kali.
#
# fasilitas_jalan juga dikeluarkan dari hitungan KEPADATAN, karena bangku bukan
# "titik minat". `lainnya` tetap dihitung sebagai kepadatan — dia titik minat
# sungguhan, hanya belum tergolongkan.
BUKAN_FUNGSI_LAHAN = {
    "overpass": ("fasilitas_jalan", "lainnya"),
    "mapid": ("transportasi",),
}
TIDAK_DIHITUNG_SEBAGAI_POI = {
    "overpass": ("fasilitas_jalan",),
    "mapid": ("transportasi",),
}

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
WITH tercakup AS (
    -- Titik minat yang berada DI DALAM poligon isochrone tiap stasiun, bukan
    -- di dalam lingkaran beradius tetap. Inilah yang disyaratkan PRD: batasnya
    -- mengikuti jaringan jalan, jadi rel dan sungai yang memutus jalan kaki
    -- ikut terhitung sebagai hambatan.
    --
    -- Satu titik boleh masuk ke lebih dari satu stasiun: kawasan yang dilayani
    -- dua stasiun memang benar-benar terlayani keduanya.
    --
    -- ST_Contains menaruh poligon di argumen pertama. Urutan itu bukan selera:
    -- PostGIS menyaring dulu dengan kotak pembatas lewat indeks GiST pada
    -- poi.location, baru menguji geometri sungguhan pada sisa yang lolos.
    SELECT s.id AS station_id, s.name AS station_name,
           iso.area_m2,
           COALESCE(p.fungsi, p.category) AS fungsi,
           CASE WHEN {PEMBANGKIT_PERJALANAN} THEN 1 ELSE 0 END AS pembangkit
    FROM stations s
    JOIN isochrones iso
      ON iso.station_id = s.id
     AND iso.minutes = :menit
    JOIN poi p
      ON ST_Contains(iso.geom, p.location)
    WHERE p.source = :sumber
      AND COALESCE(p.fungsi, p.category) <> ALL(:bukan_poi)
),
per_kategori AS (
    SELECT station_id, station_name, area_m2, fungsi,
           count(*)::float AS n,
           sum(pembangkit) AS pembangkit
    FROM tercakup
    GROUP BY station_id, station_name, area_m2, fungsi
),
total AS (
    SELECT station_id,
           sum(n) AS total_poi,
           sum(n) FILTER (WHERE fungsi <> ALL(:bukan_fungsi)) AS total_fungsi,
           sum(pembangkit) AS total_pembangkit
    FROM per_kategori
    GROUP BY station_id
)
SELECT pk.station_id,
       pk.station_name,
       pk.area_m2,
       t.total_poi::int                          AS jumlah_poi,
       t.total_pembangkit::int                   AS pembangkit_perjalanan,
       count(*) FILTER (WHERE pk.fungsi <> ALL(:bukan_fungsi))::int
                                                 AS jumlah_kategori,
       -- Entropi Shannon: -sum(p * ln p) atas proporsi tiap fungsi lahan.
       -- Dibagi ln(jumlah fungsi yang MUNGKIN, bukan yang teramati) supaya
       -- nilai tinggi hanya didapat stasiun yang fungsinya banyak sekaligus
       -- merata. Kalau dibagi jumlah teramati, stasiun berfungsi dua yang
       -- terbagi 50/50 akan dapat nilai sempurna — jelas bukan "beragam".
       -- Hanya kategori yang mewakili fungsi lahan yang ikut. Proporsinya
       -- dihitung ulang terhadap total fungsi lahan saja (t.total_fungsi),
       -- bukan terhadap seluruh titik — kalau tidak, jumlah p_i tidak sama
       -- dengan 1 dan hasilnya bukan entropi lagi.
       (-sum(
            CASE WHEN pk.fungsi <> ALL(:bukan_fungsi)
                 THEN (pk.n / t.total_fungsi) * ln(pk.n / t.total_fungsi)
                 ELSE 0 END
        ) / ln(:jumlah_kategori))                 AS keberagaman
FROM per_kategori pk
JOIN total t USING (station_id)
GROUP BY pk.station_id, pk.station_name, pk.area_m2,
         t.total_poi, t.total_fungsi, t.total_pembangkit
ORDER BY t.total_poi DESC
"""

SQL_CEK_SUMBER = """
SELECT count(*)::int AS n FROM poi WHERE source = :sumber
"""

SQL_CEK_ISOCHRONE = """
SELECT count(*)::int AS n,
       count(*) FILTER (WHERE station_id IS NOT NULL)::int AS tersambung,
       count(*) FILTER (WHERE area_m2 IS NULL)::int        AS tanpa_luas
  FROM isochrones WHERE minutes = :menit
"""


class SumberPoiKosong(RuntimeError):
    """Dilempar kalau variabel U dihitung untuk lajur yang belum ada isinya.

    Alasannya sama dengan IsochroneBelumSiap: tanpa penjagaan ini, menyaring
    poi.source ke lajur yang kosong hanya mengembalikan nol baris, dan nol baris
    terlihat persis seperti "belum dijalankan" - bukan seperti kesalahan.
    """


class IsochroneBelumSiap(RuntimeError):
    """Dilempar kalau variabel U dihitung sebelum poligonnya masuk.

    Ada supaya kegagalannya berbunyi. Tanpa penjagaan ini, JOIN ke tabel kosong
    hanya mengembalikan nol baris, dan nol baris terlihat persis seperti "belum
    dijalankan" — bukan seperti kesalahan. Pola itu sudah tujuh kali muncul di
    proyek ini dalam bentuk angka yang masuk akal tapi keliru.
    """


def hitung_urban(
    session: Session,
    menit: int = MENIT_CATCHMENT,
    sumber: str = "overpass",
) -> list[IndikatorUrban]:
    """Hitung bahan variabel U untuk seluruh stasiun, dibatasi isochrone.

    `sumber` memilih lajur data, dan dua lajur TIDAK boleh dijumlahkan:
    sistem kategorinya bukan partisi yang sama, jadi entropinya tidak sebanding.

    Satu keterbatasan lajur "mapid" yang harus disadari sebelum memakainya:
    pembangkit_perjalanan akan selalu 0. Penanda pembangkit dibaca dari tag OSM
    mentah (shop=mall, amenity=hospital, amenity=university, leisure=stadium),
    dan layer MAPID tidak membawa tag mentah sama sekali — 15 kategorinya juga
    tidak memuat mal, rumah sakit, universitas, maupun stadion sebagai kategori
    tersendiri. Padahal PRD Tabel 6 menyebut "jumlah pembangkit perjalanan
    berskala besar" sebagai bagian variabel U. Artinya lajur MAPID sendirian
    tidak bisa memenuhi variabel U; ia berguna sebagai pembanding kepadatan,
    bukan sebagai pengganti.
    """
    if sumber not in JUMLAH_KATEGORI:
        raise ValueError(f"sumber tidak dikenal: {sumber!r}")

    if session.execute(text(SQL_CEK_SUMBER), {"sumber": sumber}).one().n == 0:
        perintah = {
            "overpass": "python -m scripts.ingest_poi",
            "mapid": "python -m scripts.ingest_layers poi",
        }[sumber]
        raise SumberPoiKosong(
            f"tidak ada satu pun titik minat dengan source={sumber!r} di database. "
            f"Jalankan: {perintah}"
        )

    cek = session.execute(text(SQL_CEK_ISOCHRONE), {"menit": menit}).one()
    if cek.n == 0:
        raise IsochroneBelumSiap(
            f"tidak ada poligon isochrone {menit} menit di database. "
            "Jalankan: python -m scripts.ingest_layers isochrones"
        )
    if cek.tersambung == 0:
        raise IsochroneBelumSiap(
            f"{cek.n} poligon {menit} menit ada, tapi tidak satu pun tersambung "
            "ke stasiun. Kemungkinan stations.osm_id belum terisi — seed ulang stasiun."
        )
    if cek.tanpa_luas:
        raise IsochroneBelumSiap(
            f"{cek.tanpa_luas} poligon {menit} menit belum punya area_m2, "
            "jadi kepadatan tidak bisa dihitung."
        )

    baris = session.execute(
        text(SQL_URBAN),
        {
            "menit": menit,
            "sumber": sumber,
            "jumlah_kategori": JUMLAH_KATEGORI[sumber],
            "bukan_fungsi": list(BUKAN_FUNGSI_LAHAN[sumber]),
            "bukan_poi": list(TIDAK_DIHITUNG_SEBAGAI_POI[sumber]),
        },
    ).all()

    return [
        IndikatorUrban(
            station_id=r.station_id,
            station_name=r.station_name,
            jumlah_poi=r.jumlah_poi,
            # Sekarang kepadatan benar-benar menambah informasi. Dengan radius
            # tetap, luasnya sama untuk semua stasiun sehingga kepadatan cuma
            # jumlah yang diskalakan dan urutannya identik. Dengan isochrone,
            # luasnya berbeda tiap stasiun: stasiun yang jangkauannya terpotong
            # rel bisa punya sedikit titik minat namun kepadatan tinggi, dan
            # perbedaan itulah yang hilang selama batasnya masih lingkaran.
            kepadatan_per_km2=r.jumlah_poi / (float(r.area_m2) / 1_000_000.0),
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
         --
         -- Dikunci ke sumber Overpass secara EKSPLISIT. Tanpa baris itu,
         -- perlindungannya cuma kebetulan: baris MAPID kebetulan bercategory
         -- 'halte' (bukan 'transportasi') dan kebetulan tidak punya tag mentah
         -- sehingga MODA_LAIN selalu salah untuknya. Dua kebetulan yang sama-sama
         -- runtuh kalau taksonominya disentuh, dan runtuhnya diam-diam: halte
         -- terhitung dua kali, moda_terhubung menggelembung, tidak ada yang error.
         SELECT count(*)
         FROM poi p
         WHERE p.source = 'overpass'
           AND p.category = 'transportasi'
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
