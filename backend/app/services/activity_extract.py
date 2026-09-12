"""Ekstraksi terstruktur variabel E dan C dari narasi Activity.

KENAPA LLM, BUKAN REGEX
------------------------
Parser pola narasumber (`activity_parse.py`) memakai regex, dan itu tepat di
sana: bentuk kalimatnya sudah ditetapkan Panduan Lapangan ("menurut petugas,
tingkat 4 dari 5").

Di sini bentuknya bebas. Contoh nyata dari data yang sama-sama harus terbaca:

    "3 layar iklan poster digital, 2 layar iklan poster biasa, 1 banner kecil"
    "layar iklan landscape dan digital"                    (tanpa angka)
    "Dari sekitar delapan unit yang tersedia, satu kosong" (angka ditulis huruf)
    "2 iklan digital di koridor menuju halte BRT"

Regex yang menangkap keempatnya akan jadi tebakan berlapis yang gagal diam-diam
pada bentuk kelima.

PENJAGA: SETIAP ANGKA WAJIB MEMBAWA KUTIPAN, DAN KUTIPANNYA DIVERIFIKASI
------------------------------------------------------------------------
Model diminta menyertakan potongan kalimat **verbatim** untuk tiap angka yang
diklaimnya. Potongan itu lalu dicari di narasi aslinya. Kalau tidak ketemu,
ekstraksinya **ditolak** - bukan diperbaiki, bukan diterima dengan catatan.

Ini membuat halusinasi tertangkap mesin, bukan tertangkap kepercayaan. Model
boleh salah membaca; yang tidak boleh adalah salahnya lolos ke database dan
menjadi angka yang tidak bisa dibantah siapa pun.

Pola yang sama sudah dipakai di `ai_tools.py`: AI mengusulkan, data memutuskan.

KEDUDUKAN TERHADAP PRD
-----------------------
PRD Tabel 6 menetapkan:
  C Komersial : media iklan terpasang, keterisian lapak, indeks sentimen fasilitas
  E Ekonomi   : rentang harga klaster tenant, komposisi kategori usaha,
                tingkat keterisian ruang komersial

Ketiganya bersumber dari Activity, dan modul ini yang membacanya.

PRD hal. 16 juga menetapkan output model berbasis teks dibatasi **maksimal 15
persen** terhadap skor akhir. Pembatas itu BELUM diterapkan (F5-1c) dan harus
dipasang sebelum hasil modul ini menyentuh skor.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI  # noqa: F401  (dipakai anotasi tipe lama)
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.station_areas import BATAS_AREA_STASIUN_M
from app.services.llm_penyedia import Rantai, SemuaPenyediaHabis

# Narasi yang tidak menyebut apa pun soal iklan, lapak, atau keluhan tidak perlu
# dikirim ke model sama sekali. Menyaring lebih dulu memangkas ~1.034 menjadi
# ~300 panggilan.
POLA_KANDIDAT = re.compile(
    r"(iklan|banner|videotron|\bLED\b|billboard|gapura|lightbox|"
    r"unit|kios|lapak|tenant|gerai|"
    r"keluhan|rusak|kotor|panas|bocor|bau|gelap|antre)",
    re.IGNORECASE,
)

# Kata yang menandai catatan KONDISI fasilitas, baik buruk maupun baik. Daftar
# pertama di atas hanya berisi kata keluhan, sehingga catatan "banyak tempat
# duduk" atau "toilet bersih" tidak pernah dikirim ke model (ADJUSTMENT 9.31).
POLA_FASILITAS = re.compile(
    r"(fasilitas|toilet|wc|musholl?a|tempat\s+duduk|kursi|bangku|eskalator|"
    r"lift|tangga|\bAC\b|kipas|pencahayaan|lampu|terang|gelap|bersih|kotor|"
    r"nyaman|sempit|luas|licin|bocor|panas|sejuk|sampah|rusak|antre|"
    r"penunjuk\s+arah|signage|ramp|difabel|disabilitas|trotoar|peneduh|kanopi)",
    re.IGNORECASE,
)

# Penyaring kasar sebelum memanggil model: narasi yang tidak menyebut angka
# rupiah sama sekali tidak mungkin memuat harga, dan memanggil model untuknya
# hanya membakar kuota. Sengaja longgar - "Rp3 juta" maupun "Rp15.000" lolos,
# dan pemisahan harga menu versus omset diserahkan ke model, yang bisa membaca
# konteks kalimatnya.
POLA_HARGA = re.compile(r"rp\s?[0-9]", re.IGNORECASE)

SKEMA_HARGA = """{
  "harga": [{"item": "str", "kategori": "str", "harga_idr": int, "satuan": "str", "jenis": "menu|omset", "kutipan": "str"}]
}"""

SKEMA = """{
  "iklan": [{"jenis": "str", "jumlah": int, "status": "terpakai|kosong", "kutipan": "str"}],
  "lapak": {"unit_total": int|null, "unit_terisi": int|null, "kutipan": "str"},
  "tenant": [{"nama": "str", "kategori": "str", "status": "aktif|tutup|kosong", "kutipan": "str"}],
  "fasilitas": [{"jenis": "str", "ringkasan": "str", "sentimen": float, "kutipan": "str"}],
  "harga": [{"item": "str", "kategori": "str", "harga_idr": int, "satuan": "str", "jenis": "menu|omset", "kutipan": "str"}]
}"""

SKEMA_FASILITAS = """{
  "fasilitas": [{"jenis": "str", "ringkasan": "str", "sentimen": float, "kutipan": "str"}]
}"""

INSTRUKSI = f"""Kamu mengekstrak data terstruktur dari catatan survey lapangan stasiun kereta di Jakarta.

