"""Facility Sponsorship Trigger (F6-2) + validasi silang spasial (F5-1c).

APA YANG DIMINTA PRD
--------------------
PRD hal. 19: "Keluhan yang lolos validasi spasial tampil sebagai penanda pada
peta. Sistem menampilkan usulan bentuk sponsorship beserta lokasi fasilitas
terkait."

PRD hal. 12 menetapkan aturan validasinya: "Setiap temuan berbasis teks wajib
melalui spatial cross-validation, yaitu diuji terhadap kondisi spasial yang
dapat diverifikasi. Sebagai contoh, keluhan mengenai sulitnya menemukan suatu
kategori usaha hanya diterima apabila query spasial memang menunjukkan
ketiadaan atau keterbatasan kategori tersebut pada radius yang relevan."

TIGA STATUS, BUKAN DUA - DAN ALASANNYA (ADJUSTMENT 9.34)
--------------------------------------------------------
Kalimat PRD itu berlaku untuk klaim yang MEMANG bisa diuji dengan data spasial.
Sebagian besar keluhan fasilitas tidak begitu: "lift sedang rusak", "tidak ada
kipas sehingga panas" - tidak ada tabel di database ini yang bisa membenarkan
atau membantahnya.

Dua jalan keluar yang keliru:
  - menandai semuanya "tervalidasi" -> melanggar hal. 12, dan menyematkan
    kepastian yang tidak pernah diuji;
  - membuang yang tidak bisa diuji -> menghapus justru keluhan fisik yang
    paling layak jadi peluang CSR.

Karena itu statusnya tiga:
  tervalidasi         klaimnya diuji ke data spasial DAN cocok
  bertentangan        klaimnya diuji DAN dibantah data -> TIDAK ditampilkan
  pengamatan langsung tidak ada data spasial yang bisa menguji; ia berdiri di
                      atas pengamatan surveyor beserta fotonya, dan label ini
                      ikut tampil di UI supaya pembaca tahu bedanya

KELUHAN YANG BUKAN SOAL FASILITAS
---------------------------------
Ekstraksi LLM kadang menaruh catatan komersial ("pembeli sepi", "harga sewa
mahal") ke dalam `facility_issues`. Itu bukan fasilitas dan tidak ada bentuk
sponsorship yang masuk akal untuknya, jadi disaring keluar dan DIHITUNG - lihat
`HasilSponsorship.bukan_fasilitas`. Angkanya adalah umpan balik untuk prompt
ekstraksi, bukan sesuatu yang disembunyikan.

USULAN BENTUK SPONSORSHIP
------------------------
Dari tabel pemetaan kata kunci di bawah, bukan dari model bahasa. Keluhan yang
tidak cocok dengan satu pun pola TIDAK dikarangkan usulannya; ia tetap tampil
dengan usulan kosong dan catatan bahwa bentuknya perlu ditinjau manusia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

MENIT_BAWAAN = 10

# Sejauh apa sebuah keluhan masih boleh disebut keluhan STASIUN ITU.
#
# Titik Activity ditautkan ke stasiun lewat isochrone 15 menit, dan itu benar
# untuk analisis kawasan - tetapi terlalu longgar untuk CSR. Terbukti nyata:
# catatan berjudul "Kondisi Trotoar di Sekitar Stasiun Tebet" tertaut ke Cawang
# karena jatuh di dalam isochrone Cawang, 877 m dari stasiunnya. Menawarkannya
# sebagai peluang CSR Cawang salah alamat dua kali: bukan asetnya, dan bukan
# kawasannya (ADJUSTMENT 9.36).
#
# 500 m kira-kira jarak jalan kaki 6 menit, cukup untuk mencakup pintu masuk,
# jalur penghubung, dan halte di depan stasiun.
BATAS_JARAK_M = 500

# Ambang "kategori usaha langka" di dalam isochrone. Nol berarti benar-benar
# tidak ada; satu masih dianggap membenarkan keluhan "sulit menemukan".
AMBANG_LANGKA = 1

# Median keramaian ternormalisasi (0-1) yang masih dianggap membenarkan keluhan
# "sepi". 0,4 setara tingkat 2,6 pada skala 1-5.
AMBANG_SEPI = 0.4

STATUS_VALID = "tervalidasi"
STATUS_BANTAH = "bertentangan"
STATUS_LANGSUNG = "pengamatan langsung"

# Keluhan yang sebenarnya catatan komersial, bukan fasilitas.
BUKAN_FASILITAS = re.compile(
    r"(pembeli|omset|omzet|harga\s+sewa|penjualan|dagangan|sepi\s+pembeli|"
    r"kunjungan\s+pembeli)",
    re.IGNORECASE,
)

# Kategori usaha yang bisa diuji ketersediaannya lewat tabel `poi`. Kuncinya
# pola kata di keluhan; nilainya kategori di `poi.category` (lajur mapid).
KATEGORI_TERUJI: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"apotek|obat|farmasi", re.I), "apotek", "apotek"),
    (re.compile(r"minimarket|indomaret", re.I), "indomaret", "minimarket"),
    (re.compile(r"alfamart", re.I), "alfamart", "minimarket"),
    (re.compile(r"kopi|coffee", re.I), "coffee_shop", "kedai kopi"),
    (re.compile(r"atm|bank", re.I), "atm_bank", "ATM atau bank"),
    (re.compile(r"halte|bus|transjakarta|brt", re.I), "halte", "halte bus"),
]

# Pola keluhan "sepi", yang bisa diuji ke skala keramaian narasumber.
POLA_SEPI = re.compile(r"\b(sepi|lengang|tidak\s+ramai|jarang\s+dilalui)\b", re.I)

# Kewenangan atas fasilitasnya. Menentukan apakah KAI bisa menjanjikan
# perbaikannya kepada sponsor, dan ini pertanyaan yang ditanyakan Villyan
# sendiri: trotoar di bahu jalan atau lahan pemda tidak bisa ditawarkan begitu
# saja (ADJUSTMENT 9.36).
ASET_STASIUN = "aset stasiun"
LUAR_LAHAN = "di luar lahan stasiun"

KETERANGAN_KEWENANGAN = {
    ASET_STASIUN: "Berada di dalam atau menempel bangunan stasiun; KAI yang mengelolanya.",
    LUAR_LAHAN: (
        "Berada di jalan atau trotoar yang umumnya dikelola pemerintah daerah. "
        "Sponsorship tetap mungkin lewat program CSR bersama, tetapi WAJIB melalui "
        "izin pengelola jalan - jangan ditawarkan sebagai aset KAI."
    ),
}

# Bentuk sponsorship per jenis keluhan. Urutan penting: yang lebih khusus dulu.
USULAN: list[tuple[re.Pattern, str, str, str]] = [
    (
        re.compile(r"guiding\s*block|tactile|difabel|disabilitas|kursi\s*roda", re.I),
        "Jalur difabel bersponsor",
        "guiding block dan tactile paving berlogo sponsor, dipasang sepanjang jalur masuk",
        LUAR_LAHAN,
    ),
    (
        re.compile(r"trotoar|pedestrian|pejalan|bahu\s+jalan|zebra", re.I),
        "Perbaikan jalur pejalan kaki",
        "penataan trotoar dan penyeberangan sebagai CSR akses, dengan papan nama sponsor di ujung jalur",
        LUAR_LAHAN,
    ),
    (
        re.compile(r"penerangan|pencahayaan|lampu|gelap|pju|redup", re.I),
        "Penerangan bersponsor",
        "lampu koridor atau PJU berlogo sponsor; biaya listrik dan perawatan masuk paket kemitraan",
        LUAR_LAHAN,
    ),
    (
        re.compile(r"tempat\s+duduk|bangku|kursi|menunggu", re.I),
        "Bangku tunggu bersponsor",
        "bangku peron atau area tunggu dengan panel iklan pada sandarannya",
        ASET_STASIUN,
    ),
    (
        re.compile(r"ventilasi|kipas|pendingin|\bac\b|panas|gerah|sirkulasi", re.I),
        "Pendingin udara bersponsor",
        "kipas industri atau AC area tunggu, merek sponsor tampil pada unitnya",
        ASET_STASIUN,
    ),
    (
        re.compile(r"atap|kanopi|peneduh|hujan|teduh", re.I),
        "Kanopi peneduh bersponsor",
        "kanopi jalur masuk atau area tunggu dengan panel merek pada rangkanya",
        ASET_STASIUN,
    ),
    (
        re.compile(r"toilet|wc|kebersihan|kotor|sampah|bau|jorok", re.I),
        "Kebersihan bersponsor",
        "tempat sampah terpilah dan perawatan toilet dengan penanda merek yang tenang",
        ASET_STASIUN,
    ),
    (
        re.compile(r"parkir|sepeda|motor\s+parkir", re.I),
        "Fasilitas parkir bersponsor",
        "rak sepeda atau penataan parkir motor, merek sponsor pada rangka dan papan petunjuk",
        ASET_STASIUN,
    ),
    (
        re.compile(r"lift|eskalator|tangga|akses\s+vertikal", re.I),
        "Kemitraan pemeliharaan akses vertikal",
        "kontrak perawatan lift atau eskalator, merek sponsor pada panel informasi di sisinya",
        ASET_STASIUN,
    ),
    (
        re.compile(r"antre|antrean|kapasitas|padat|penumpukan|sempit", re.I),
        "Penataan antrean bersponsor",
        "pembatas antrean dan papan petunjuk arah berlogo sponsor",
        ASET_STASIUN,
    ),
    (
        re.compile(r"charging|colokan|listrik\s+hp|wifi|internet", re.I),
        "Titik daya dan wifi bersponsor",
        "charging station atau titik wifi gratis atas nama sponsor",
        ASET_STASIUN,
    ),
    (
        re.compile(r"air\s+minum|dispenser|haus", re.I),
        "Dispenser air minum bersponsor",
        "titik isi ulang air minum dengan merek sponsor",
        ASET_STASIUN,
    ),
    (
        re.compile(r"informasi|petunjuk|signage|papan\s+nama|arah", re.I),
        "Papan petunjuk bersponsor",
        "signage arah dan peta stasiun, ruang merek kecil di bagian bawah papan",
        ASET_STASIUN,
    ),
]


@dataclass
class HasilSponsorship:
    peluang: list[dict]
    bukan_fasilitas: int = 0
    dibantah: int = 0
    di_luar_lingkup: int = 0  # keluhan di stasiun non-KRL, tidak ikut dihitung
    tanpa_bentuk: int = 0     # tidak ada bentuk sponsorship yang masuk akal
    terlalu_jauh: int = 0     # keluhan di luar radius stasiun, kemungkinan salah alamat
    digabung: int = 0         # laporan kembar yang dilebur jadi satu peluang


# Hanya stasiun yang ikut diskor. Keluhan di stasiun MRT yang kebetulan
# tertangkap survey Activity (ASEAN Headquarters, Blok M BCA, Bendungan Hilir)
# TIDAK ditampilkan: produk ini menilai ruang komersial stasiun KAI Commuter,
# dan menawarkan CSR atas aset operator lain bukan kewenangan siapa pun di sini.
SQL_KELUHAN = """
SELECT f.id, f.station_id, s.name AS station_name, f.issue_type, f.description,
       f.sentiment_score, ap.id AS point_id, ap.name AS point_name,
       ST_X(ap.location) AS lon, ST_Y(ap.location) AS lat,
       round(ST_Distance(ST_Transform(ap.location, 32748),
                         ST_Transform(s.location, 32748))::numeric) AS jarak_m
  FROM facility_issues f
  JOIN stations s ON s.id = f.station_id
  LEFT JOIN activity_points ap ON ap.id = f.activity_point_id
 WHERE f.sentiment_score < 0
   AND EXISTS (SELECT 1 FROM station_scores sc WHERE sc.station_id = f.station_id)
   AND (CAST(:sid AS integer) IS NULL OR f.station_id = :sid)
 ORDER BY f.sentiment_score, f.id
