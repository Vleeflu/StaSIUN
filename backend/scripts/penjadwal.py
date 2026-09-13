"""Penjadwal penyegaran data. Satu proses, tidur sampai jamnya, lalu memanggil.

KENAPA BUKAN CRON SISTEM
-------------------------
Cron menuntut satu berkas jadwal di luar aplikasi, dan berkas itu tidak ikut
`git`, tidak ikut image, dan tidak ikut pindah saat penempatan berganti mesin.
Akibatnya jadwal jadi pengetahuan yang hanya ada di satu server dan hilang
begitu server itu diganti. Penjadwal di dalam image membawa jadwalnya sendiri.

KENAPA BUKAN PUSTAKA PENJADWAL
-------------------------------
Yang dibutuhkan cuma "jalankan sekali sehari pada jam sekian". Menambah
dependensi untuk itu berarti menambah sesuatu yang harus diperbarui dan bisa
rusak, demi perilaku yang muat dalam lima puluh baris.

DUA IRAMA, BUKAN SATU
----------------------
Penyegaran harian menyentuh yang berubah tiap hari: entri Activity baru,
ekstraksinya, lalu skor. Penyegaran mingguan menambahkan tarikan Overpass untuk
titik minat dan guna lahan, yang memakan puluhan menit tetapi isinya nyaris
tidak berubah dari minggu ke minggu.

YANG TIDAK DILAKUKAN PENJADWAL INI
-----------------------------------
Ia tidak menjamin tepat waktu. Kalau prosesnya mati semalaman, jadwal yang
terlewat TIDAK dikejar. Itu pilihan sadar: mengejar jadwal yang terlewat berarti
menjalankan beberapa penyegaran beruntun saat mesin baru bangun, dan penyegaran
berikutnya toh akan mengerjakan seluruh data yang tertinggal.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

JAM_HARIAN = int(os.environ.get("JAM_HARIAN", "19"))
HARI_MINGGUAN = int(os.environ.get("HARI_MINGGUAN", "6"))


def berikutnya(sekarang: datetime) -> datetime:
    """Jam jalan berikutnya sesudah `sekarang`, selalu di masa depan."""
    calon = sekarang.replace(hour=JAM_HARIAN, minute=0, second=0, microsecond=0)
    if calon <= sekarang:
        calon += timedelta(days=1)
    return calon


def jalankan(lambat: bool) -> int:
    perintah = [sys.executable, "-u", "-m", "scripts.refresh_data"]
    if lambat:
        perintah.append("--termasuk-lambat")

    label = "mingguan (termasuk Overpass)" if lambat else "harian"
    print(f"[penjadwal] memulai penyegaran {label}", flush=True)

    hasil = subprocess.run(perintah)
    print(f"[penjadwal] penyegaran selesai, kode keluar {hasil.returncode}", flush=True)
    return hasil.returncode


def main() -> int:
    print(
        f"[penjadwal] hidup. Harian pukul {JAM_HARIAN:02d}:00 UTC, "
        f"penyegaran lambat tiap hari ke-{HARI_MINGGUAN} dalam seminggu "
        f"(0 = Senin).",
        flush=True,
    )

    while True:
        sekarang = datetime.now(timezone.utc)
        target = berikutnya(sekarang)
        tidur = (target - sekarang).total_seconds()
        print(
            f"[penjadwal] menunggu {tidur / 3600:.1f} jam sampai "
            f"{target.isoformat(timespec='minutes')}",
            flush=True,
        )

        # Tidur dipecah supaya penghentian container tidak perlu menunggu
        # sampai jam berikutnya untuk diperhatikan.
        sisa = tidur
        while sisa > 0:
            time.sleep(min(60.0, sisa))
            sisa -= 60.0

        jalankan(lambat=datetime.now(timezone.utc).weekday() == HARI_MINGGUAN)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[penjadwal] dihentikan.", flush=True)
        sys.exit(0)