Balas HANYA JSON dengan bentuk persis ini, tanpa penjelasan apa pun:
{SKEMA}

ATURAN YANG TIDAK BOLEH DILANGGAR:
1. Setiap objek WAJIB punya "kutipan" berisi potongan kalimat PERSIS dari teks
   aslinya, disalin apa adanya termasuk ejaannya. Jangan meringkas, jangan
   memperbaiki, jangan menerjemahkan kutipan.
2. Kalau sebuah angka tidak disebut di teks, tulis null. JANGAN menebak.
   "beberapa unit" bukan angka - tulis null.
3. Angka yang ditulis huruf ("delapan unit") diubah jadi angka (8), tetapi
   kutipannya tetap berisi kata aslinya.
4. "fasilitas" berisi SEMUA catatan tentang kondisi fasilitas stasiun: yang
   buruk (keluhan), yang biasa saja, DAN yang baik. Contoh yang baik: "banyak
   tempat duduk", "toilet bersih", "fasilitas tergolong nyaman". Satu kalimat
   yang memuji sekaligus mengeluh dipecah jadi dua objek.
   "sentimen" adalah polaritas -1.0 sampai 1.0: keluhan negatif, pujian
   positif, catatan netral mendekati 0. Jangan memasukkan penilaian keramaian
   atau jumlah iklan ke sini.
5. Array yang tidak ada isinya ditulis []. Objek "lapak" yang tidak disebut
   ditulis dengan semua nilai null.
6. Jangan memasukkan apa pun yang tidak tertulis di teks.
7. "harga" hanya diisi kalau teks menyebut ANGKA rupiah. Bedakan dua hal yang
   sama-sama berupa rupiah tetapi maknanya berbeda jauh:
   - "menu" = harga yang dibayar pembeli untuk satu produk. Contoh: "dibanderol
     seharga Rp10.000", "paket hemat mulai dari Rp15.000".
   - "omset" = pendapatan pedagang, biasanya per hari. Contoh: "omset harian
     mencapai Rp3 juta", "rata-rata penjualan harian Rp2 juta".
   Menyebut omset sebagai harga menu akan membuat harga median satu stasiun
   melonjak ratusan kali lipat, jadi penandaan ini wajib benar.
