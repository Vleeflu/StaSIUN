"""Jalankan seluruh pipeline data berurutan, satu perintah, aman diulang.

KENAPA BERKAS INI ADA
----------------------
Sampai sekarang tiap tahap dijalankan sendiri-sendiri dari komputer pengembang,
dan urutannya harus diingat manusia. Itu berjalan selama yang menjalankan tahu
bahwa TSI butuh SEPI, dan SEPI butuh hasil ekstraksi. Begitu aplikasinya publik
dan datanya harus menyegar sendiri, urutan itu tidak boleh lagi bergantung pada
ingatan siapa pun.

URUTANNYA BUKAN SELERA
-----------------------
Tiap tahap memakai keluaran tahap sebelumnya:

    Activity mentah -> titik + skala keramaian -> arketipe -> E dan C
                                                               |
                                            skor SEPI <--------+
                                                |
                                            skor TSI

Menjalankan `compute_tsi` sebelum `compute_sepi` bukan sekadar lebih lambat, ia
memakai pengali konektivitas dari skor LAMA, dan hasilnya terlihat wajar
sehingga salahnya tidak ketahuan.

TAHAP LAMBAT DIPISAH
---------------------
Guna lahan dan titik minat ditarik dari Overpass, yang membatasi laju
permintaan dan kerap membalas 429 atau 504. Sekali jalan bisa memakan
setengah jam, sementara isinya nyaris tidak berubah dari minggu ke minggu.
Keduanya karena itu TIDAK ikut jadwal harian; ia punya penanda `lambat` dan
hanya jalan kalau diminta.

SATU JALAN PADA SATU WAKTU
---------------------------
Dua penyegaran yang berjalan bersamaan akan saling menimpa: keduanya menulis
`station_scores` untuk pita yang sama. Kunci berkas mencegahnya, dan kalau
proses sebelumnya mati tanpa sempat melepas kunci, kunci yang lebih tua dari
`UMUR_KUNCI_MAKS` dianggap basi lalu diambil alih.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BERKAS_KUNCI = Path(os.environ.get("REFRESH_LOCK", "/tmp/stasiun_refresh.lock"))
BERKAS_STATUS = Path(os.environ.get("REFRESH_STATUS", "/tmp/stasiun_refresh.json"))

# Penyegaran terpanjang yang pernah tercatat sekitar 40 menit (guna lahan penuh
# saat Overpass sedang membatasi laju). Dua jam memberi ruang lega tanpa
# membuat kunci yang benar-benar macet tertahan semalaman.
UMUR_KUNCI_MAKS = 2 * 60 * 60


@dataclass
class Tahap:
    nama: str
    modul: str
    argumen: list[str] = field(default_factory=list)
    lambat: bool = False
    # Tahap yang boleh gagal tanpa menghentikan sisanya. Ekstraksi LLM masuk
    # kategori ini: kuota penyedia bisa habis di tengah jalan, dan itu bukan
    # alasan untuk membatalkan penghitungan skor atas data yang sudah ada.
    boleh_gagal: bool = False
    keterangan: str = ""


def susun_tahap(menit: int) -> list[Tahap]:
    return [
        Tahap(
            "activity",
            "scripts.ingest_activity",
            lambat=False,
            boleh_gagal=True,
            keterangan="tarik entri Activity baru dari GEO MAPID",
        ),
        Tahap(
            "parse",
            "scripts.parse_activity",
            keterangan="ubah entri mentah jadi titik dan skala keramaian",
        ),
        Tahap(
            "arketipe",
            "scripts.hitung_arketipe",
            keterangan="latih ulang LDA dan beri label arketipe tiap titik",
        ),
        Tahap(
            "ekstraksi",
            "scripts.extract_ec",
            boleh_gagal=True,
            keterangan="ekstrak variabel E dan C dari narasi memakai LLM",
        ),
        Tahap(
            "harga",
            "scripts.extract_ec",
            argumen=["--harga-ulang"],
            boleh_gagal=True,
            keterangan="panen harga menu dari narasi yang sudah diekstrak",
        ),
        Tahap(
            "poi",
            "scripts.ingest_poi",
            lambat=True,
            keterangan="tarik ulang titik minat dari Overpass",
        ),
        Tahap(
            "kawasan",
            "scripts.ingest_area_profile",
            argumen=["--menit", str(menit)],
            lambat=True,
            keterangan="tarik ulang guna lahan dari Overpass",
        ),
        Tahap(
            "sepi",
            "scripts.compute_sepi",
            argumen=["--minutes", str(menit)],
            keterangan="hitung ulang skor SEPI dan peringkatnya",
        ),
        Tahap(
            "tsi",
            "scripts.compute_tsi",
            argumen=["--minutes", str(menit)],
            keterangan="hitung ulang indeks kelayakan usaha",
        ),
    ]


def ambil_kunci() -> bool:
    """True kalau kunci berhasil diambil. Kunci basi diambil alih."""
    if BERKAS_KUNCI.exists():
        umur = time.time() - BERKAS_KUNCI.stat().st_mtime
        if umur < UMUR_KUNCI_MAKS:
            return False
        print(
            f"! kunci berumur {umur / 60:.0f} menit dianggap basi, diambil alih.",
            flush=True,
        )
    BERKAS_KUNCI.parent.mkdir(parents=True, exist_ok=True)
    BERKAS_KUNCI.write_text(str(os.getpid()), encoding="utf-8")
    return True


def lepas_kunci() -> None:
    try:
        BERKAS_KUNCI.unlink()
    except FileNotFoundError:
        pass


def tulis_status(isi: dict) -> None:
    """Simpan ringkasan penyegaran terakhir supaya bisa dibaca tanpa log."""
    try:
        BERKAS_STATUS.parent.mkdir(parents=True, exist_ok=True)
        BERKAS_STATUS.write_text(json.dumps(isi, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"! status tidak tersimpan: {exc}", flush=True)


def jalankan(tahap: Tahap) -> tuple[bool, float, str]:
    mulai = time.monotonic()
    perintah = [sys.executable, "-u", "-m", tahap.modul, *tahap.argumen]
    print(f"\n=== {tahap.nama}: {tahap.keterangan}", flush=True)
    hasil = subprocess.run(perintah, capture_output=True, text=True)
    lama = time.monotonic() - mulai

    keluaran = (hasil.stdout or "") + (hasil.stderr or "")
    for baris in keluaran.strip().splitlines()[-12:]:
        print("   " + baris, flush=True)

    # Baris terakhir yang tidak kosong biasanya ringkasan tahapnya.
    ringkas = next(
        (b.strip() for b in reversed(keluaran.strip().splitlines()) if b.strip()), ""
    )
    return hasil.returncode == 0, lama, ringkas[:200]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--menit", type=int, default=10, help="pita isochrone yang diskor")
    p.add_argument(
        "--termasuk-lambat",
        action="store_true",
        help="ikutkan tahap Overpass (titik minat dan guna lahan). Pakai mingguan "
        "atau bulanan, bukan harian",
    )
    p.add_argument(
        "--hanya",
        nargs="+",
        default=None,
        help="jalankan tahap tertentu saja, sebut namanya",
    )
    p.add_argument(
        "--daftar",
        action="store_true",
        help="tampilkan daftar tahap lalu keluar, tanpa menjalankan apa pun",
    )
    args = p.parse_args()

    tahap = susun_tahap(args.menit)

    if args.daftar:
        for t in tahap:
            tanda = " [lambat]" if t.lambat else ""
            print(f"{t.nama:12}{tanda:10} {t.keterangan}")
        return 0

    if args.hanya:
        diminta = set(args.hanya)
        tidak_dikenal = diminta - {t.nama for t in tahap}
        if tidak_dikenal:
            print(f"! tahap tidak dikenal: {', '.join(sorted(tidak_dikenal))}")
            return 2
        antrian = [t for t in tahap if t.nama in diminta]
    else:
        antrian = [t for t in tahap if args.termasuk_lambat or not t.lambat]

    if not ambil_kunci():
        print("! penyegaran lain sedang berjalan. Tidak ada yang dikerjakan.")
        return 0

    mulai = datetime.now(timezone.utc)
    catatan: list[dict] = []
    gagal_fatal = False

    try:
        for t in antrian:
            sukses, lama, ringkas = jalankan(t)
            catatan.append(
                {
                    "tahap": t.nama,
                    "sukses": sukses,
                    "detik": round(lama, 1),
                    "ringkas": ringkas,
                    "boleh_gagal": t.boleh_gagal,
                }
            )
            if sukses:
                print(f"   selesai dalam {lama:.0f} detik", flush=True)
                continue

            if t.boleh_gagal:
                print(
                    f"!  {t.nama} gagal, tetapi tahap ini boleh gagal. Diteruskan.",
                    flush=True,
                )
                continue

            # Tahap wajib yang gagal menghentikan sisanya. Meneruskan berarti
            # menghitung skor di atas bahan yang belum lengkap, dan hasilnya
            # tetap tersimpan rapi tanpa satu pun tanda bahwa ia keliru.
            print(f"!! {t.nama} gagal. Sisa tahap dibatalkan.", flush=True)
            gagal_fatal = True
            break
    finally:
        lepas_kunci()

    selesai = datetime.now(timezone.utc)
    status = {
        "mulai": mulai.isoformat(),
        "selesai": selesai.isoformat(),
        "detik_total": round((selesai - mulai).total_seconds(), 1),
        "termasuk_lambat": args.termasuk_lambat,
        "berhasil": not gagal_fatal,
        "tahap": catatan,
    }
    tulis_status(status)

    berhasil = sum(1 for c in catatan if c["sukses"])
    print(
        f"\n{berhasil} dari {len(catatan)} tahap berhasil "
        f"dalam {status['detik_total'] / 60:.1f} menit.",
        flush=True,
    )
    return 1 if gagal_fatal else 0


if __name__ == "__main__":
    sys.exit(main())
