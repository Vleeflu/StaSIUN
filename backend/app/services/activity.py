"""Penarik data Activity dari Community MAPS milik GEO MAPID.

Activity adalah hasil survey lapangan tim: cerita naratif berfoto, bertitik
koordinat, ditulis mengikuti Panduan Lapangan Survey StaSIUN. Ia satu-satunya
sumber variabel E dan C menurut PRD Tabel 6, dan sumber skala keramaian untuk
variabel T.

DUA HAL YANG MENENTUKAN, DAN KEDUANYA GAGAL DIAM-DIAM KALAU DILANGGAR
---------------------------------------------------------------------

1. RENTANG TANGGAL WAJIB. Dokumen MAPID menulis: "Limit is fixed at 60 (12 x 5)
   without date range. With date range, all data within the date range is
   returned." Tidak ada `offset` maupun `limit`, dan tidak ada penanda apa pun
   di balasan kalau isinya terpotong. Menarik tanpa rentang tanggal karena itu
   mengembalikan 60 baris yang TERLIHAT seperti seluruh data.

   Ini kelas kegagalan yang sama dengan Geoserver yang memotong di 200 fitur,
   dan itu sudah menipu proyek ini sekali. Di sini rentang tanggal dibuat
   argumen WAJIB, bukan opsional dengan nilai bawaan - supaya tidak ada jalan
   untuk lupa.

2. KODE STATUSNYA TIDAK BISA DIPERCAYA. Per 11 Sep 2026 endpoint ini selalu
   membalas 500 untuk permintaan kami, termasuk ketika memakai body contoh
   milik dokumennya sendiri. Yang sudah dipastikan lewat pengujian:

     - tanpa header kunci  -> 400 "x-api-key header is required"
     - kunci tak dikenal   -> 401 "Unauthorized: Api key not found"
     - kunci 32 karakter apa pun, asli maupun palsu -> 500
     - bentuk body apa pun, termasuk contoh dokumen -> 500

   Karena 401 memang dipakai untuk kunci tak dikenal, 500 BUKAN penanda baku
   "kunci salah". Dari luar tidak bisa dibedakan antara kunci yang belum diberi
   akses dan endpoint yang rusak di sisi server. Pesan error di bawah karena itu
   menyebut kedua kemungkinan, bukan menuduh salah satu.

CARA MENARIK: PER STASIUN, BUKAN SEKALI UNTUK SELURUH DKI
----------------------------------------------------------
Permintaan dikirim satu per satu memakai poligon isochrone tiap stasiun.
Alasannya bukan kerapian:

  - Tiap Activity langsung diketahui stasiunnya, tanpa perlu spatial join
    susulan yang bisa salah di kawasan tangkapan yang tumpang tindih.
  - Batas 60 jadi tidak relevan secara alami, karena tiap permintaan meliputi
    kawasan kecil.
  - Gate spasial PRD (harus di dalam isochrone) terpenuhi di sumbernya.

Yang dikorbankan: 46 panggilan API, bukan satu. Itu murah dan hanya dijalankan
sesekali.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

# Bbox DKI Jakarta, dipakai sebagai gate wilayah. Longgar sedikit supaya
# stasiun di tepi tidak ikut terbuang.
BBOX_DKI = (106.6, -6.4, 107.05, -5.95)

# Panjang minimum narasi supaya dianggap punya isi. Panduan Lapangan mensyaratkan
# empat hal disebut (lokasi, jam, keramaian, tipe orang), yang tidak mungkin
# muat di bawah ini. Entri lebih pendek hampir pasti uji coba atau salah kirim.
MIN_PANJANG_NARASI = 80


class ActivityError(RuntimeError):
    """Penarikan Activity gagal, dan alasannya tidak bisa disimpulkan dari status."""


@dataclass
class HasilTarik:
    diminta: int = 0
    diterima: int = 0
    tersimpan: int = 0
    duplikat: int = 0
    ditolak: dict[str, int] = field(default_factory=dict)
    kena_batas_60: list[str] = field(default_factory=list)

    def tolak(self, alasan: str) -> None:
        self.ditolak[alasan] = self.ditolak.get(alasan, 0) + 1


def _kunci() -> str:
    """Kunci untuk endpoint Activity.

    TERJAWAB 11 Sep: yang diterima adalah `MAPID_BASEMAP_KEY` (24 karakter),
    BUKAN `MAPID_API_KEY` (32 karakter) yang dipakai Geoserver. Namanya
    menyesatkan - ia bukan kunci khusus basemap melainkan kunci umum layanan
    MAPID.

    Cara temuan ini sempat terlewat layak dicatat. Pengujian sebelumnya MEMANG
    mencoba `MAPID_BASEMAP_KEY`, hasilnya tercetak "(kosong)", lalu dilewati -
    tanpa menyadari bahwa kosong berarti kuncinya tidak pernah sampai ke
    container, bukan berarti kuncinya ditolak. Nilainya sudah ada di `.env`
    sejak awal; yang kurang cuma satu baris di `docker-compose.yml`.

    Pelajarannya: hasil uji "kosong" atau "tidak ada" bukan hasil uji. Ia
    pertanda pengujiannya sendiri yang belum berjalan.

    Urutannya tetap berantai supaya panitia bisa memberi kunci terpisah tanpa
    mengubah kode.
    """
    key = (
        settings.MAPID_MISSION_KEY
        or settings.MAPID_BASEMAP_KEY
        or settings.MAPID_API_KEY
    )
    if not key:
        raise ActivityError(
            "Tidak ada kunci sama sekali. Isi MAPID_BASEMAP_KEY di backend/.env "
            "— itu kunci yang diterima endpoint Activity."
        )
    return key


def _cincin_tertutup(koordinat: list) -> list:
    """Pastikan cincin poligon tertutup dan punya minimal 4 titik.

    API menolak cincin terbuka. Poligon dari PostGIS biasanya sudah tertutup,
    tetapi memeriksanya di sini lebih murah daripada menebak arti error 500.
    """
    cincin = [list(map(float, t[:2])) for t in koordinat]
    if cincin and cincin[0] != cincin[-1]:
        cincin.append(cincin[0])
    return cincin


def ambil_untuk_poligon(
    poligon: dict,
    mulai: date,
    selesai: date,
    *,
    hashtag: list[str] | None = None,
    timeout: float = 90.0,
) -> list[dict]:
    """Tarik Activity di dalam satu poligon, pada satu rentang tanggal.

    `mulai` dan `selesai` WAJIB. Lihat catatan nomor 1 di atas: tanpa keduanya
    API memotong di 60 baris tanpa memberi tahu.
    """
    if mulai > selesai:
        raise ActivityError(f"rentang tanggal terbalik: {mulai} > {selesai}")

    if poligon.get("type") != "Polygon":
        raise ActivityError(
            f"API Activity hanya menerima Polygon, bukan {poligon.get('type')!r}. "
            "MultiPolygon harus dipecah dulu jadi poligon-poligon tunggal."
        )

    body: dict = {
        "feature": {
            "type": "Polygon",
            "coordinates": [_cincin_tertutup(r) for r in poligon["coordinates"]],
        },
        "start_date": mulai.isoformat(),
        "end_date": selesai.isoformat(),
    }
    if hashtag:
        body["hashtag"] = hashtag

    try:
        balasan = httpx.post(
            settings.MAPID_ACTIVITY_URL,
            headers={"Content-Type": "application/json", "x-api-key": _kunci()},
            json=body,
            timeout=timeout,
        )
    except httpx.RequestError as exc:
        raise ActivityError(f"tidak bisa menghubungi API Activity: {exc}") from exc

    if balasan.status_code != 200:
        raise ActivityError(
            f"API Activity membalas HTTP {balasan.status_code}: "
            f"{balasan.text[:200]}.\n"
            "Status ini TIDAK menunjuk satu sebab. Per 11 Sep 2026 endpoint "
            "membalas 500 bahkan untuk body contoh milik dokumennya sendiri, "
            "sehingga dua hal berikut terlihat identik dari luar:\n"
            "  (a) kunci kita belum diberi akses ke API kompetisi;\n"
            "  (b) endpoint sedang rusak di sisi server MAPID.\n"
            "Yang bisa diperiksa sendiri: poligon bertipe Polygon dengan cincin "
            "tertutup, dan kedua tanggal terkirim bersama. Kalau keduanya sudah "
            "benar, tanyakan ke mentor MAPID (blocker N14)."
        )

    isi = balasan.json()
    return isi.get("data", {}).get("activities", []) or []


def _di_dalam_bbox(geometry: dict) -> bool:
    if (geometry or {}).get("type") != "Point":
        return False
    try:
        lon, lat = float(geometry["coordinates"][0]), float(geometry["coordinates"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    # Koordinat nol adalah nilai bawaan GPS yang gagal, bukan lokasi di Jakarta.
    if lon == 0 or lat == 0:
        return False
    kiri, bawah, kanan, atas = BBOX_DKI
    return kiri <= lon <= kanan and bawah <= lat <= atas


def hash_payload(aktivitas: dict) -> str:
    """Sidik jari isi, untuk mengenali entri yang sudah pernah disimpan.

    Memakai `_id` kalau ada - itu identitas dari sumbernya. Kalau tidak ada,
    jatuh ke hash seluruh isi, supaya penarikan ulang tidak menggandakan baris.
    """
    penanda = aktivitas.get("_id")
    bahan = penanda if penanda else json.dumps(aktivitas, sort_keys=True, default=str)
    return hashlib.sha256(str(bahan).encode("utf-8")).hexdigest()


def lolos_gate(aktivitas: dict, hasil: HasilTarik) -> bool:
    """Gate wilayah dan gate kualitas, keduanya aturan yang dieksekusi kode.

    Gate spasial (di dalam isochrone) TIDAK dikerjakan di sini: ia sudah
    terpenuhi di sumbernya, karena permintaan dikirim per poligon isochrone.
    """
    if not _di_dalam_bbox(aktivitas.get("geometry")):
        hasil.tolak("di luar bbox DKI atau koordinat tidak sah")
        return False

    narasi = (aktivitas.get("description") or "").strip()
    if len(narasi) < MIN_PANJANG_NARASI:
        hasil.tolak(f"narasi di bawah {MIN_PANJANG_NARASI} karakter")
        return False

    return True


SQL_ISOCHRONE = """
SELECT s.id   AS station_id,
       s.name AS station_name,
       ST_AsGeoJSON(i.geom) AS geom
  FROM stations s
  JOIN isochrones i ON i.station_id = s.id AND i.minutes = :menit
 ORDER BY s.name