8. Untuk rentang harga ("Rp10.000 - Rp15.000"), tulis batas BAWAHNYA, dan
   kutipannya tetap memuat rentang aslinya. "satuan" diisi apa adanya dari
   teks, misalnya "per porsi", "per cup", "per hari"."""

ATURAN_FASILITAS = """4. "fasilitas" berisi SEMUA catatan tentang kondisi fasilitas stasiun: yang
   buruk (keluhan), yang biasa saja, DAN yang baik. Contoh yang baik: "banyak
   tempat duduk", "toilet bersih", "fasilitas tergolong nyaman". Satu kalimat
   yang memuji sekaligus mengeluh dipecah jadi dua objek.
   "sentimen" adalah polaritas -1.0 sampai 1.0: keluhan negatif, pujian
   positif, catatan netral mendekati 0. Jangan memasukkan penilaian keramaian
   atau jumlah iklan ke sini."""

INSTRUKSI_FASILITAS = f"""Kamu mengekstrak catatan kondisi fasilitas dari catatan survey lapangan stasiun kereta di Jakarta.

Balas HANYA JSON dengan bentuk persis ini, tanpa penjelasan apa pun:
{SKEMA_FASILITAS}

ATURAN YANG TIDAK BOLEH DILANGGAR:
1. Setiap objek WAJIB punya "kutipan" berisi potongan kalimat PERSIS dari teks
   aslinya, disalin apa adanya termasuk ejaannya.
2. Jangan memasukkan apa pun yang tidak tertulis di teks.
3. Kalau tidak ada catatan kondisi fasilitas, balas {{"fasilitas": []}}.
{ATURAN_FASILITAS}"""


@dataclass
class HasilEkstraksi:
    diproses: int = 0
    dilewati: int = 0
    iklan: int = 0
    klaster: int = 0
    tenant: int = 0
    keluhan: int = 0          # seluruh catatan kondisi fasilitas
    fasilitas_positif: int = 0
    harga: int = 0            # harga menu yang masuk ke price_references
    omset_dilewati: int = 0   # angka rupiah yang ternyata omset, bukan harga
    harga_luar_stasiun: int = 0  # harga dari lapak di luar batas area stasiun
    kutipan_ditolak: int = 0
    gagal_parse: int = 0
    bentuk_salah: int = 0     # balasan JSON sah, tetapi isinya bukan objek
    kena_rate_limit: int = 0
    pesan_rate_limit: str | None = None
    penyedia_terpakai: list[str] = field(default_factory=list)
    contoh_ditolak: list[str] = field(default_factory=list)


def _normalkan(teks: str) -> str:
    """Rapatkan spasi dan turunkan huruf, untuk mencocokkan kutipan.

    Model kadang menyalin dengan spasi ganda atau memotong di tengah kata.
    Menormalkan keduanya menghindari penolakan karena beda spasi semata —
    tetapi TIDAK melonggarkan isinya: kata yang tidak ada tetap tidak ketemu.
    """
    return re.sub(r"\s+", " ", teks).strip().lower()


def kutipan_sah(kutipan: str | None, narasi: str) -> bool:
    """Apakah kutipannya benar-benar ada di narasi aslinya.

    Kutipan yang terlalu pendek ditolak juga: potongan tiga huruf akan cocok
    dengan hampir apa pun dan tidak membuktikan apa-apa.
    """
    if not kutipan or len(kutipan.strip()) < 8:
        return False
    return _normalkan(kutipan) in _normalkan(narasi)


def _klien() -> OpenAI:
    """Klien penyedia utama. Disisakan untuk uji cepat dan pemakaian satuan.

    Jalur penarikan massal TIDAK memakainya lagi - ia memakai `Rantai`, yang
    tahu cara pindah penyedia.
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY belum diisi di backend/.env")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


class RateLimitHabis(SemuaPenyediaHabis):
    """Nama lama untuk `SemuaPenyediaHabis`, disisakan supaya skrip lama tetap jalan."""


# Penanganan batas kuota pindah ke `llm_penyedia.Rantai`: batas PER MENIT
# ditunggu, batas PER HARI membuat rantai pindah ke penyedia cadangan, dan
# `SemuaPenyediaHabis` hanya dilempar kalau seluruh penyedia habis. Sebelumnya
# semua itu ada di sini dan hanya mengenal satu penyedia, sehingga kuota harian
# Groq menghentikan seluruh fitur AI (ADJUSTMENT 9.37).


