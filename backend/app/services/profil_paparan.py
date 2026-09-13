"""Profil paparan per stasiun - dasar fitur Ad-Space (PRD bagian h).

PRD memisahkan tegas dua profil yang mudah tertukar:

    "Profil paparan menggambarkan SIAPA YANG MELINTASI suatu zona dan menjadi
    dasar fitur Ad-Space, disusun dari pola keramaian antar-rentang waktu dan
    karakteristik kawasan. Profil pembeli menggambarkan siapa yang benar-benar
    BERTRANSAKSI dan menjadi dasar fitur Tenant Valuation."

Berkas ini menyusun yang pertama, dari empat bahan:

1. **Pola keramaian** per rentang waktu - `crowd_ratings`, skala ordinal 1-5
   dari narasumber. Bukan hitungan kepala.
2. **Karakter kawasan** - `area_profile`, proporsi guna lahan hunian/kantor/
   niaga di dalam isochrone.
3. **Profil pengunjung** - disimpulkan dari fungsi kawasan x pola keramaian,
   BUKAN dari penampilan atau keterangan tentang siapa yang terlihat lewat.
4. **Waktu singgah** - sinyal perilaku di narasi yang sama.

Tiga hal yang SENGAJA tidak dilakukan, dan alasannya:

- **Tidak ada penghitungan orang.** PRD Out-of-Scope melarang pengolahan data
  identitas dan pengukuran arus individual (UU 27/2022 tentang Pelindungan
  Data Pribadi), dan menegaskan produk memakai indikator agregat serta variabel
  proxy. Yang dihitung di sini adalah BERAPA NARASI menyebut sesuatu, bukan
  berapa orang.
- **Tidak ada penilaian penampilan pengunjung.** PRD Tabel 3 menyebutnya
  eksplisit. Profil pengunjung diturunkan dari fungsi kawasan dan pola
  keramaian - dua hal yang terukur - bukan dari siapa yang terlihat lewat,
  dan bukan pula dari keterangan narasumber tentang penampilan mereka.
- **Tidak memanggil model bahasa.** Seluruh isi berkas ini kamus dan hitungan.
  Itu membuatnya bisa dijalankan saat kuota model habis, bisa diaudit baris per
  baris, dan tidak masuk ke dalam batas 15 persen kontribusi model teks.

**Waktu singgah bukan dwell-time individual.** Yang ditolak PRD adalah
mengukur berapa lama SESEORANG berada di suatu titik. Yang disusun di sini
adalah watak tempatnya: ruang yang orang lewati begitu saja, atau ruang yang
membuat orang berhenti. Bedanya menentukan format iklan yang masuk akal -
paparan sekilas menuntut visual cepat, ruang tunggu memungkinkan teks naratif.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Kamus waktu singgah
# ---------------------------------------------------------------------------
#
# Polanya dipilih setelah dihitung kemunculannya di 1.034 narasi, bukan
# dikarang lebih dulu: 368 narasi memuat sinyal melintas, 260 memuat sinyal
# berhenti.

# Kamus AUDIENS dihapus 12 Sep.
#
# Ia memanen kalimat seperti "mayoritas penumpang adalah pekerja kantoran" dari
# narasi survey. Kalimat itu hasil menerka dari penampilan orang yang lewat -
# hanya saja yang menerka narasumber, bukan kami, dan meminjam terkaan orang
# lain tidak membuatnya berhenti jadi terkaan. PRD Tabel 3 mensyaratkan profil
# paparan disusun tanpa mengandalkan penilaian penampilan pengunjung.
#
# Penggantinya `profil_pengunjung`: fungsi kawasan x pola keramaian, dua hal
# yang sama-sama terukur.


# Sinyal waktu singgah. "Pedagang" sengaja TIDAK masuk sini walau paling sering
# muncul: pedagang adalah penghuni tetap ruangnya, bukan orang yang melintas,
# jadi ia tidak mengatakan apa pun tentang berapa lama pengunjung berhenti.
SINGGAH_LAMA = re.compile(
    r"tempat duduk|kursi|menunggu|antre|antri|nongkrong|hangout|ruang tunggu|"
    r"bersantai|istirahat|makan di tempat",
    re.I,
)
SINGGAH_SEBENTAR = re.compile(
    r"berjalan|melintas|bergegas|langsung menuju|arus orang|terus mengalir|transit",
    re.I,
)
# Kalimat penyangkal. "Tak ada tempat duduk" memuat kata "tempat duduk" dan
# akan terbaca sebagai sinyal singgah lama padahal maknanya kebalikannya.
TANPA_DUDUK = re.compile(r"(tak|tidak|belum|tanpa)\s+(ada\s+)?tempat duduk", re.I)


@dataclass
class Paparan:
    station_id: int
    station_name: str
    kawasan: dict | None = None
    keramaian: dict = field(default_factory=dict)
    audiens: list[dict] = field(default_factory=list)
    waktu_singgah: dict = field(default_factory=dict)
    format_iklan: dict = field(default_factory=dict)
    dasar: dict = field(default_factory=dict)


# KEDUA ukuran diambil, tidak dipilih salah satu.
#
# Sebelumnya berkas ini memilih lajur berbobot lantai dengan alasan "di situ
# orangnya". Villyan membantah alasan itu, dan bantahannya benar: luas lantai
# kantor tidak berarti semua penghuninya pekerja kantoran, dan kampung pun
# dihuni pekerja kantoran - bedanya kampung adalah ASAL perjalanan sedangkan
# menara adalah TUJUAN, dan keduanya sama-sama mengisi stasiun.
#
# Ada bias teknis yang menguatkan bantahan itu: rumah di permukiman padat
# jarang dipetakan satu per satu di OSM, jadi ia hanya dihitung 1 lantai
# sementara menara dihitung puluhan. Angka berbobot lantai CENDERUNG TERLALU
# BESAR untuk kantor.
#
# Maka keduanya disajikan berdampingan sebagai KURUNG: luas tanah jadi batas
# satu sisi, luas lantai jadi batas sisi lain, dan kebenarannya ada di antara
# keduanya. Saat keduanya tidak sepakat, ketidaksepakatan itu ikut dilaporkan -
# ia informasi, bukan gangguan (ADJUSTMENT 9.45).
SQL_KAWASAN = """
SELECT profile, office_share, residential_share, komposisi,
       source, source_url, accessed_at
  FROM area_profile
 WHERE station_id = :sid
 ORDER BY (source = 'overpass-landuse-lantai') DESC, updated_at DESC
