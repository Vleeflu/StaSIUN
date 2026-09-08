"""Stasiun yang hak penamaannya sudah terjual, dan kelompok pembandingnya.

Ditemukan 7 Sep: nama stasiun MRT dan LRT di data OpenStreetMap sudah memuat
nama sponsornya, dan itu tersimpan di tabel `stations` sejak seed pertama.
Modul ini mengubah temuan itu dari catatan di dokumen menjadi sesuatu yang bisa
dipanggil kode. Riwayatnya di ADJUSTMENT.md bagian 7.10.

DUA KEPUTUSAN YANG MENENTUKAN KEABSAHAN PEMAKAIANNYA
----------------------------------------------------

1. Daftar ditulis tangan, BUKAN dicocokkan dengan pola.
   Godaannya menulis aturan semacam "kalau nama stasiun mengandung nama merek
   maka bersponsor". Itu ditolak: mencocokkan merek pada teks bebas gagal
   diam-diam di kedua arah — "Bank Jakarta" tertangkap, tetapi nama tempat
   seperti "ASEAN" bisa ikut tertangkap sebagai merek. Dua belas baris yang
   ditulis eksplisit bisa diperiksa mata manusia; regex tidak.

2. Pembandingnya HANYA MRT dan LRT, bukan seluruh stasiun.
   Stasiun KAI Commuter tidak pernah menawarkan hak penamaan dengan cara yang
   sama. Memasukkannya sebagai "belum bersponsor" akan mencampur dua sebab yang
   berbeda: belum terjual karena kurang menarik, dan belum terjual karena
   memang tidak pernah dijual. Perancu itu membuat perbandingan apa pun jadi
   tidak sah.

CATATAN KEHATI-HATIAN
---------------------
Nama-nama ini berasal dari OpenStreetMap, bukan pengumuman resmi operator.
Sebelum dipakai sebagai dasar valuasi rupiah, daftarnya wajib dicocokkan ke
sumber resmi MRT Jakarta dan LRT — kesepakatan bisa berakhir atau berganti
tanpa OSM ikut diperbarui.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.station import Station

# Jaringan yang benar-benar memperjualbelikan hak penamaan stasiun. Hanya di
# sinilah "belum bersponsor" berarti "belum terjual", bukan "tidak dijual".
JARINGAN_BERSPONSOR = ("MRT Jakarta", "LRT Jakarta", "LRT Jabodebek")

# nama_di_database -> (nama dasar stasiun, nama sponsor)
SPONSOR = {
    "Blok A VISA": ("Blok A", "VISA"),
    "Blok M BCA": ("Blok M", "BCA"),
    "Bundaran HI Bank Jakarta": ("Bundaran HI", "Bank Jakarta"),
    "Cipete Raya TUKU": ("Cipete Raya", "TUKU"),
    "Dukuh Atas BNI": ("Dukuh Atas", "BNI"),
    "Fatmawati Indomaret": ("Fatmawati", "Indomaret"),
    "Istora Mandiri": ("Istora", "Mandiri"),
    "Lebak Bulus Bank Syariah Indonesia": ("Lebak Bulus", "Bank Syariah Indonesia"),
    "Senayan Mastercard": ("Senayan", "Mastercard"),
    "Setiabudi Astra": ("Setiabudi", "Astra"),
    "Dukuh Atas Bank Syariah Indonesia": ("Dukuh Atas", "Bank Syariah Indonesia"),
    "Boulevard Utara Summarecon Mall": ("Boulevard Utara", "Summarecon Mall"),
}

# Nama yang MIRIP sponsor tetapi bukan. Didaftar eksplisit supaya keputusan ini
# terlihat dan bisa dibantah, bukan tersembunyi sebagai kelalaian.
#   "ASEAN Headquarters" -> merujuk Sekretariat ASEAN yang memang berlokasi di
#   sana. Itu nama tempat, bukan merek yang membeli hak penamaan.
BUKAN_SPONSOR = {"ASEAN Headquarters"}


@dataclass
class StatusPenamaan:
    station_id: int
    nama_lengkap: str
    jaringan: str
    nama_dasar: str
    sponsor: str | None

    @property
    def bersponsor(self) -> bool:
        return self.sponsor is not None


def klasifikasi(session: Session) -> list[StatusPenamaan]:
    """Bagi stasiun MRT dan LRT jadi kelompok bersponsor dan belum."""
    rows = session.execute(
        select(Station.id, Station.name, Station.types)
        .where(Station.types.any(JARINGAN_BERSPONSOR[0]) | Station.types.overlap(list(JARINGAN_BERSPONSOR)))
        .order_by(Station.name)
    ).all()

    hasil = []
    for r in rows:
        jaringan = r.types[0] if r.types else "Lainnya"
        if jaringan not in JARINGAN_BERSPONSOR:
            continue
        dasar, sponsor = SPONSOR.get(r.name, (r.name, None))
        hasil.append(
            StatusPenamaan(
                station_id=r.id,
                nama_lengkap=r.name,
                jaringan=jaringan,
                nama_dasar=dasar,
                sponsor=sponsor,
            )
        )
    return hasil


def periksa_daftar(session: Session) -> list[str]:
    """Cocokkan daftar tertulis tangan di atas dengan isi database.

    Daftar yang ditulis tangan punya satu kelemahan: dia membeku sementara
    datanya bisa berubah. Fungsi ini membuat perbedaan itu berbunyi, bukan
    mengendap. Kembalian berupa daftar keluhan; kosong berarti cocok.

    Dipanggil di awal skrip mana pun yang memakai SPONSOR, supaya nama yang
    berubah di OSM ketahuan sebagai keluhan, bukan sebagai stasiun yang
    diam-diam berpindah kelompok.
    """
    nama_di_db = {
        r.name
        for r in session.execute(select(Station.name, Station.types)).all()
        if r.types and r.types[0] in JARINGAN_BERSPONSOR
    }

    keluhan = []
    for nama in SPONSOR:
        if nama not in nama_di_db:
            keluhan.append(f"terdaftar bersponsor tetapi tidak ada di database: {nama!r}")
    for nama in BUKAN_SPONSOR:
        if nama not in nama_di_db:
            keluhan.append(f"terdaftar sebagai bukan-sponsor tetapi tidak ada di database: {nama!r}")
    return keluhan


def ringkas(daftar: list[StatusPenamaan]) -> dict:
    """Angka ringkas untuk laporan dan pemeriksaan daya uji statistik."""
    bersponsor = [d for d in daftar if d.bersponsor]
    belum = [d for d in daftar if not d.bersponsor]
    return {
        "total": len(daftar),
        "bersponsor": len(bersponsor),
        "belum": len(belum),
        "sponsor": sorted({d.sponsor for d in bersponsor if d.sponsor}),
    }