def ekstrak_satu(
    rantai: Rantai, narasi: str, instruksi: str = INSTRUKSI
) -> dict | None:
    """Minta model mengekstrak satu narasi.

    Mengembalikan None kalau balasannya tidak terbaca sebagai JSON, dan
    MELEMPAR `SemuaPenyediaHabis` kalau seluruh penyedia kehabisan kuota harian.

    `reasoning_effort: low` memangkas token penalaran model yang mendukungnya.
    Pekerjaannya menyalin dan menstrukturkan, bukan menalar panjang; token yang
    dihemat berarti lebih banyak narasi per kuota harian.
    """
    balasan = rantai.panggil(
        messages=[
            {"role": "system", "content": instruksi},
            {"role": "user", "content": narasi},
        ],
        response_format={"type": "json_object"},
        extra_body={"reasoning_effort": "low"},
    )
    if balasan is None:
        return None

    isi = balasan.choices[0].message.content or ""
    try:
        return json.loads(isi)
    except json.JSONDecodeError:
        return None


def _objek(nilai, hasil: HasilEkstraksi) -> list[dict]:
    """Ambil hanya objek yang berbentuk benar dari satu bagian balasan model.

    Model kadang membalas JSON yang sah tetapi bentuknya bukan yang diminta -
    misalnya `"iklan": "tidak ada"` atau `"tenant": [null, "Indomaret"]`
    padahal yang diminta daftar objek. Bagian seperti itu tidak bisa disimpan,
    dan kalau dibiarkan melempar TypeError di tengah penyimpanan, satu narasi
    rusak akan menghentikan seluruh proses.

    Yang salah bentuk DIHITUNG lewat `hasil.bentuk_salah`, tidak dibuang
    diam-diam: kalau satu penyedia cadangan ternyata sering salah bentuk,
    angka itulah yang menunjukkannya.
    """
    if nilai is None:
        return []
    if not isinstance(nilai, list):
        hasil.bentuk_salah += 1
        return []
    bersih = []
    for item in nilai:
        if isinstance(item, dict):
            bersih.append(item)
        else:
            hasil.bentuk_salah += 1
    return bersih


def _simpan(
    session: Session, station_id: int | None, point_id: int, narasi: str,
    data: dict, hasil: HasilEkstraksi
) -> None:
    """Tulis hasil ekstraksi, membuang tiap bagian yang kutipannya tidak sah."""
    if station_id is None:
        return

    for item in _objek(data.get("iklan"), hasil):
        if not kutipan_sah(item.get("kutipan"), narasi):
            hasil.kutipan_ditolak += 1
            if len(hasil.contoh_ditolak) < 3:
                hasil.contoh_ditolak.append(str(item.get("kutipan"))[:70])
            continue
        jumlah = item.get("jumlah")
        if not isinstance(jumlah, int) or jumlah < 0:
            continue
        status = item.get("status")
        session.execute(
            text(
                """INSERT INTO ad_spots
                   (station_id, activity_point_id, media_type, media_count,
                    status, visibility_note, created_at, updated_at)
                   VALUES (:sid, :pid, :jenis, :jumlah, :status, :catatan,
                           now(), now())"""
            ),
            {
                "sid": station_id, "pid": point_id,
                "jenis": (item.get("jenis") or "tidak disebut")[:80],
                "jumlah": jumlah,
                "status": status if status in ("terpakai", "kosong") else "terpakai",
                "catatan": item.get("kutipan")[:300],
            },
        )
        hasil.iklan += 1

    lapak = data.get("lapak")
    if not isinstance(lapak, dict):
        if lapak is not None:
            hasil.bentuk_salah += 1
        lapak = {}
    total, terisi = lapak.get("unit_total"), lapak.get("unit_terisi")
    if isinstance(total, int) and total > 0 and kutipan_sah(lapak.get("kutipan"), narasi):
        terisi = terisi if isinstance(terisi, int) and 0 <= terisi <= total else None
        session.execute(
            text(
                """INSERT INTO tenant_clusters
                   (station_id, name, unit_total, unit_filled, unit_empty,
                    criteria_note, created_at, updated_at)
                   VALUES (:sid, :nama, :total, :terisi, :kosong, :catatan,
                           now(), now())"""
            ),
            {
                "sid": station_id,
                "nama": f"klaster dari Activity #{point_id}",
                "total": total,
                "terisi": terisi if terisi is not None else 0,
                "kosong": (total - terisi) if terisi is not None else 0,
                "catatan": lapak.get("kutipan")[:300],
            },
        )
        hasil.klaster += 1
    elif total is not None and not kutipan_sah(lapak.get("kutipan"), narasi):
        hasil.kutipan_ditolak += 1

    for item in _objek(data.get("tenant"), hasil):
        if not kutipan_sah(item.get("kutipan"), narasi):
            hasil.kutipan_ditolak += 1
            continue
        nama = (item.get("nama") or "").strip()
        if not nama:
            continue
        status = item.get("status")
        session.execute(
            text(
                """INSERT INTO tenants
                   (station_id, activity_point_id, name, category, status,
                    created_at, updated_at)
                   VALUES (:sid, :pid, :nama, :kat, :status, now(), now())"""
            ),
            {
                "sid": station_id, "pid": point_id, "nama": nama[:120],
                "kat": (item.get("kategori") or "lainnya")[:60],
                "status": status if status in ("aktif", "tutup", "kosong") else "aktif",
            },
        )
        hasil.tenant += 1

    _simpan_harga(session, station_id, point_id, narasi, data, hasil)
    _simpan_fasilitas(session, station_id, point_id, narasi, data, hasil)


