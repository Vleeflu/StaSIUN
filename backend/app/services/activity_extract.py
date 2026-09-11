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

from openai import APIError, OpenAI, RateLimitError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

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

SKEMA = """{
  "iklan": [{"jenis": "str", "jumlah": int, "status": "terpakai|kosong", "kutipan": "str"}],
  "lapak": {"unit_total": int|null, "unit_terisi": int|null, "kutipan": "str"},
  "tenant": [{"nama": "str", "kategori": "str", "status": "aktif|tutup|kosong", "kutipan": "str"}],
  "fasilitas": [{"jenis": "str", "ringkasan": "str", "sentimen": float, "kutipan": "str"}]
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
6. Jangan memasukkan apa pun yang tidak tertulis di teks."""

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
    kutipan_ditolak: int = 0
    gagal_parse: int = 0
    kena_rate_limit: int = 0
    pesan_rate_limit: str | None = None
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
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY belum diisi di backend/.env")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


class RateLimitHabis(RuntimeError):
    """Kuota penyedia habis. Dibedakan dari kegagalan lain karena obatnya beda:
    menunggu atau menaikkan tier, bukan memperbaiki prompt."""


# Batas penyedia ada dua jenis dan obatnya berbeda. Batas PER MENIT (Groq free
# tier: 8.000 token/menit) pulih dalam hitungan detik - menunggu lalu mencoba
# lagi adalah jawaban yang benar. Batas PER HARI tidak akan pulih dengan
# menunggu beberapa detik, jadi di situ proses berhenti. Versi pertama
# memperlakukan keduanya sama dan berhenti di batas per menit, sehingga
# ratusan narasi tidak pernah diproses dalam sekali jalan.
PENANDA_HARIAN = re.compile(r"per\s+day|\bTPD\b|\bRPD\b", re.IGNORECASE)
TUNGGU = re.compile(r"try again in\s+(?:(\d+)m)?\s*([\d.]+)(ms|s)", re.IGNORECASE)
MAKS_COBA = 6


def _lama_tunggu(pesan: str) -> float:
    m = TUNGGU.search(pesan)
    if not m:
        return 15.0
    menit = int(m.group(1) or 0)
    angka = float(m.group(2))
    detik = angka / 1000 if m.group(3).lower() == "ms" else angka
    return menit * 60 + detik + 1.0


def ekstrak_satu(
    klien: OpenAI, narasi: str, instruksi: str = INSTRUKSI
) -> dict | None:
    """Minta model mengekstrak satu narasi.

    Mengembalikan None kalau balasannya tidak terbaca sebagai JSON, dan
    MELEMPAR `RateLimitHabis` kalau kuota HARIAN habis. Batas per menit
    ditunggu, bukan dilempar.

    Perbedaan None vs RateLimitHabis penting dan sempat saya samarkan: versi
    pertama menangkap RateLimitError lalu mengembalikan None, sehingga entri
    yang sebenarnya kehabisan kuota dilaporkan sebagai "balasan tidak terbaca
    sebagai JSON". Dua sebab yang obatnya berbeda tampil sebagai satu.

    `reasoning_effort: low` memangkas token penalaran gpt-oss. Pekerjaannya
    menyalin dan menstrukturkan, bukan menalar panjang; token yang dihemat
    berarti lebih banyak narasi per kuota harian.
    """
    for _ in range(MAKS_COBA):
        try:
            balasan = klien.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": instruksi},
                    {"role": "user", "content": narasi},
                ],
                response_format={"type": "json_object"},
                extra_body={"reasoning_effort": "low"},
            )
            break
        except RateLimitError as exc:
            pesan = str(exc)
            if PENANDA_HARIAN.search(pesan):
                raise RateLimitHabis(pesan) from exc
            time.sleep(_lama_tunggu(pesan))
        except APIError:
            return None
    else:
        raise RateLimitHabis("batas per menit tidak kunjung pulih setelah beberapa percobaan")

    isi = balasan.choices[0].message.content or ""
    try:
        return json.loads(isi)
    except json.JSONDecodeError:
        return None


def _simpan(
    session: Session, station_id: int | None, point_id: int, narasi: str,
    data: dict, hasil: HasilEkstraksi
) -> None:
    """Tulis hasil ekstraksi, membuang tiap bagian yang kutipannya tidak sah."""
    if station_id is None:
        return

    for item in data.get("iklan") or []:
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

    lapak = data.get("lapak") or {}
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

    for item in data.get("tenant") or []:
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

    _simpan_fasilitas(session, station_id, point_id, narasi, data, hasil)


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
    for item in (data.get("fasilitas") or data.get("keluhan") or []):
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


def ekstrak_semua(session: Session, batas: int | None = None) -> HasilEkstraksi:
    """Ekstrak E dan C dari seluruh narasi yang berpeluang memuatnya."""
    hasil = HasilEkstraksi()
    klien = _klien()

    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, ap.narrative
              FROM activity_points ap
              JOIN stations s ON s.id = ap.station_id
             WHERE ap.llm_ec_at IS NULL
             -- Stasiun yang diskor lebih dulu: kuota harian terbatas, dan
             -- hasil untuk stasiun di luar lingkup skor tidak dipakai menghitung.
             ORDER BY s.served DESC, ap.id
            """
        )
    ).all()

    for point_id, station_id, narasi in baris:
        if not (POLA_KANDIDAT.search(narasi or "") or POLA_FASILITAS.search(narasi or "")):
            hasil.dilewati += 1
            continue
        if batas is not None and hasil.diproses >= batas:
            break

        try:
            data = ekstrak_satu(klien, narasi)
        except RateLimitHabis as exc:
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
                "UPDATE activity_points SET llm_ec_at = now(), llm_fasilitas_at = now() "
                "WHERE id = :i"
            ),
            {"i": point_id},
        )

        # Commit per entri supaya penarikan panjang yang terputus di tengah
        # tidak kehilangan seluruh pekerjaannya.
        session.commit()

    return hasil


def ekstrak_fasilitas_ulang(session: Session, batas: int | None = None) -> HasilEkstraksi:
    """Pass kondisi fasilitas untuk narasi yang dulu diekstrak skema KELUHAN saja.

    Baris `facility_issues` lama milik titik itu dihapus lalu diganti hasil
    skema baru, dalam satu transaksi per titik - supaya satu titik tidak
    pernah berisi campuran hasil dua skema.
    """
    hasil = HasilEkstraksi()
    klien = _klien()
    baris = session.execute(
        text(
            """
            SELECT ap.id, ap.station_id, ap.narrative
              FROM activity_points ap
              JOIN stations s ON s.id = ap.station_id
             WHERE ap.llm_ec_at IS NOT NULL
               AND ap.llm_fasilitas_at IS NULL
             ORDER BY s.served DESC, ap.id
            """
        )
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
            data = ekstrak_satu(klien, narasi, INSTRUKSI_FASILITAS)
        except RateLimitHabis as exc:
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
    return hasil