"""

# MEDIAN, bukan rata-rata. Skala 1-5 dari narasumber itu ordinal: jarak antara
# "3 ramai biasa" dan "4 terus mengalir" tidak sama dengan jarak antara "1" dan
# "2", sehingga merata-ratakannya mengarang ketelitian yang tidak ada.
SQL_KERAMAIAN = """
SELECT time_window,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY rating) AS nilai,
       MIN(scale_min) AS skala_min,
       MAX(scale_max) AS skala_maks,
       COUNT(*) AS jumlah
  FROM crowd_ratings
 WHERE station_id = :sid
 GROUP BY time_window
"""

# Arti tiap tingkat keramaian, mengikuti Panduan Lapangan yang dipakai surveyor.
# Kalimatnya diambil dari cara narasumber sendiri menjelaskannya di lapangan -
# "arus orang terus mengalir, tetapi tidak sampai berdesakan" - bukan dikarang
# ulang, supaya yang dibaca pengguna sama dengan yang dimaksud penilainya.
ARTI_KERAMAIAN = (
    "sangat lengang, hampir tidak ada orang lewat",
    "lengang, sesekali ada orang lewat",
    "ramai biasa",
    "arus orang terus mengalir, tetapi tidak berdesakan",
    "sangat padat, kadang berdesakan",
)


def arti_keramaian(nilai: float, skala_min: int, skala_maks: int) -> str:
    """Terjemahkan angka keramaian jadi kalimat, apa pun rentang skalanya.

    Tidak semua penilaian memakai 1-5. Activity yang ditulis tim lain kadang
    memakai "3 dari 3" atau "7 dari 10", dan angka 3 pada skala 1-3 berarti
    PALING RAMAI sementara pada skala 1-5 ia cuma sedang. Menerjemahkan angka
    mentahnya akan membalik makna.

    Maka yang diterjemahkan adalah POSISINYA pada skala masing-masing:
    (nilai - min) / (maks - min), lalu dipetakan ke lima tingkat yang sama.
    Cara ini sejalan dengan normalisasi berjangkar ujung yang dipakai parser
    (ADJUSTMENT 9.32).
    """
    rentang = skala_maks - skala_min
    posisi = 0.0 if rentang <= 0 else (nilai - skala_min) / rentang
    indeks = min(int(posisi * len(ARTI_KERAMAIAN)), len(ARTI_KERAMAIAN) - 1)
    return ARTI_KERAMAIAN[indeks]

SQL_NARASI = """
SELECT narrative FROM activity_points WHERE station_id = :sid
"""

URUTAN_WAKTU = ("pagi", "siang", "sore")


def _kawasan(session: Session, sid: int) -> dict | None:
    """Komposisi kawasan menurut KEDUA ukuran, beserta kesepakatannya.

    Tidak ada satu label yang dinyatakan sebagai kebenaran. Yang dikembalikan
    adalah komposisi penuh per ukuran, ditambah satu kalimat yang menyatakan
    apakah kedua ukuran sepakat soal fungsi mana yang terbesar.

    Kalau tidak sepakat - misalnya luas tanah bilang hunian sedangkan luas
    lantai bilang kantor - itu justru gambaran paling jujur tentang kawasannya:
    tanahnya didominasi permukiman, ruang terbangunnya didominasi perkantoran.
    Memilih salah satu dan menyembunyikan yang lain akan membuang fakta itu.
    """
    baris = session.execute(text(SQL_KAWASAN), {"sid": sid}).all()
    if not baris:
        return None

    per_ukuran: dict[str, dict] = {}
    for r in baris:
        komposisi = r.komposisi or {}
        nama = komposisi.get("ukuran") or (
            "luas_lantai" if r.source.endswith("lantai") else "luas_tanah"
        )
        per_ukuran[nama] = {
            "label": r.profile,
            "porsi": komposisi.get("porsi"),
            "luas_m2": komposisi.get("luas_m2"),
            "kelas_terbesar": komposisi.get("kelas_terbesar"),
            "dominasi": komposisi.get("dominasi"),
            "arti": komposisi.get("arti"),
            "bias_diketahui": komposisi.get("bias_diketahui"),
            "cakupan_tag_lantai": komposisi.get("cakupan_tag_lantai"),
            "sumber": r.source,
            "sumber_url": r.source_url,
            "diakses": r.accessed_at.isoformat() if r.accessed_at else None,
        }

    tanah = per_ukuran.get("luas_tanah", {})
    lantai = per_ukuran.get("luas_lantai", {})
    a, b = tanah.get("kelas_terbesar"), lantai.get("kelas_terbesar")
    if a and b and a == b:
        sepakat, catatan = True, f"Kedua ukuran sepakat: fungsi terbesar adalah {a}."
    elif a and b:
        sepakat, catatan = False, (
            f"Kedua ukuran TIDAK sepakat: menurut luas tanah {a}, menurut luas "
            f"lantai terbangun {b}. Artinya tanahnya didominasi {a} sementara "
            f"ruang terbangunnya didominasi {b} - keduanya benar, dan keduanya "
            "perlu disebut."
        )
    else:
        sepakat, catatan = None, "Hanya satu ukuran yang tersedia."

    return {
        "per_ukuran": per_ukuran,
        "sepakat": sepakat,
        "catatan": catatan,
        "peringatan": (
            "Komposisi ini menggambarkan peruntukan lahan, bukan jenis "
            "pekerjaan orang yang melintas. Kawasan permukiman tetap dihuni "
            "pekerja kantor; bedanya, permukiman merupakan titik asal "
            "perjalanan sedangkan kawasan perkantoran titik tujuannya."
        ),
    }


def _keramaian(session: Session, sid: int) -> dict:
    hasil = {}
    for r in session.execute(text(SQL_KERAMAIAN), {"sid": sid}).all():
        nilai = float(r.nilai)
        skala_min, skala_maks = int(r.skala_min), int(r.skala_maks)
        hasil[r.time_window] = {
            "nilai": round(nilai, 1),
            "skala_min": skala_min,
            "skala_maks": skala_maks,
            # Angka tanpa arti memaksa pembaca menebak. "4 dari 5" bisa berarti
            # apa saja sampai seseorang memberitahu bahwa itu berarti arus orang
            # terus mengalir tanpa berdesakan.
            "arti": arti_keramaian(nilai, skala_min, skala_maks),
            "jumlah_penilaian": int(r.jumlah),
        }
    return {w: hasil[w] for w in URUTAN_WAKTU if w in hasil}


def _puncak(keramaian: dict) -> str | None:
    """Rentang waktu dengan keramaian tertinggi, atau None kalau seri/kosong."""
    if not keramaian:
        return None
    tertinggi = max(v["nilai"] for v in keramaian.values())
    puncak = [w for w, v in keramaian.items() if v["nilai"] == tertinggi]
    return puncak[0] if len(puncak) == 1 else " dan ".join(puncak)


# Profil pengunjung DITURUNKAN dari fungsi kawasan x pola keramaian,
# bukan dari siapa yang terlihat di lapangan.
#
# PRD Tabel 3 mensyaratkan profil paparan disusun "tanpa mengandalkan penilaian
# penampilan pengunjung", dan Out-of-Scope-nya menolak pengolahan data identitas
# (UU 27/2022). Versi sebelumnya melanggar semangat itu lewat pintu belakang:
# ia memanen kalimat seperti "mayoritas penumpang adalah pekerja kantoran" dari
# narasi. Kalimat itu sendiri hasil menerka dari penampilan - hanya saja yang
# menerka narasumber, bukan kami. Meminjam terkaan orang lain tidak membuatnya
# berhenti jadi terkaan.
#
# Yang dipakai sekarang dua hal yang sama-sama terukur: untuk apa kawasan di
# sekitar stasiun dipakai, dan kapan stasiunnya ramai. Perkantoran yang ramai
# pagi dan sore menghasilkan kesimpulan yang sama kuatnya, tanpa menilai siapa
# pun yang lewat.
KELOMPOK_KAWASAN = {
    "kantor": "pekerja kantor",
    "hunian": "warga sekitar",
    "niaga": "pengunjung pertokoan",
    "wisata": "pengunjung tempat wisata",
    "industri": "pekerja kawasan industri",
    "pendidikan": "pelajar",
}

# Ambang 0,15: fungsi yang porsinya di bawah itu ada, tetapi terlalu kecil untuk
# menyimpulkan kelompok pengunjung darinya.
AMBANG_KELOMPOK = 0.15

# KETERBATASAN GUNA LAHAN, dan kenapa tiga kelompok di bawah dihitung dari titik
# minat alih-alih dari luas kawasan.
#
# Komposisi kawasan hanya mengenal lima kelas - hunian, kantor, niaga, wisata,
# industri - dan dua di antaranya tersumbat:
#
#   1. `landuse=commercial` di OSM dipetakan ke "kantor", karena tag itu
#      maknanya bercabang dan lebih sering berarti perkantoran. Di hub niaga
#      Jakarta pilihan itu MELESET: Tanah Abang tercatat 75,7% kantor dan
#      0,0% niaga - padahal di sana berdiri Pasar Tanah Abang.
#   2. Tidak ada kelas pendidikan sama sekali, jadi pelajar tidak akan pernah
#      muncul betapa pun banyak sekolah di sekitarnya.
#
# Memperbaiki akar masalahnya berarti menarik ulang seluruh poligon guna lahan
# dari Overpass dengan tag yang lebih kaya. Berkas mentah yang tersimpan sudah
# terklasifikasi - tag aslinya tidak ikut disimpan - sehingga tidak bisa
# dihitung ulang tanpa mengambil data lagi.
#
# Yang bisa dilakukan sekarang: membaca langsung titik minat yang memang sudah
# ada di basis data. Polanya sama persis dengan kelompok wisata di bawah, yang
# sudah lebih dulu memakai jalan ini dengan alasan serupa - museum menempati
# lahan kecil tetapi menarik banyak orang, jadi luas melewatkannya.
#
# Ambangnya rendah dan jumlahnya SELALU disebut di kalimat alasan, supaya
# pembaca menilai sendiri seberapa kuat kehadirannya. Sekolah tersebar di
# seluruh Jakarta - mediannya 14 per stasiun - sehingga ambang tinggi justru
# akan membuang stasiun seperti Palmerah yang pelajarnya jelas terlihat.
AMBANG_PENDIDIKAN = 5
AMBANG_PASAR = 1
AMBANG_PUSAT_BELANJA = 1


SQL_TITIK_PENDIDIKAN = """
SELECT COUNT(*)
  FROM isochrones i
  JOIN poi p ON ST_Contains(i.geom, p.location)
 WHERE i.station_id = :sid AND i.minutes = 10
   AND p.source = 'overpass' AND p.category = 'pendidikan'