# Batas kewarasan harga menu. Rp1.000 menyaring angka yang jelas bukan harga
# (tahun, nomor peron), dan Rp1.000.000 menyaring omset yang lolos salah label
# dari model. Keduanya dihitung, tidak dibuang diam-diam.
HARGA_MENU_MIN = 1_000
HARGA_MENU_MAKS = 1_000_000


def _simpan_harga(
    session: Session, station_id: int, point_id: int, narasi: str,
    data: dict, hasil: HasilEkstraksi
) -> None:
    """Tulis harga menu ke `price_references`.

    Hanya `jenis == "menu"` yang disimpan. Omset harian ikut diekstrak supaya
    model tidak tergoda melabelinya sebagai harga, tetapi TIDAK ditulis: tabel
    ini dibaca `hitung_ekonomi` sebagai harga per porsi, dan satu baris omset
    Rp3 juta di sana cukup untuk membuat harga median satu stasiun tidak masuk
    akal.

    `source` diisi "survey activity", bukan nama situs, karena angkanya memang
    berasal dari wawancara narasumber tim sendiri - data primer, bukan riset
    sekunder. PRD mewajibkan sumber dan tanggal akses tercatat untuk keduanya.
    """
    # Batas area stasiun, memakai ambang yang SAMA dengan katalog area
    # (`station_areas.BATAS_AREA_STASIUN_M`, 250 m) alih-alih mengarang
    # definisi ketiga soal "dekat stasiun".
    #
    # Bukan kehati-hatian teoretis. Panen pertama memungut "Donat Rp10.000"
    # sebagai harga milik Blok M BCA, padahal lapaknya 485 m dari stasiun -
    # itu harga kawasan pertokoan Blok M, bukan harga di dalam stasiun.
    # Harga menu dipakai menyusun rentang harga per klaster tenant, dan
    # klaster yang dimaksud adalah lapak di dalam stasiun.
    jarak = session.execute(
        text(
            """SELECT ST_Distance(ap.location::geography, s.location::geography)
                 FROM activity_points ap, stations s
                WHERE ap.id = :pid AND s.id = :sid"""
        ),
        {"pid": point_id, "sid": station_id},
    ).scalar()
    if jarak is not None and jarak > BATAS_AREA_STASIUN_M:
        hasil.harga_luar_stasiun += len(_objek(data.get("harga"), hasil))
        return

    for item in _objek(data.get("harga"), hasil):
        if not kutipan_sah(item.get("kutipan"), narasi):
            hasil.kutipan_ditolak += 1
            continue
        if item.get("jenis") != "menu":
            hasil.omset_dilewati += 1
            continue
        harga = item.get("harga_idr")
        if not isinstance(harga, int) or not HARGA_MENU_MIN <= harga <= HARGA_MENU_MAKS:
            hasil.omset_dilewati += 1
            continue
        session.execute(
            text(
                """INSERT INTO price_references
                   (kind, category, item_name, price_idr, unit, station_id,
                    activity_point_id, source, source_url, accessed_at,
                    created_at, updated_at)
                   VALUES ('menu', :kat, :item, :harga, :satuan, :sid, :pid,
                           'survey activity', NULL, CURRENT_DATE, now(), now())"""
            ),
            {
                "kat": (item.get("kategori") or "tidak disebut")[:60],
                "item": (item.get("item") or None),
                "harga": harga,
                "satuan": (item.get("satuan") or "per porsi")[:40],
                "sid": station_id,
                "pid": point_id,
            },
        )
        hasil.harga += 1