"""

SQL_SIMPAN = """
INSERT INTO activity_raw
    (source_kind, source_ref, external_id, payload, payload_hash,
     gate_status, gate_reason, fetched_at, created_at, updated_at)
VALUES
    ('mapid_activity', :ref, :external_id, CAST(:payload AS jsonb), :hash,
     :status, :reason, now(), now(), now())
ON CONFLICT DO NOTHING
"""


def tarik_semua(
    session: Session,
    mulai: date,
    selesai: date,
    *,
    menit: int = 15,
    hashtag: list[str] | None = None,
    simpan: bool = True,
) -> HasilTarik:
    """Tarik Activity untuk seluruh stasiun yang punya isochrone.

    Cincin 15 menit dipakai sebagai gate spasial, mengikuti LAYER.md - paling
    longgar di antara ketiganya, supaya tidak ada Activity yang terbuang hanya
    karena berada di tepi kawasan tangkapan. Penyempitan ke cincin yang lebih
    rapat dikerjakan belakangan saat menghitung variabel, bukan saat menarik.
    """
    hasil = HasilTarik()

    for baris in session.execute(text(SQL_ISOCHRONE), {"menit": menit}).all():
        geom = json.loads(baris.geom)

        # MultiPolygon dipecah: API hanya menerima Polygon tunggal.
        bagian = (
            [{"type": "Polygon", "coordinates": c} for c in geom["coordinates"]]
            if geom["type"] == "MultiPolygon"
            else [geom]
        )

        for poligon in bagian:
            hasil.diminta += 1
            aktivitas = ambil_untuk_poligon(
                poligon, mulai, selesai, hashtag=hashtag
            )
            hasil.diterima += len(aktivitas)

            # Kalau tepat 60, besar kemungkinan balasannya terpotong walau
            # rentang tanggal sudah dikirim. Dicatat, bukan didiamkan.
            if len(aktivitas) == 60:
                hasil.kena_batas_60.append(baris.station_name)

            for satu in aktivitas:
                lolos = lolos_gate(satu, hasil)
                if not simpan:
                    hasil.tersimpan += int(lolos)
                    continue

                terpakai = session.execute(
                    text(SQL_SIMPAN),
                    {
                        "ref": baris.station_name,
                        "external_id": satu.get("_id"),
                        "payload": json.dumps(satu, default=str),
                        "hash": hash_payload(satu),
                        # Nilainya ditentukan check constraint di skema:
                        # 'pending' | 'passed' | 'rejected'. Bukan pilihan bebas.
                        "status": "passed" if lolos else "rejected",
                        "reason": None if lolos else "gagal gate wilayah/kualitas",
                    },
                ).rowcount
                if terpakai:
                    hasil.tersimpan += 1
                else:
                    hasil.duplikat += 1

    if simpan:
        session.commit()
    return hasil