"""

SQL_HITUNG_KATEGORI = """
SELECT count(*)
  FROM poi p
  JOIN isochrones i ON i.station_id = :sid AND i.minutes = :menit
 WHERE p.source = 'mapid' AND p.category = :kategori
   AND ST_Contains(i.geom, p.location)
"""

SQL_KERAMAIAN = """
SELECT percentile_disc(0.5) WITHIN GROUP (
           ORDER BY (rating - scale_min)::float / (scale_max - scale_min)
       )::float AS median, count(*) AS n
  FROM crowd_ratings WHERE station_id = :sid
"""


def usulan_untuk(jenis: str, deskripsi: str) -> tuple[str | None, str | None, str | None]:
    """Bentuk sponsorship dari jenis keluhan; deskripsi hanya cadangan.

    Urutannya menentukan, dan versi pertama salah: keluhan berjenis "penerangan"
    di Pasar Minggu Baru mendapat usulan "Perbaikan jalur pejalan kaki", karena
    deskripsinya memuat "gelap bagi pejalan kaki" dan pola trotoar diperiksa
    lebih dulu. Jenis keluhan adalah ringkasan yang ditulis untuk menamai
    masalahnya, jadi ia yang berhak menang.
    """
    for sumber in (jenis, deskripsi):
        for pola, bentuk, dasar, milik in USULAN:
            if pola.search(sumber or ""):
                return bentuk, dasar, milik
    return None, None, None


def _validasi(db: Session, baris, teks: str, menit: int) -> dict:
    """Uji klaim keluhan ke kondisi spasial yang bisa diperiksa."""
    for pola, kategori, sebutan in KATEGORI_TERUJI:
        if pola.search(teks):
            jumlah = db.execute(
                text(SQL_HITUNG_KATEGORI),
                {"sid": baris.station_id, "menit": menit, "kategori": kategori},
            ).scalar_one()
            cocok = jumlah <= AMBANG_LANGKA
            return {
                "status": STATUS_VALID if cocok else STATUS_BANTAH,
                "uji": f"jumlah {sebutan} di dalam isochrone {menit} menit",
                "temuan": f"{jumlah} titik",
                "catatan": (
                    f"Keluhan cocok: hanya {jumlah} {sebutan} dalam jangkauan jalan kaki."
                    if cocok
                    else f"Data membantah: ada {jumlah} {sebutan} dalam jangkauan jalan kaki."
                ),
            }

    if POLA_SEPI.search(teks):
        hasil = db.execute(text(SQL_KERAMAIAN), {"sid": baris.station_id}).first()
        if hasil and hasil.n:
            cocok = hasil.median <= AMBANG_SEPI
            setara = 1 + 4 * hasil.median
            return {
                "status": STATUS_VALID if cocok else STATUS_BANTAH,
                "uji": "median skala keramaian narasumber",
                "temuan": f"{setara:.1f} dari 5 ({hasil.n} penilaian)",
                "catatan": (
                    "Keluhan cocok: skala keramaian narasumber memang rendah."
                    if cocok
                    else "Data membantah: narasumber menilai keramaiannya tidak rendah."
                ),
            }

    return {
        "status": STATUS_LANGSUNG,
        "uji": None,
        "temuan": None,
        "catatan": (
            "Tidak ada data spasial yang bisa menguji klaim ini. Ia berdiri di atas "
            "pengamatan surveyor beserta foto lapangannya."
        ),
    }


def peluang_sponsorship(
    db: Session, station_id: int | None = None, menit: int = MENIT_BAWAAN
) -> HasilSponsorship:
    hasil = HasilSponsorship(peluang=[])
    hasil.di_luar_lingkup = db.execute(
        text(
            """
            SELECT count(*) FROM facility_issues f
             WHERE f.sentiment_score < 0
               AND NOT EXISTS (
                     SELECT 1 FROM station_scores sc WHERE sc.station_id = f.station_id
                   )
            """
        )
    ).scalar_one()

    for baris in db.execute(text(SQL_KELUHAN), {"sid": station_id}).all():
        teks = f"{baris.issue_type} {baris.description}"

        if BUKAN_FASILITAS.search(teks):
            hasil.bukan_fasilitas += 1
            continue

        if baris.jarak_m is not None and baris.jarak_m > BATAS_JARAK_M:
            # Kemungkinan besar milik stasiun lain yang isochrone-nya bertindih.
            hasil.terlalu_jauh += 1
            continue

        validasi = _validasi(db, baris, teks, menit)
        if validasi["status"] == STATUS_BANTAH:
            # Dibuang, bukan ditampilkan dengan catatan kecil. PRD hal. 12
            # menyatakan keluhan yang dibantah query spasial tidak diterima.
            hasil.dibantah += 1
            continue

        bentuk, dasar, milik = usulan_untuk(baris.issue_type, baris.description)
        if bentuk is None:
            # Tidak ada industri yang masuk akal menyeponsori "harus keluar dulu
            # dari stasiun". Menampilkannya dengan usulan kosong hanya membuat
            # daftar peluang terlihat panjang tanpa menambah peluang.
            hasil.tanpa_bentuk += 1
            continue

        hasil.peluang.append(
            {
                "id": baris.id,
                "station_id": baris.station_id,
                "stasiun": baris.station_name,
                "jenis": baris.issue_type,
                "keluhan": baris.description,
                "sentimen": baris.sentiment_score,
                "lokasi": {
                    "lon": baris.lon,
                    "lat": baris.lat,
                    "jarak_m": int(baris.jarak_m) if baris.jarak_m is not None else None,
                    "nama_titik": baris.point_name,
                },
                "validasi": validasi,
                "usulan": {
                    "bentuk": bentuk,
                    "dasar": dasar,
                    "kewenangan": milik,
                    "catatan_kewenangan": KETERANGAN_KEWENANGAN[milik],
                },
                "jumlah_laporan": 1,
            }
        )

    return _gabung_berdekatan(hasil)


# Dua laporan tentang hal yang sama, dari titik yang sama atau bersebelahan,
# adalah SATU peluang. Terbukti nyata: Duri punya dua keluhan "trotoar" dengan
# koordinat identik, hasil dua kalimat berbeda dalam satu narasi.
RADIUS_GABUNG_M = 30


def _gabung_berdekatan(hasil: HasilSponsorship) -> HasilSponsorship:
    disimpan: list[dict] = []
    for p in hasil.peluang:
        kembar = next(
            (
                q
                for q in disimpan
                if q["station_id"] == p["station_id"]
                and q["usulan"]["bentuk"] == p["usulan"]["bentuk"]
                and _dekat(q["lokasi"], p["lokasi"])
            ),
            None,
        )
        if kembar is None:
            disimpan.append(p)
            continue
        kembar["jumlah_laporan"] += 1
        hasil.digabung += 1
        # Keluhan yang lebih panjang biasanya yang lebih menjelaskan.
        if len(p["keluhan"] or "") > len(kembar["keluhan"] or ""):
            kembar["keluhan"] = p["keluhan"]

    hasil.peluang = disimpan
    return hasil


def _dekat(a: dict, b: dict) -> bool:
    """Jarak kasar dua titik dalam meter, cukup untuk ambang 30 m.

    Dihitung di Python, bukan PostGIS: jumlah peluangnya puluhan, dan satu
    kueri per pasangan akan jauh lebih mahal daripada aritmatika ini.
    """
    if None in (a["lon"], a["lat"], b["lon"], b["lat"]):
        return False
    dx = (a["lon"] - b["lon"]) * 111_320 * 0.995  # cos(-6.2 derajat)
    dy = (a["lat"] - b["lat"]) * 110_574
    return (dx * dx + dy * dy) ** 0.5 <= RADIUS_GABUNG_M


def sebagai_geojson(hasil: HasilSponsorship) -> dict:
    """Penanda peta. Keluhan tanpa koordinat dilewati, bukan ditaruh di titik stasiun."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": p["id"],
                "geometry": {"type": "Point", "coordinates": [p["lokasi"]["lon"], p["lokasi"]["lat"]]},
                "properties": {
                    "station_id": p["station_id"],
                    "stasiun": p["stasiun"],
                    "jenis": p["jenis"],
                    "keluhan": p["keluhan"],
                    "status": p["validasi"]["status"],
                    "usulan": p["usulan"]["bentuk"],
                    "kewenangan": p["usulan"]["kewenangan"],
                    "jumlah_laporan": p["jumlah_laporan"],
                },
            }
            for p in hasil.peluang
            if p["lokasi"]["lon"] is not None
        ],
    }