def _simpan_fasilitas(
    session: Session, station_id: int, point_id: int, narasi: str,
    data: dict, hasil: HasilEkstraksi
) -> None:
    """Tulis catatan kondisi fasilitas ke `facility_issues`.

    Nama tabelnya warisan skema awal. Isinya kini SEMUA catatan kondisi, dan
    `sentiment_score` positif menandai catatan yang baik. Pemakai yang hanya
    butuh keluhan - pemicu Facility Sponsorship - wajib menyaring
    `sentiment_score < 0`.
    """
    for item in _objek(data.get("fasilitas") or data.get("keluhan"), hasil):
        if not kutipan_sah(item.get("kutipan"), narasi):
            hasil.kutipan_ditolak += 1
            continue
        sentimen = item.get("sentimen")
        sentimen = (
            float(sentimen)
            if isinstance(sentimen, (int, float)) and -1.0 <= sentimen <= 1.0
            else None
        )
        session.execute(
            text(
                """INSERT INTO facility_issues
                   (station_id, activity_point_id, issue_type, description,
                    sentiment_score, spatially_validated, created_at, updated_at)
                   VALUES (:sid, :pid, :jenis, :desk, :sentimen, false,
                           now(), now())"""
            ),
            {
                "sid": station_id, "pid": point_id,
                "jenis": (item.get("jenis") or "lainnya")[:60],
                "desk": (item.get("ringkasan") or item.get("kutipan"))[:500],
                "sentimen": sentimen,
            },
        )
        hasil.keluhan += 1
        if sentimen is not None and sentimen > 0:
            hasil.fasilitas_positif += 1


INSTRUKSI_HARGA = f"""Kamu mengekstrak harga dari catatan survey lapangan stasiun kereta di Jakarta.

Balas HANYA JSON dengan bentuk persis ini, tanpa penjelasan apa pun:
{SKEMA_HARGA}

ATURAN YANG TIDAK BOLEH DILANGGAR:
1. Setiap objek WAJIB punya "kutipan" berisi potongan kalimat PERSIS dari teks
   aslinya, disalin apa adanya termasuk ejaannya.
2. Isi hanya kalau teks menyebut ANGKA rupiah. Kalau tidak ada, balas
   {{"harga": []}}.
3. Bedakan dua hal yang sama-sama berupa rupiah:
   - "menu" = harga yang dibayar pembeli untuk satu produk. Contoh:
     "dibanderol seharga Rp10.000", "paket hemat mulai dari Rp15.000".
   - "omset" = pendapatan pedagang, biasanya per hari. Contoh: "omset harian
     mencapai Rp3 juta", "rata-rata penjualan harian Rp2 juta".
   Menyebut omset sebagai harga menu akan membuat harga median satu stasiun
   melonjak ratusan kali lipat, jadi penandaan ini wajib benar.
4. Untuk rentang harga, tulis batas BAWAHNYA; kutipan tetap memuat rentang
   aslinya. "satuan" diisi apa adanya dari teks, misalnya "per porsi".
5. Jangan memasukkan apa pun yang tidak tertulis di teks."""