"""

# Pasar rakyat dan pusat belanja dihitung TERPISAH. Keduanya sama-sama niaga,
# tetapi orang yang mengisinya berbeda: pasar mempertemukan pedagang yang
# mengangkut barang dagangan sejak subuh, mal mempertemukan pengunjung yang
# datang siang untuk berbelanja. Menggabungkan keduanya akan menghapus
# perbedaan yang justru menentukan bentuk iklan dan jam tayangnya.
SQL_TITIK_PASAR = """
SELECT COUNT(*)
  FROM isochrones i
  JOIN poi p ON ST_Contains(i.geom, p.location)
 WHERE i.station_id = :sid AND i.minutes = 10
   AND p.source = 'overpass' AND p.osm_tags->>'amenity' = 'marketplace'
"""

SQL_TITIK_PUSAT_BELANJA = """
SELECT COUNT(*)
  FROM isochrones i
  JOIN poi p ON ST_Contains(i.geom, p.location)
 WHERE i.station_id = :sid AND i.minutes = 10
   AND p.source = 'overpass'
   AND p.osm_tags->>'shop' IN ('mall', 'department_store')
"""

SQL_TITIK_WISATA = """
SELECT COUNT(*)
  FROM isochrones i
  JOIN poi p ON ST_Contains(i.geom, p.location)
 WHERE i.station_id = :sid AND i.minutes = 10
   AND (p.category IN ('wisata_budaya', 'wisata_alam')
        OR p.osm_tags->>'tourism' IN ('museum', 'attraction', 'gallery', 'artwork')
        OR p.osm_tags ? 'historic')
