"""Ubah `activity_raw` menjadi `activity_points` dan `crowd_ratings`.

ARSITEKTUR DUA LAPIS — MENGIKUTI PRD HAL. 15, BUKAN KENYAMANAN KODE
--------------------------------------------------------------------
PRD menetapkan ekstraksi berjalan dalam dua lapis yang **sejajar dan saling
tidak bergantung**:

  Lapis 1 (universal)  Topic Modeling (LDA), NER, dan Sentiment Analysis atas
                       korpus naratif seluruh Activity. **BELUM DIBANGUN** —
                       lihat F5-1, tertahan N12 (pilihan pustaka NLP Bahasa
                       Indonesia). Tabel `activity_extractions` masih kosong.

  Lapis 2 (opsional)   Hanya pada entri yang memuat pola penilaian narasumber,
                       yaitu skala keramaian DISERTAI atribusi ke petugas. Kalau
                       polanya tidak ada, entri **dilewati tanpa menghentikan
                       proses** — bukan dibuang.

YANG DIKERJAKAN MODUL INI: PENYIAPAN + LAPIS 2. BUKAN LAPIS 1.
---------------------------------------------------------------
Modul ini melakukan dua hal, dan keduanya BUKAN NLP:

  1. Menyiapkan korpus - mengubah `activity_raw` menjadi `activity_points` yang
     tertaut ke stasiun secara spasial. Ini prasyarat lapis 1, bukan lapis 1.
  2. Menjalankan **"Parser pola narasumber"**, yang PRD Tabel 7 daftarkan
     sebagai komponen TERSENDIRI di samping LDA/NER/Sentiment. PRD tidak
     menyebutnya model NLP, dan memang tidak perlu: yang dicari adalah pola
     tekstual yang bentuknya sudah ditetapkan Panduan Lapangan. Regex tepat
     untuk itu.

Perbedaan ini penting supaya tidak ada yang menyangka lapis NLP sudah jalan.
Selama `activity_extractions` kosong, arketipe stasiun belum ada - dan tanpa
arketipe, mekanisme shrinkage (F3-7) tidak punya kelompok pembanding.

Kalimat PRD yang paling menentukan bentuk modul ini:

    "Apabila sistem hanya berfungsi pada data yang mengikuti satu format
     tertentu, produk tidak akan dapat memanfaatkan keseluruhan data yang
     tersedia."

Karena itu **tidak ada satu pun percabangan `if provenance == ...`** di sini.
Kolom `provenance` diisi untuk pelaporan, dan berhenti di situ — persis
peringatan yang sudah tertulis di `models/activity.py`. Entri tim sendiri tidak
mendapat jalur istimewa; ia hanya lebih sering lolos lapis 2 karena formatnya
memang memuat atribusi.

KENAPA ATRIBUSI DIWAJIBKAN SEBELUM ANGKA DIAMBIL
------------------------------------------------
Panduan Lapangan menegaskan skala 1-5 hanya sah kalau berasal dari narasumber,
tidak pernah dari surveyor, dan wajib beratribusi. Alasannya metodologis:
surveyor mengamati sesaat dan tidak punya dasar menilai keramaian normal suatu
titik, sedangkan petugas yang berjaga tiap hari punya pembanding harian.

Maka angka "tingkat 4" yang muncul TANPA penyebutan narasumber sengaja tidak
diambil. Mengambilnya akan menyelundupkan penilaian surveyor ke dalam variabel
yang PRD nyatakan harus berasal dari narasumber — dan tidak ada yang akan tahu,
karena angkanya terlihat sama saja.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.geo import SRID_RENDER

# Tagar tim sendiri. HANYA untuk mengisi kolom `provenance` yang dipakai
# pelaporan. Tidak boleh jadi syarat apa pun di jalur pemrosesan.
TAGAR_TIM = "tim_jujur_saya_tidak_tahu_dan_juga_tidak_diberitahu"

# Kata yang menandai kalimatnya mengutip orang lain, bukan pengamatan surveyor.
# Diambil dari contoh nyata di data: "Menurut petugas keamanan yang berjaga",
# "Berdasarkan informasi kasir tenant", "ia menilai keramaiannya di tingkat 3".
# Diperluas 12 Sep setelah audit seluruh 1.034 narasi menemukan bentuk yang
# terlewat: "Berdasarkan petugas keamanan" (#478), "Dari hasil obrolan dengan
# salah satu penjaga kios" (#1094), "skala yang diberikan oleh petugas" (#1023),
# "Kondisi saat ini dikatakan" (#1024). "berdasarkan" TIDAK dibiarkan berdiri
# sendiri, karena "berdasarkan pengamatan saya" adalah kebalikan atribusi.
ATRIBUSI = re.compile(
    r"\b(menurut(?:nya)?|kata|ujar|beliau|ia\s+menilai|"
    r"berdasarkan\s+(?:informasi|keterangan|penuturan|petugas|narasumber|satpam|"
    r"penjaga|kasir|pedagang|penjual|pemilik)|"
    r"menyebutkan|menuturkan|mengatakan|dikatakan|menjelaskan|mengaku|"
    r"obrolan|wawancara|diwawancarai|narasumber|diberikan\s+oleh)\b",
    re.IGNORECASE,
)

# Angka skala. Narasi nyata memakai "tingkat 4 dari 5" (template Panduan) dan
# "skala 4 dari 5" (Lampiran C PRD sendiri menyebutnya "Skala 1..5"). Versi
# pertama hanya mengenali "tingkat", sehingga rating yang ditulis "skala N" -
# termasuk survey tim di Jakarta Kota - tidak pernah terbaca (B23).
#   grup 1  angka
#   grup 2  angka kedua kalau narasumber memberi rentang ("skala 4 hingga 5")
#   grup 3  penyebut ("dari 5", "dari 10")
# Bentuk kedua, "N dari K" tanpa kata skala ("nilai kepadatan 5 dari 5", #1024),
# ikut dikenali - tetapi TIDAK kalau diikuti benda yang bisa dihitung
# ("3 dari 5 kios terisi" adalah keterisian, bukan keramaian).
#
# RENTANG SKALA SELAIN 1-5 (ADJUSTMENT 9.32)
# Protokol tim dan PRD memakai 1-5, tetapi Activity universal ditulis tim lain
# dengan kebiasaan sendiri: "3 dari 3", "7 dari 10". Angka seperti itu dulu
# dibuang. Sekarang disimpan BESERTA rentangnya dan dinormalisasi berjangkar
# ujung, (r - min) / (max - min), sehingga ujung bawah skala mana pun = 0 dan
# ujung atasnya = 1. Aturannya:
#   ada penyebut K (3..10)    -> rentang 1..K (0..K kalau angkanya 0)
#   tanpa penyebut, angka 1-5 -> rentang 1..5, standar PRD dan Panduan Lapangan
#   tanpa penyebut, di luar 1-5 -> DILEWATI: rentangnya tidak diketahui, dan
#                                menebaknya sama saja mengarang
SKALA = re.compile(
    r"\b(?:tingkat|skala|level)\s+(10|\d)\b"
    r"(?:\s*(?:hingga|sampai|-|atau)\s*(10|\d)\b)?"
    r"(?:\s*(?:dari|/)\s*(\d{1,2})\b)?"
    r"|\b(10|\d)\s*(?:dari|/)\s*(10|[3-9])\b"
    r"(?!\s*(?:unit|kios|lapak|tenant|gerai|toko|orang|layar|media|iklan|pintu|"
    r"peron|titik|spot|kursi|lampu|menit|jam|hari|kali|kereta|%))",
    re.IGNORECASE,
)

SKALA_MAKS_BAWAAN = 5
PENYEBUT_SAH = range(3, 11)


def _angka(m: re.Match) -> int:
    return int(m.group(1) or m.group(4))


def _penyebut(m: re.Match) -> int | None:
    teks = m.group(3) or m.group(5)
    return int(teks) if teks else None


def _rentang_skala(m: re.Match) -> tuple[int, int] | str:
    """(skala_min, skala_maks) untuk satu angka, atau label sebab dilewati."""
    nilai, penyebut = _angka(m), _penyebut(m)
    if penyebut is None:
        if 1 <= nilai <= SKALA_MAKS_BAWAAN:
            return 1, SKALA_MAKS_BAWAAN
        return LABEL_TANPA_PENYEBUT
    if penyebut not in PENYEBUT_SAH or nilai > penyebut:
        return LABEL_SKALA_TAK_DIKENAL
    return (0 if nilai == 0 else 1), penyebut

# Rentang waktu PRD hal. 12: Pagi 06.00-09.00, Siang 09.00-16.00,
# Sore 16.00-19.00. Versi pertama memakai 10-14 untuk siang dan 15-19 untuk
# sore - karangan, bukan PRD.
# HANYA tiga ini yang diterima `ck_crowd_rating_time_window`. "Malam" atau jam
# di luar 06-19 TIDAK dipaksakan masuk salah satu dari tiga, karena memilihkan
# rentang untuk narasumber sama saja mengarang. Kehilangannya dihitung di
# `HasilParse` menurut sebabnya.
KATA_WAKTU = re.compile(r"\b(pagi|siang|tengah\s+hari|sore|malam)\b", re.IGNORECASE)
RENTANG_JAM = re.compile(
    r"\b(\d{1,2})[.:](\d{2})\s*(?:-|–|sampai|hingga|s/d|sd)\s*"
    r"(?:(?:malam|jam|pukul|sekitar)\s+)*(\d{1,2})(?:[.:](\d{2}))?\b",
    re.IGNORECASE,
)
JAM = re.compile(r"\b(\d{1,2})[.:](\d{2})\b")

# Kalimat tentang akhir pekan dilewati. Profil PRD adalah "kebiasaan audiens
# yang konsisten" harian; mencampur rating Sabtu-Minggu ke rata-rata hari kerja
# akan menggeser profil tanpa ada yang tahu (ADJUSTMENT 9.29).
AKHIR_PEKAN = re.compile(
    r"\b(weekend|akhir\s+pekan|sabtu|hari\s+minggu|hari\s+libur)\b", re.IGNORECASE
)

# Kata penghubung yang membuat satu angka berlaku untuk beberapa rentang:
# "pagi hari dan sore hari ... tingkat 5".
PENGHUBUNG = re.compile(r"\b(dan|serta|maupun)\b", re.IGNORECASE)

# Batas kalimat: titik yang diikuti spasi atau akhir teks (bukan titik di
# "07.00"), tanda seru/tanya, titik koma, atau baris baru yang diikuti huruf
# kapital. Baris baru biasa TIDAK memutus kalimat, karena ada narasi yang
# terpotong baris di tengah kalimat ("ia menilai keramaiannya di<enter>tingkat 5").
BATAS_KALIMAT = re.compile(r"\.(?=\s|$)|[!?;]|\n(?=\s*[A-Z\n])")

RENTANG_SAH = {"pagi", "siang", "sore"}
LABEL_AKHIR_PEKAN = "akhir pekan"
LABEL_TANPA_PENYEBUT = "angka di luar 1-5 tanpa penyebut"
LABEL_SKALA_TAK_DIKENAL = "rentang skala tidak dikenal"
LABEL_SKALA_TIDAK_KONSISTEN = "penyebut tidak konsisten dalam satu narasi"
LABEL_RENTANG_SKALA = "skala berupa rentang"
LABEL_SURVEYOR = "sebelum atribusi"


@dataclass
class HasilParse:
    titik: int = 0
    berpola_narasumber: int = 0
    rating: int = 0
    tanpa_stasiun: int = 0
    # Skala yang terbaca tetapi tidak disimpan, dihitung menurut sebabnya
    # supaya kehilangannya terlihat.
    terbuang: dict[str, int] = field(default_factory=dict)
    provenance: dict[str, int] = field(default_factory=dict)

    def catat_provenance(self, asal: str) -> None:
        self.provenance[asal] = self.provenance.get(asal, 0) + 1

    def catat_terbuang(self, label: str) -> None:
        self.terbuang[label] = self.terbuang.get(label, 0) + 1


def deteksi_pola_narasumber(narasi: str) -> bool:
    """Apakah entri ini memuat skala keramaian yang beratribusi.

    Keduanya harus ada. Angka tanpa atribusi berarti penilaian surveyor, dan
    Panduan Lapangan melarangnya dipakai sebagai skala.
    """
    return bool(SKALA.search(narasi)) and bool(ATRIBUSI.search(narasi))


def _label_jam(jam: float) -> str:
    if 6 <= jam < 9:
        return "pagi"
    if 9 <= jam < 16:
        return "siang"
    if 16 <= jam < 19:
        return "sore"
    return "di luar 06-19"


def _token_waktu(kalimat: str) -> list[tuple[int, int, str, str]]:
    """Semua penanda waktu dalam satu kalimat: (awal, akhir, label, jenis).

    Rentang jam diberi label dari TITIK TENGAHNYA. "06.00 sampai 09.00" bertitik
    tengah 07.30 = pagi; kalau jam akhirnya dibaca sendiri, 09.00 justru jatuh
    ke siang menurut batas PRD. Kata waktu yang berada DI DALAM rentang jam
    ("16:00 hingga malam 20:00") diabaikan - rentangnya yang menentukan.
    """
    token = []
    terpakai = []
    for m in RENTANG_JAM.finditer(kalimat):
        awal = int(m.group(1)) + int(m.group(2)) / 60
        akhir = int(m.group(3)) + int(m.group(4) or 0) / 60
        label = _label_jam((awal + akhir) / 2) if akhir > awal else "di luar 06-19"
        token.append((m.start(), m.end(), label, "jam"))
        terpakai.append((m.start(), m.end()))

    def di_rentang(posisi: int) -> bool:
        return any(a <= posisi < b for a, b in terpakai)

    for m in JAM.finditer(kalimat):
        if not di_rentang(m.start()):
            jam = int(m.group(1)) + int(m.group(2)) / 60
            token.append((m.start(), m.end(), _label_jam(jam), "jam"))
    for m in KATA_WAKTU.finditer(kalimat):
        if not di_rentang(m.start()):
            kata = m.group(1).lower()
            label = "siang" if kata.startswith("tengah") else kata
            token.append((m.start(), m.end(), label, "kata"))
    return sorted(token)


def _pilih(token: list, kalimat: str, arah: str) -> list[str]:
    """Label dari penanda waktu di satu wilayah pencarian.

    Kata eksplisit ("pagi") didahulukan daripada jam, karena itu label yang
    diucapkan narasumber sendiri; jam hanya pendukung dan kadang salah ketik
    ("16-30 - 19:00").

    Kalau beberapa label berbeda dihubungkan "dan/serta/maupun", SEMUANYA
    berlaku. Kalau tidak, dipilih yang TERDEKAT ke angka. Versi pertama memilih
    yang pertama menurut urutan daftar pagi-siang-sore, dan itu sumber utama B23.
    """
    if not token:
        return []
    kata = [t for t in token if t[3] == "kata"]
    calon = kata or token
    label_unik = []
    for t in calon:
        if t[2] not in label_unik:
            label_unik.append(t[2])
    if len(label_unik) > 1:
        tersambung = all(
            PENGHUBUNG.search(kalimat[a[1] : b[0]])
            for a, b in zip(calon, calon[1:])
            if a[2] != b[2]
        )
        if tersambung:
            return label_unik
    terdekat = calon[-1] if arah == "mundur" else calon[0]
    return [terdekat[2]]


def _rating_kalimat(kalimat: str) -> list[tuple[int, str, int, int]]:
    skala = list(SKALA.finditer(kalimat))
    if not skala:
        return []
    if AKHIR_PEKAN.search(kalimat):
        return [(_angka(m), LABEL_AKHIR_PEKAN, 0, 0) for m in skala]

    token = _token_waktu(kalimat)
    koma = [0] + [m.end() for m in re.finditer(",", kalimat)] + [len(kalimat) + 1]
    klausa = list(zip(koma, koma[1:]))

    def klausa_ke(posisi: int) -> int:
        return next(i for i, (a, b) in enumerate(klausa) if a <= posisi < b)

    hasil = []
    for i, m in enumerate(skala):
        nilai = _angka(m)
        rentang = _rentang_skala(m)
        if isinstance(rentang, str):
            hasil.append((nilai, rentang, 0, 0))
            continue
        s_min, s_maks = rentang
        if m.group(2) is not None:
            # "skala 4 hingga 5": memilih 4 atau 5 sama saja mengarang.
            hasil.append((nilai, LABEL_RENTANG_SKALA, 0, 0))
            continue

        ki = klausa_ke(m.start())
        k_awal, k_akhir = klausa[ki]
        sebelum = skala[i - 1].end() if i > 0 else 0
        sesudah = skala[i + 1].start() if i + 1 < len(skala) else len(kalimat)

        # Cari di klausa yang sama, dua arah, dibatasi angka tetangga. Arah yang
        # penanda waktunya LEBIH DEKAT yang dipakai: pada "skala 2 pada siang
        # hari dan kemudian meningkat ke skala 5 pada jam 16.00 hingga 20.00",
        # "siang" milik skala 2, dan rentang jam milik skala 5.
        mundur = [t for t in token if max(k_awal, sebelum) <= t[0] and t[1] <= m.start()]
        maju = [t for t in token if m.end() <= t[0] and t[1] <= min(k_akhir, sesudah)]
        jarak_mundur = m.start() - mundur[-1][1] if mundur else None
        jarak_maju = maju[0][0] - m.end() if maju else None
        if jarak_mundur is not None and (jarak_maju is None or jarak_mundur <= jarak_maju):
            label = _pilih(mundur, kalimat, "mundur")
        else:
            label = _pilih(maju, kalimat, "maju")

        # Tidak ada di klausanya sendiri: mundur ke klausa sebelumnya, selama
        # klausa itu tidak memuat angka lain ("Pagi hari jam 05:00 sampai
        # 08:00, di peron ini tidak terlalu ramai, sekitar skala 2").
        j = ki - 1
        while not label and j >= 0:
            p_awal, p_akhir = klausa[j]
            if any(p_awal <= s.start() < p_akhir for s in skala):
                break
            label = _pilih(
                [t for t in token if p_awal <= t[0] and t[1] <= p_akhir],
                kalimat,
                "mundur",
            )
            j -= 1

        for nama in label or ["tidak disebut"]:
            hasil.append((nilai, nama, s_min, s_maks))
    return hasil


def ambil_rating(narasi: str) -> list[tuple[int, str, int, int]]:
    """Seluruh skala keramaian: (angka, rentang waktu, skala_min, skala_maks).

    Satu angka bisa menghasilkan lebih dari satu pasangan ("pagi dan sore ...
    tingkat 5"). Label di luar pagi/siang/sore dikembalikan apa adanya lalu
    disaring pemanggil, supaya jumlah yang terbuang bisa dihitung menurut
    sebabnya.

    Atribusi berlaku MULAI kalimat yang menyebut narasumber. Angka di kalimat
    sebelumnya ("Saat pengamatan, terlihat keramaian berada pada skala 2")
    adalah penilaian surveyor, yang Panduan Lapangan larang dipakai. Versi
    pertama memeriksa atribusi untuk seluruh narasi sekaligus, sehingga angka
    surveyor ikut lolos asal ada kata "menurut" di mana pun.
    """
    if not deteksi_pola_narasumber(narasi):
        return []

    hasil = []
    awal = 0
    sudah_atribusi = False
    for b in list(BATAS_KALIMAT.finditer(narasi)) + [None]:
        akhir = b.start() if b else len(narasi)
        kalimat = narasi[awal:akhir]
        sudah_atribusi = sudah_atribusi or bool(ATRIBUSI.search(kalimat))
        if sudah_atribusi:
            hasil.extend(_rating_kalimat(kalimat))
        else:
            hasil.extend((_angka(m), LABEL_SURVEYOR, 0, 0) for m in SKALA.finditer(kalimat))
        awal = b.end() if b else len(narasi)
    return _periksa_konsistensi_skala(hasil)


def _periksa_konsistensi_skala(
    hasil: list[tuple[int, str, int, int]]
) -> list[tuple[int, str, int, int]]:
    """Satu narasi, satu skala. Penyebut minoritas dianggap tidak konsisten.

    Menormalisasi berjangkar ujung mengandaikan narasumber sungguh memakai skala
    yang ia sebut. Kasus nyata #791 membantahnya: "sore ... tingkat 5 dari 5",
    lalu "pagi hari cukup ramai pada tingkat 3 dari 3". Diskalakan apa adanya,
    pagi = 1,0 = sama padatnya dengan sore - bertentangan dengan kalimatnya
    sendiri ("paling ramai justru sore"). Hampir pasti salah ketik.

    Satu narasumber dalam satu narasi wajar memakai satu skala. Maka kalau
    rentangnya tidak seragam, yang dipakai rentang MAYORITAS; angka dengan
    rentang lain dilewati dan dihitung, bukan diskalakan diam-diam. Kalau
    jumlahnya seri, tidak ada yang bisa dipercaya dan semuanya dilewati.
    """
    sah = [h for h in hasil if h[1] in RENTANG_SAH and h[3] > 0]
    ragam: dict[tuple[int, int], int] = {}
    for h in sah:
        ragam[(h[2], h[3])] = ragam.get((h[2], h[3]), 0) + 1
    if len(ragam) <= 1:
        return hasil
    urut = sorted(ragam.values(), reverse=True)
    mayoritas = max(ragam, key=ragam.get) if urut[0] > urut[1] else None
    return [
        (h[0], LABEL_SKALA_TIDAK_KONSISTEN, 0, 0)
        if h in sah and (h[2], h[3]) != mayoritas
        else h
        for h in hasil
    ]


def _narasumber(narasi: str) -> str | None:
    """Sebutan narasumber apa adanya, untuk atribusi di `respondent_ref`.

    Tidak dinormalkan jadi kategori. Menyimpan "petugas keamanan yang berjaga"
    apa adanya membuat klaimnya bisa ditelusuri balik ke kalimat aslinya;
    memetakannya ke "satpam" akan menghapus jejak itu demi kerapian.
    """
    m = re.search(
        r"(?:menurut|berdasarkan\s+(?:informasi|keterangan))\s+([a-z\s]{3,40})",
        narasi,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


SQL_STASIUN_TERDEKAT = """
SELECT s.id AS station_id, i.id AS isochrone_id
  FROM isochrones i
  JOIN stations s ON s.id = i.station_id
 WHERE i.minutes = :menit
   AND ST_Contains(i.geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
 ORDER BY ST_Distance(
            ST_Transform(s.location, 32748),
            ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 32748)
          )
 LIMIT 1
"""


def _simpan_rating(
    session: Session,
    point_id: int,
    station_id: int | None,
    narasi: str,
    diamati: datetime | None,
    hasil: HasilParse,
) -> None:
    narasumber = _narasumber(narasi)
    for nilai, jendela, s_min, s_maks in ambil_rating(narasi):
        if jendela not in RENTANG_SAH:
            hasil.catat_terbuang(jendela)
            continue
        session.execute(
            text(
                """
                INSERT INTO crowd_ratings
                    (activity_point_id, station_id, time_window, rating,
                     scale_min, scale_max, respondent_ref, observed_at,
                     created_at, updated_at)
                VALUES
                    (:pid, :sid, :jendela, :nilai, :smin, :smaks, :ref, :diamati,
                     now(), now())
                """
            ),
            {
                "pid": point_id,
                "sid": station_id,
                "jendela": jendela,
                "nilai": nilai,
                "smin": s_min,
                "smaks": s_maks,
                "ref": narasumber,
                "diamati": diamati,
            },
        )
        hasil.rating += 1


def bangun_ulang_rating(session: Session) -> HasilParse:
    """Hapus lalu isi ulang `crowd_ratings` dari `activity_points` yang sudah ada.

    Sengaja TIDAK menyentuh `activity_points`. Titik-titik itu dirujuk hasil
    ekstraksi LLM (`ad_spots`, `tenants`, `facility_issues`) yang mahal dibuat
    ulang karena kuota penyedia model terbatas. Memperbaiki parser cukup
    membangun ulang tabel turunannya sendiri - keuntungan menyimpan narasi
    mentah lebih dulu (ELT).
    """
    hasil = HasilParse()
    session.execute(text("DELETE FROM crowd_ratings"))
    baris = session.execute(
        text(
            "SELECT id, station_id, narrative, observed_at FROM activity_points ORDER BY id"
        )
    ).all()
    for point_id, station_id, narasi, diamati in baris:
        narasi = narasi or ""
        hasil.titik += 1
        berpola = deteksi_pola_narasumber(narasi)
        if berpola:
            hasil.berpola_narasumber += 1
        # Kolom penanda ikut diperbarui: pola "skala N" dulu tidak dikenali.
        session.execute(
            text("UPDATE activity_points SET has_interviewer_pattern = :b WHERE id = :i"),
            {"b": berpola, "i": point_id},
        )
        _simpan_rating(session, point_id, station_id, narasi, diamati, hasil)
    session.commit()
    return hasil


def parse_semua(session: Session, menit: int = 15) -> HasilParse:
    """Baca seluruh `activity_raw` yang lolos gate, isi titik dan rating.

    Idempoten: baris yang sudah punya `activity_points` dilewati, sehingga
    menjalankan ulang tidak menggandakan apa pun.
    """
    hasil = HasilParse()

    baris = session.execute(
        text(
            """
            SELECT ar.id, ar.payload
              FROM activity_raw ar
             WHERE ar.gate_status = 'passed'
               AND NOT EXISTS (
                     SELECT 1 FROM activity_points ap WHERE ap.raw_id = ar.id
                   )
            """
        )
    ).all()

    for raw_id, payload in baris:
        isi = payload if isinstance(payload, dict) else json.loads(payload)
        narasi = (isi.get("description") or "").strip()
        geom = isi.get("geometry") or {}
        koordinat = geom.get("coordinates") or []
        if len(koordinat) < 2:
            continue

        lon, lat = float(koordinat[0]), float(koordinat[1])

        tautan = session.execute(
            text(SQL_STASIUN_TERDEKAT), {"menit": menit, "lon": lon, "lat": lat}
        ).first()
        station_id = tautan.station_id if tautan else None
        isochrone_id = tautan.isochrone_id if tautan else None
        if station_id is None:
            hasil.tanpa_stasiun += 1

        # Provenance dicatat, TIDAK dipakai bercabang.
        asal = "survey tim" if TAGAR_TIM in narasi.lower() else "activity umum"
        hasil.catat_provenance(asal)

        berpola = deteksi_pola_narasumber(narasi)
        if berpola:
            hasil.berpola_narasumber += 1

        diamati = None
        if isi.get("created_at"):
            try:
                diamati = datetime.fromisoformat(
                    str(isi["created_at"]).replace("Z", "+00:00")
                )
            except ValueError:
                diamati = None

        point_id = session.execute(
            text(
                """
                INSERT INTO activity_points
                    (raw_id, station_id, isochrone_id, name, narrative,
                     photo_urls, observed_at, location, provenance,
                     has_interviewer_pattern, created_at, updated_at)
                VALUES
                    (:raw_id, :station_id, :isochrone_id, :name, :narrative,
                     CAST(:photos AS jsonb), :observed_at,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :provenance,
                     :berpola, now(), now())
                RETURNING id
                """
            ),
            {
                "raw_id": raw_id,
                "station_id": station_id,
                "isochrone_id": isochrone_id,
                "name": isi.get("title"),
                "narrative": narasi,
                "photos": json.dumps(isi.get("medias") or []),
                "observed_at": diamati,
                "lon": lon,
                "lat": lat,
                "provenance": asal,
                "berpola": berpola,
            },
        ).scalar()
        hasil.titik += 1

        # Lapis 2. Kalau polanya tidak ada, bagian ini sekadar tidak berjalan —
        # titiknya sudah tersimpan dan tetap terpakai lewat lapis 1.
        _simpan_rating(session, point_id, station_id, narasi, diamati, hasil)

    session.commit()
    return hasil