def ekstrak_harga_ulang(
    session: Session, batas: int | None = None, stasiun: list[str] | None = None
) -> HasilEkstraksi:
    """Panen harga untuk narasi yang terlanjur diekstrak sebelum skema memuatnya.

    201 narasi diekstrak sebelum bagian `harga` ada di skema, dan 45 di
    antaranya menyebut angka rupiah. Tanpa pass ini mereka tidak akan pernah
    dipanen: jalur utama hanya melihat `llm_ec_at IS NULL`.

    Hemat kuota dengan dua cara. Pertama, narasi yang tidak menyebut angka
    rupiah ditandai selesai TANPA memanggil model. Kedua, skemanya hanya berisi
    bagian harga, bukan skema gabungan - balasannya jauh lebih pendek.

    Baris harga lama milik titik itu dihapus lebih dulu, supaya menjalankan
    perintah ini dua kali tidak menggandakan harga yang sama.
    """
    hasil = HasilEkstraksi()
    rantai = Rantai()
    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, ap.narrative
              FROM activity_points ap
              JOIN stations s ON s.id = ap.station_id
             WHERE ap.llm_ec_at IS NOT NULL
               AND ap.llm_harga_at IS NULL
               AND (CAST(:stasiun AS text[]) IS NULL
                    OR s.name = ANY(CAST(:stasiun AS text[])))
             ORDER BY s.served DESC, ap.id
            """
        ),
        {"stasiun": stasiun},
    ).all()

    for point_id, station_id, narasi in baris:
        if not POLA_HARGA.search(narasi or ""):
            hasil.dilewati += 1
            session.execute(
                text("UPDATE activity_points SET llm_harga_at = now() WHERE id = :i"),
                {"i": point_id},
            )
            session.commit()
            continue
        if batas is not None and hasil.diproses >= batas:
            break

        try:
            data = ekstrak_satu(rantai, narasi, INSTRUKSI_HARGA)
        except SemuaPenyediaHabis as exc:
            hasil.kena_rate_limit = len(baris) - hasil.diproses - hasil.dilewati
            hasil.pesan_rate_limit = str(exc)[:300]
            break
        hasil.diproses += 1
        if data is None:
            hasil.gagal_parse += 1
            continue

        session.execute(
            text(
                "DELETE FROM price_references WHERE activity_point_id = :i "
                "AND source = 'survey activity'"
            ),
            {"i": point_id},
        )
        if station_id is not None:
            _simpan_harga(session, station_id, point_id, narasi, data, hasil)
        session.execute(
            text("UPDATE activity_points SET llm_harga_at = now() WHERE id = :i"),
            {"i": point_id},
        )
        session.commit()

    hasil.penyedia_terpakai = rantai.terpakai
    return hasil


def ekstrak_semua(
    session: Session,
    batas: int | None = None,
    stasiun: list[str] | None = None,
    menyebut: str | None = None,
) -> HasilEkstraksi:
    """Ekstrak E dan C dari seluruh narasi yang berpeluang memuatnya.

    `menyebut` menyaring berdasarkan ISI narasi, bukan stasiunnya. Ditambahkan
    12 Sep setelah satu putaran kuota habis sia-sia: menjalankan tanpa penyaring
    memproses menurut urutan id, sehingga 585 narasi terbakar tanpa satu pun
    media iklan terbaca - sementara 18 narasi yang MENYEBUT iklan di empat
    stasiun tetap tidak tersentuh.

    `--stasiun` saja tidak cukup menjawab itu: ia memproses seluruh narasi
    stasiun tersebut, dan Sudirman sendirian punya 161. Menggabungkan keduanya
    membuat kuota yang terbatas jatuh tepat pada narasi yang dicari.

    `stasiun` mempersempit ke stasiun tertentu. Ditambahkan 12 Sep karena
    kuota harian penyedia model habis sebelum urutan id sampai ke stasiun
    yang paling perlu - 4 catatan iklan Jakarta Kota tidak pernah terbaca dua
    hari berturut-turut. Ini mengubah URUTAN kerja, bukan syarat masuk: tanpa
    argumen ini seluruh narasi tetap diproses seperti biasa.
    """
    hasil = HasilEkstraksi()
    rantai = Rantai()

    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, ap.narrative
              FROM activity_points ap
              JOIN stations s ON s.id = ap.station_id
             WHERE ap.llm_ec_at IS NULL
               AND (CAST(:stasiun AS text[]) IS NULL
                    OR s.name = ANY(CAST(:stasiun AS text[])))
               AND (CAST(:menyebut AS text) IS NULL
                    OR ap.narrative ~* CAST(:menyebut AS text))
             -- Stasiun yang diskor lebih dulu: kuota harian terbatas, dan
             -- hasil untuk stasiun di luar lingkup skor tidak dipakai menghitung.
             ORDER BY s.served DESC, ap.id
            """
        ),
        {"stasiun": stasiun, "menyebut": menyebut},
    ).all()

    for point_id, station_id, narasi in baris:
        if not (POLA_KANDIDAT.search(narasi or "") or POLA_FASILITAS.search(narasi or "")):
            hasil.dilewati += 1
            continue
        if batas is not None and hasil.diproses >= batas:
            break

        try:
            data = ekstrak_satu(rantai, narasi)
        except SemuaPenyediaHabis as exc:
            # Berhenti, bukan lanjut. Meneruskan hanya menghasilkan ratusan
            # kegagalan beruntun yang menyamar sebagai "sudah diproses".
            hasil.kena_rate_limit = len(baris) - hasil.diproses - hasil.dilewati
            hasil.pesan_rate_limit = str(exc)[:300]
            break
        hasil.diproses += 1
        if data is None:
            hasil.gagal_parse += 1
            continue

        _simpan(session, station_id, point_id, narasi, data, hasil)
        # Skema gabungan sudah memuat kondisi fasilitas, jadi kedua penanda diisi.
        session.execute(
            text(
                "UPDATE activity_points SET llm_ec_at = now(), "
                "llm_fasilitas_at = now(), llm_harga_at = now() WHERE id = :i"
            ),
            {"i": point_id},
        )

        # Commit per entri supaya penarikan panjang yang terputus di tengah
        # tidak kehilangan seluruh pekerjaannya.
        session.commit()

    hasil.penyedia_terpakai = rantai.terpakai
    return hasil