"""

# Ambang 5 titik wisata. Pembedanya tajam dan bukan hasil penalaan: Jakarta Kota
# punya 16, sementara Sudirman 1 dan BNI City 0.
AMBANG_TITIK_WISATA = 5


# Sektor usaha yang masuk akal beriklan, per kelompok pengunjung.
#
# Ini HEURISTIK BISNIS, bukan hasil pengukuran - dan keluarannya menyebut itu
# sendiri. Dasarnya sederhana dan bisa dibantah siapa pun: iklan bekerja ketika
# yang ditawarkan cocok dengan keperluan orang yang sedang lewat. Pekerja yang
# bergegas ke kereta relevan dengan layanan yang dipakai harian; pengunjung
# museum relevan dengan kuliner dan oleh-oleh.
#
# Tidak ada angka di sini, dan memang tidak boleh ada. Menempelkan skor pada
# tebakan akan membuatnya terlihat seperti hasil hitungan.
SEKTOR_PER_KELOMPOK: dict[str, tuple[str, ...]] = {
    "pekerja kantor": ("perbankan dan dompet digital", "kopi dan makanan cepat saji", "telekomunikasi"),
    "warga sekitar": ("kebutuhan rumah tangga", "layanan kesehatan", "ritel harian"),
    "pengunjung tempat wisata": ("kuliner dan oleh-oleh", "pariwisata dan perjalanan", "pembayaran digital"),
    "pengunjung pertokoan": ("ritel dan fesyen", "promo belanja", "pembayaran digital"),
    "pedagang dan pembeli pasar": (
        "layanan keuangan mikro",
        "logistik dan pengiriman",
        "kebutuhan harian",
    ),
    "pelajar": ("telekomunikasi dan paket data", "makanan ringan", "hiburan digital"),
    "pekerja kawasan industri": ("kebutuhan harian", "layanan keuangan mikro"),
}


def sektor_iklan(pengunjung: list[dict], waktu_singgah: dict) -> dict:
    """Sektor usaha yang paling masuk akal beriklan di satu titik.

    Menggabungkan dua hal yang sudah tersusun: SIAPA yang melintas di kawasan
    ini, dan BERAPA LAMA orang berhenti di titik itu. Yang pertama menentukan
    sektornya, yang kedua menentukan apakah pesan panjang sempat terbaca.
    """
    sektor: list[str] = []
    for p in pengunjung[:2]:
        for s in SEKTOR_PER_KELOMPOK.get(p["kelompok"], ()):
            if s not in sektor:
                sektor.append(s)

    label = waktu_singgah.get("label")
    if label == "cenderung lama":
        catatan = (
            "Karena orang berhenti cukup lama di sini, sektor yang perlu "
            "penjelasan - layanan keuangan, properti, pendidikan - masih sempat "
            "tersampaikan."
        )
    elif label == "cenderung singkat":
        catatan = (
            "Karena paparannya sekilas, yang paling berhasil di sini adalah merek "
            "yang sudah dikenal dan pesan satu kalimat."
        )
    else:
        catatan = None

    return {
        "sektor": sektor[:4],
        "catatan": catatan,
        "dasar": (
            "Usulan awal berdasarkan profil pengunjung kawasan dan pola singgah "
            "di titik ini, bukan hasil pengukuran respons iklan."
        ),
    }


def profil_pengunjung(
    kawasan: dict | None,
    keramaian: dict,
    jumlah_titik_wisata: int = 0,
    jumlah_sekolah: int = 0,
    jumlah_pasar: int = 0,
    jumlah_pusat_belanja: int = 0,
) -> list[dict]:
    """Kelompok pengunjung yang masuk akal, beserta dasar penarikannya.

    Tiap kelompok membawa `dasar` - kalimat yang menyebutkan dari mana ia
    disimpulkan. Tanpa itu, daftar kelompok terbaca seperti hasil pengamatan
    langsung, padahal ia kesimpulan.
    """
    if not kawasan:
        return []
    # Porsi diambil dari kedua ukuran, lalu dipakai yang TERBESAR per fungsi.
    #
    # Versi sebelumnya memakai luas tanah saja, dan hasilnya keliru persis di
    # tempat yang paling penting: BNI City - jantung kawasan perkantoran -
    # menampilkan "warga sekitar" di urutan pertama, karena menurut luas tanah
    # 57% kawasannya permukiman (kampung Karet Tengsin di belakang menara).
    # Menurut luas lantai terbangun, 84%-nya justru perkantoran.
    #
    # Untuk profil paparan, memilih salah satu ukuran selalu salah di sebagian
    # stasiun: luas tanah mengecilkan menara, luas lantai mengecilkan
    # permukiman padat. Maka tiap fungsi dinilai dari sisi TERKUATNYA - sebuah
    # fungsi dianggap hadir kalau ia besar menurut salah satu ukuran. Kawasan
    # bisa punya banyak kantor DAN banyak rumah sekaligus; itu bukan
    # kontradiksi, dan keduanya sama-sama mengisi peron.
    ukuran = kawasan.get("per_ukuran") or {}
    porsi: dict[str, float] = {}
    asal: dict[str, str] = {}
    for nama_ukuran, u in ukuran.items():
        for kelas, nilai in ((u or {}).get("porsi") or {}).items():
            if float(nilai) > porsi.get(kelas, 0.0):
                porsi[kelas] = float(nilai)
                asal[kelas] = nama_ukuran
    if not porsi:
        return []

    # Pola waktu dipakai sebagai penajam, bukan penentu. Pagi dan sore ramai
    # sementara siang lengang adalah tanda khas perjalanan berangkat-pulang.
    def posisi(w: str) -> float | None:
        v = keramaian.get(w)
        if not v or v["skala_maks"] <= v["skala_min"]:
            return None
        return (v["nilai"] - v["skala_min"]) / (v["skala_maks"] - v["skala_min"])

    pagi, siang, sore = posisi("pagi"), posisi("siang"), posisi("sore")
    pola_komuter = (
        pagi is not None
        and sore is not None
        and siang is not None
        and min(pagi, sore) - siang >= 0.2
    )

    hasil = []

    # Pemicu kedua untuk kelompok wisata: JUMLAH titik wisata, bukan luasnya.
    #
    # Museum menempati lahan kecil tetapi menarik banyak pengunjung, sehingga
    # ukuran luas melewatkannya - Kota Tua hanya 7% dari luas lantai kawasan
    # Jakarta Kota, di bawah ambang, padahal di dalamnya ada 16 titik wisata dan
    # cagar budaya. Menghitung titiknya menangkap apa yang luas tidak bisa.
    if jumlah_titik_wisata >= AMBANG_TITIK_WISATA:
        hasil.append(
            {
                "kelompok": "pengunjung tempat wisata",
                "dasar": (
                    f"terdapat {jumlah_titik_wisata} titik wisata dan cagar budaya "
                    "dalam jangkauan jalan kaki dari stasiun"
                ),
                "porsi_kawasan": round(porsi.get("wisata", 0.0), 3),
            }
        )

    # Pasar rakyat: satu saja sudah cukup. OSM menandai `amenity=marketplace`
    # dengan hemat - hanya 122 titik di seluruh wilayah studi - jadi kehadirannya
    # bukan kebetulan, dan satu pasar mengumpulkan pedagang serta pembeli dalam
    # jumlah yang tidak bisa diabaikan.
    if jumlah_pasar >= AMBANG_PASAR:
        hasil.append(
            {
                "kelompok": "pedagang dan pembeli pasar",
                "dasar": (
                    f"terdapat {jumlah_pasar} pasar rakyat dalam jangkauan jalan "
                    "kaki dari stasiun"
                ),
                "porsi_kawasan": round(porsi.get("niaga", 0.0), 3),
            }
        )

    if jumlah_sekolah >= AMBANG_PENDIDIKAN:
        hasil.append(
            {
                "kelompok": "pelajar",
                "dasar": (
                    f"terdapat {jumlah_sekolah} sekolah dan kampus dalam jangkauan "
                    "jalan kaki dari stasiun"
                ),
                "porsi_kawasan": 0.0,
            }
        )

    # Pusat belanja memicu kelompok yang sama dengan kelas `niaga`. Ini penambal
    # untuk salah petakan `landuse=commercial` -> "kantor": tanpa ini, Tanah Abang
    # yang punya tiga mal tetap tercatat 0% niaga dan pengunjung pertokoannya
    # hilang sama sekali.
    if jumlah_pusat_belanja >= AMBANG_PUSAT_BELANJA:
        hasil.append(
            {
                "kelompok": KELOMPOK_KAWASAN["niaga"],
                "dasar": (
                    f"terdapat {jumlah_pusat_belanja} pusat belanja dalam jangkauan "
                    "jalan kaki dari stasiun"
                ),
                "porsi_kawasan": round(porsi.get("niaga", 0.0), 3),
            }
        )

    sudah = {h["kelompok"] for h in hasil}

    for kelas, nilai in sorted(porsi.items(), key=lambda x: -x[1]):
        if nilai < AMBANG_KELOMPOK or kelas not in KELOMPOK_KAWASAN:
            continue
        # Kelompok yang sudah masuk lewat hitungan titik tidak diulang dari
        # sisi luas - dua baris dengan nama sama akan terbaca seperti kekeliruan.
        if KELOMPOK_KAWASAN[kelas] in sudah:
            continue
        nama = KELOMPOK_KAWASAN[kelas]
        sebutan = {
            "hunian": "permukiman",
            "kantor": "perkantoran",
            "niaga": "pertokoan",
            "wisata": "tempat wisata",
            "industri": "kawasan industri",
            "pendidikan": "sekolah dan kampus",
        }.get(kelas, kelas)
        patokan = (
            "ruang terbangun di sekitar stasiun"
            if asal.get(kelas) == "luas_lantai"
            else "luas wilayah di sekitar stasiun"
        )
        dasar = f"{round(nilai * 100)}% {patokan} berupa {sebutan}"
        # Pola komuter menempel di ALASAN, bukan di nama kelompoknya. Semua yang
        # masuk stasiun sudah pasti berkomuter, jadi "pekerja kantor yang
        # berkomuter" tidak membedakan apa pun dari "pekerja kantor" - ia cuma
        # memanjangkan sebutan. Yang benar-benar informatif adalah jam ramainya,
        # dan itu tempatnya di kalimat dasar.
        if pola_komuter and kelas in ("kantor", "hunian"):
            dasar += ", dan stasiun ramai pada pagi dan sore tetapi lengang di siang hari"
        hasil.append({"kelompok": nama, "dasar": dasar, "porsi_kawasan": round(nilai, 3)})
    return hasil


def waktu_singgah_narasi(narasi: list[str]) -> dict:
    """Watak ruang: dilewati begitu saja, atau membuat orang berhenti.

    Dinyatakan sebagai kecenderungan, bukan menit. Kita tidak mengukur durasi
    siapa pun, dan tidak boleh berpura-pura bisa.
    """
    lama = sebentar = penyangkal = 0
    for n in narasi:
        ada_penyangkal = bool(TANPA_DUDUK.search(n))
        if ada_penyangkal:
            penyangkal += 1
        if SINGGAH_LAMA.search(n) and not ada_penyangkal:
            lama += 1
        if SINGGAH_SEBENTAR.search(n) or ada_penyangkal:
            sebentar += 1

    total = lama + sebentar
    if total == 0:
        return {
            "label": "tidak terbaca",
            "alasan": "pola singgah belum terbaca dari pengamatan yang ada",
            "sinyal_lama": 0,
            "sinyal_sebentar": 0,
        }

    porsi_lama = lama / total
    if porsi_lama >= 0.6:
        label, alasan = (
            "cenderung lama",
            "tersedia ruang untuk duduk, menunggu, dan berkumpul",
        )
    elif porsi_lama <= 0.4:
        label, alasan = (
            "cenderung singkat",
            "arus pengunjung didominasi perjalanan melintas",
        )
    else:
        label, alasan = (
            "beragam",
            "terdapat jalur lintasan sekaligus titik tunggu",
        )

    return {
        "label": label,
        "alasan": alasan,
        "porsi_singgah_lama": round(porsi_lama, 3),
        "sinyal_lama": lama,
        "sinyal_sebentar": sebentar,
        "kalimat_penyangkal": penyangkal,
    }


def format_iklan_dari_singgah(singgah: dict, keramaian: dict) -> dict:
    """Format iklan yang masuk akal dari watak ruang dan keramaiannya.

    Ini rekomendasi FORMAT, bukan harga. Estimasi harga wajar menunggu
    benchmark tarif per seribu paparan industri OOH (N7), dan menebaknya
    sekarang hanya akan jadi angka yang tidak bisa dipertanggungjawabkan.
    """
    label = singgah.get("label")
    # Posisi relatif, bukan angka mentah: "2 dari 3" itu sedang, sedangkan
    # "2 dari 5" itu lengang. Membandingkan angkanya saja akan menyamakan
    # keduanya.
    posisi = [
        (v["nilai"] - v["skala_min"]) / (v["skala_maks"] - v["skala_min"])
        for v in keramaian.values()
        if v["skala_maks"] > v["skala_min"]
    ]
    tertinggi = max(posisi, default=None)

    if label == "cenderung lama":
        bentuk = "teks naratif, poster informatif, atau kode QR"
        alasan = (
            "pengunjung berhenti cukup lama untuk membaca pesan yang lebih panjang"
        )
    elif label == "cenderung singkat":
        bentuk = "visual cepat berupa logo besar, satu pesan singkat, atau videotron"
        alasan = "paparan berlangsung sekilas saat pengunjung melintas"
    elif label == "beragam":
        bentuk = "visual cepat di jalur lintasan, pesan naratif di titik tunggu"
        alasan = (
            "kedua pola singgah hadir di lokasi ini, sehingga formatnya perlu dibedakan"
        )
    else:
        return {
            "bentuk": None,
            "alasan": "pola singgah belum terbaca dari pengamatan yang ada",
        }

    # Ambang 0,4 pada POSISI skala, bukan angka mentah. Sebelumnya syaratnya
    # "nilai <= 2", yang hanya benar untuk skala 1-5; pada skala 1-3 nilai 2
    # justru berarti sedang.
    catatan = None
    if tertinggi is not None and tertinggi <= 0.4:
        catatan = (
            "Di jam paling ramai pun kawasan ini masih tergolong lengang. "
            "Jangkauan iklannya terbatas, dan itu perlu disampaikan sejak awal "
            "kepada calon pemasang."
        )
    return {"bentuk": bentuk, "alasan": alasan, "catatan": catatan}


def profil_paparan(session: Session, station_id: int) -> Paparan:
    """Susun profil paparan satu stasiun."""
    baris = session.execute(
        text("SELECT id, name FROM stations WHERE id = :sid"), {"sid": station_id}
    ).first()
    if baris is None:
        raise ValueError(f"Stasiun {station_id} tidak ada")

    p = Paparan(station_id=baris.id, station_name=baris.name)

    p.kawasan = _kawasan(session, station_id)

    p.keramaian = _keramaian(session, station_id)
    narasi = [n for (n,) in session.execute(text(SQL_NARASI), {"sid": station_id}).all() if n]
    titik_wisata = session.execute(
        text(SQL_TITIK_WISATA), {"sid": station_id}
    ).scalar() or 0
    sekolah = session.execute(
        text(SQL_TITIK_PENDIDIKAN), {"sid": station_id}
    ).scalar() or 0
    pasar = session.execute(text(SQL_TITIK_PASAR), {"sid": station_id}).scalar() or 0
    belanja = session.execute(
        text(SQL_TITIK_PUSAT_BELANJA), {"sid": station_id}
    ).scalar() or 0
    p.audiens = profil_pengunjung(
        p.kawasan, p.keramaian, titik_wisata, sekolah, pasar, belanja
    )
    p.waktu_singgah = waktu_singgah_narasi(narasi)
    p.format_iklan = format_iklan_dari_singgah(p.waktu_singgah, p.keramaian)
    p.dasar = {
        "jumlah_narasi": len(narasi),
        "jumlah_penilaian_keramaian": sum(v["jumlah_penilaian"] for v in p.keramaian.values()),
        "puncak_keramaian": _puncak(p.keramaian),
        "metode": "kamus dan hitungan, tanpa model bahasa",
        "catatan_privasi": (
            "Analisis ini memakai indikator agregat: tidak ada penghitungan "
            "individu, perekaman identitas, maupun penilaian terhadap "
            "pengunjung. Komposisi kawasan menggambarkan peruntukan lahan di "
            "sekitar stasiun, bukan profil pekerjaan penghuninya."
        ),
    }
    return p
