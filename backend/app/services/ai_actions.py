"""Tombol aksi yang menyertai jawaban asisten.

KENAPA DISUSUN DI SINI, BUKAN OLEH MODEL
----------------------------------------
Cara paling cepat membuat jawaban "interaktif" adalah menyuruh model menulis
JSON tombol di akhir jawabannya. Cara itu ditolak karena alasan yang sama
dengan seluruh `ai_tools`: model bisa menyodorkan "Buka stasiun X" untuk
stasiun yang tidak pernah ia hitung, atau bobot simulasi yang tidak pernah ia
jalankan - dan tombol yang tampak resmi membuat karangan itu makin meyakinkan.

Di sini tombol diturunkan dari DUA sumber yang bisa diperiksa:
  1. log alat - alat yang benar-benar dipanggil dan hasilnya
  2. nama stasiun di jawaban - dicocokkan persis ke tabel stasiun, sehingga
     nama yang tidak ada di database tidak pernah menjadi tombol

AI memilih apa yang dihitung; data yang menentukan tombol apa yang muncul.
"""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

MAKS_AKSI = 6
MAKS_STASIUN_DARI_TEKS = 3


def _peta_nama(db: Session) -> dict[str, int]:
    """Nama stasiun terskor -> id. Hanya yang terskor, karena panelnya butuh skor."""
    baris = db.execute(
        text(
            """
            SELECT DISTINCT s.name, s.id
              FROM stations s
              JOIN station_scores sc ON sc.station_id = s.id
            """
        )
    ).all()
    return {nama: sid for nama, sid in baris}


def _nama_di_teks(teks: str, peta: dict[str, int]) -> list[int]:
    """Stasiun yang disebut di jawaban, urut kemunculan.

    Nama terpanjang dicocokkan lebih dulu dan posisinya ditandai, supaya
    "Tanah Abang" tidak juga terbaca sebagai stasiun lain yang namanya bagian
    darinya. Pencocokan peka huruf besar: "Karet" adalah stasiun, "karet" bukan.
    """
    terpakai: list[tuple[int, int]] = []
    ketemu: list[tuple[int, int]] = []
    for nama in sorted(peta, key=len, reverse=True):
        for m in re.finditer(rf"(?<!\w){re.escape(nama)}(?!\w)", teks):
            if any(a < m.end() and m.start() < b for a, b in terpakai):
                continue
            terpakai.append((m.start(), m.end()))
            ketemu.append((m.start(), peta[nama]))
    urut: list[int] = []
    for _, sid in sorted(ketemu):
        if sid not in urut:
            urut.append(sid)
    return urut


def susun_aksi(
    db: Session, reply: str, log: list[dict], station_id_konteks: int | None
) -> list[dict]:
    peta = _peta_nama(db)
    nama_dari_id = {v: k for k, v in peta.items()}
    aksi: list[dict] = []
    kunci: set[tuple] = set()

    def tambah(item: dict) -> None:
        k = (item["jenis"], item.get("station_id"), item.get("tab"),
             tuple(item.get("station_ids") or ()))
        if k in kunci or len(aksi) >= MAKS_AKSI:
            return
        kunci.add(k)
        aksi.append(item)

    def buka(nama: str, tab: str | None = None) -> None:
        sid = peta.get(nama)
        if sid is None:
            return
        label = f"Buka {nama}" if tab is None else f"{tab} {nama}"
        tambah({"jenis": "buka_stasiun", "label": label, "station_id": sid, "tab": tab})

    def bandingkan(nama: list[str]) -> None:
        ids = [peta[n] for n in nama if n in peta][:4]
        if len(ids) >= 2:
            tambah({
                "jenis": "bandingkan",
                "label": f"Bandingkan {len(ids)} stasiun",
                "station_ids": ids,
            })

    for entri in log:
        hasil = entri.get("hasil")
        if not hasil:
            continue
        alat = entri["alat"]

        if alat == "hitung_ulang_sepi" and entri["argumen"].get("bobot"):
            teratas = hasil["peringkat"][0]["stasiun"] if hasil.get("peringkat") else None
            sid = station_id_konteks or peta.get(teratas)
            if sid is not None:
                tambah({
                    "jenis": "simulasi",
                    "label": "Atur ulang bobot ini di panel",
                    "station_id": sid,
                    "bobot": hasil["bobot_dipakai"],
                })
            bandingkan([r["stasiun"] for r in hasil.get("peringkat", [])[:3]])

        elif alat == "cari_stasiun":
            nama = [r["name"] for r in hasil.get("stasiun", [])]
            for n in nama[:2]:
                buka(n)
            bandingkan(nama[:4])

        elif alat == "bandingkan_stasiun":
            bandingkan([r["name"] for r in hasil.get("stasiun", [])])

        elif alat == "tenant_untuk_stasiun":
            buka(hasil["stasiun"], tab="Tenant")

        elif alat == "peringkat_tenant":
            for r in hasil.get("peringkat", [])[:2]:
                buka(r["name"], tab="Tenant")

        elif alat == "kekokohan_peringkat":
            if "stasiun" in hasil:
                buka(hasil["stasiun"])
            else:
                bandingkan([r["stasiun"] for r in hasil.get("kokoh_di_semua_skema", [])])

    # Stasiun yang disebut di jawaban tetapi tidak datang dari alat mana pun.
    for sid in _nama_di_teks(reply, peta)[:MAKS_STASIUN_DARI_TEKS]:
        if sid != station_id_konteks:
            buka(nama_dari_id[sid])

    return aksi