def ekstrak_fasilitas_ulang(
    session: Session, batas: int | None = None, stasiun: list[str] | None = None
) -> HasilEkstraksi:
    """Pass kondisi fasilitas untuk narasi yang dulu diekstrak skema KELUHAN saja.

    Baris `facility_issues` lama milik titik itu dihapus lalu diganti hasil
    skema baru, dalam satu transaksi per titik - supaya satu titik tidak
    pernah berisi campuran hasil dua skema.
    """
    hasil = HasilEkstraksi()
    rantai = Rantai()
    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, ap.narrative
              FROM activity_points ap
              JOIN stations s ON s.id = ap.station_id
             WHERE ap.llm_ec_at IS NOT NULL
               AND ap.llm_fasilitas_at IS NULL
               AND (CAST(:stasiun AS text[]) IS NULL
                    OR s.name = ANY(CAST(:stasiun AS text[])))
             ORDER BY s.served DESC, ap.id
            """
        ),
        {"stasiun": stasiun},
    ).all()

    for point_id, station_id, narasi in baris:
        if not POLA_FASILITAS.search(narasi or ""):
            hasil.dilewati += 1
            session.execute(
                text("UPDATE activity_points SET llm_fasilitas_at = now() WHERE id = :i"),
                {"i": point_id},
            )
            continue
        if batas is not None and hasil.diproses >= batas:
            break
        try:
            data = ekstrak_satu(rantai, narasi, INSTRUKSI_FASILITAS)
        except SemuaPenyediaHabis as exc:
            hasil.kena_rate_limit = len(baris) - hasil.diproses - hasil.dilewati
            hasil.pesan_rate_limit = str(exc)[:300]
            break
        hasil.diproses += 1
        if data is None:
            hasil.gagal_parse += 1
            continue
        session.execute(
            text("DELETE FROM facility_issues WHERE activity_point_id = :i"), {"i": point_id}
        )
        _simpan_fasilitas(session, station_id, point_id, narasi, data, hasil)
        session.execute(
            text("UPDATE activity_points SET llm_fasilitas_at = now() WHERE id = :i"),
            {"i": point_id},
        )
        session.commit()

    session.commit()
    hasil.penyedia_terpakai = rantai.terpakai
    return hasil
