"""Menyusun konteks yang dikirim ke model bahasa sebelum menjawab.

Isinya dua hal: penjelasan tentang proyek StaSIUN, dan ringkasan seluruh
stasiun yang benar-benar ada di database. Tanpa ini modelnya cuma menebak dari
ingatan umum, dan jawabannya jadi tidak nyambung dengan data kita.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.station import Station

PROJECT_BRIEF = """Kamu asisten di dalam StaSIUN (Station Spatial Intelligence for
Urban Network), sebuah WebGIS untuk menilai potensi ruang komersial stasiun
KAI Commuter di DKI Jakarta.

MASALAH YANG DIKERJAKAN
Pendapatan non-farebox KAI baru sekitar 4% dari total, jauh di bawah operator
sebanding seperti MRT Jakarta yang 30-40%. Penyebabnya ruang komersial stasiun
dihargai dengan perkiraan, bukan pengukuran. UMKM juga ragu menyewa lapak
karena risiko lokasinya tidak terukur.

TIGA FITUR YANG DIRANCANG
1. Ad-Space Opportunity - peringkat kategori merek per zona di dalam stasiun,
   perkiraan nilai sewa, pemicu Facility Sponsorship berbasis CSR.
2. Tenant Valuation - pencocokan kategori tenant untuk lapak kosong, plus
   Tenant Survival Index (TSI) skala 0-100.
3. Naming Rights - perkiraan nilai kontrak tahunan dan peringkat kandidat
   sponsor.

MESIN SKOR
SEPI kependekan dari Spatial Economic Potential Index. Jangan mengarang
kepanjangan lain.
SEPI = w1*T + w2*E + w3*A + w4*U + w5*C, dengan T Transportasi, E Ekonomi,
A Aksesibilitas, U Urban, C Komersial. Bobotnya gabungan Entropy Weighting dan
AHP (syarat konsistensi CR < 0,10), peringkat akhir memakai TOPSIS. Zona
dihitung dari isochrone jalan kaki 5/10/15 menit berbasis jaringan pejalan
OpenStreetMap, bukan lingkaran buffer.

YANG SUDAH ADA DATANYA HARI INI
Hanya titik stasiun: nama, kode KAI, lin yang dilayani, status dilayani atau
cuma dilintasi, kecamatan, alamat, dan koordinat. Daftar lengkapnya ada di
bawah.

YANG BELUM ADA - JANGAN SEKALI-KALI DIKARANG
Skor SEPI dan peringkatnya, TSI, nilai naming rights, footfall, dwell-time,
arketipe LDA, poligon isochrone, serta data mitra MAPID (StrukGo, MenuGo,
PropertiGo, Activity). Semuanya BELUM dihitung. Kalau ditanya soal ini, katakan
terus terang bahwa angkanya belum ada, lalu jelaskan bagaimana nanti dihitung.
Jangan pernah menyebut angka karangan, termasuk sebagai contoh, kecuali kamu
menyatakan dengan jelas bahwa itu ilustrasi.

CARA MENJAWAB
Pakai bahasa Indonesia yang santai tapi padat. Jawab dari daftar stasiun di
bawah kalau pertanyaannya memang bisa dijawab dari situ, dan sebut nama
stasiunnya. Kalau pertanyaannya jauh di luar urusan StaSIUN dan perkeretaan
Jabodetabek, arahkan kembali dengan sopan. Balas dalam beberapa kalimat atau
daftar pendek.

Tulis dalam teks biasa. Jangan memakai markdown seperti **tebal**, *miring*,
atau judul berawalan #. Jangan memakai notasi LaTeX seperti $...$ atau
subscript w_1; tulis saja w1. Jangan membuat tabel. Kalau perlu daftar, pakai
tanda hubung di awal baris."""


def _station_line(row) -> str:
    parts = [row.name]

    if row.code:
        parts.append(f"[{row.code}]")

    if row.lines:
        parts.append("lin " + ",".join(row.lines))

    if len(row.lines) > 1:
        parts.append("interchange")

    if not row.served:
        parts.append("TIDAK dilayani, kereta lewat tanpa berhenti")

    if row.kecamatan:
        parts.append(row.kecamatan)

    return "- " + " | ".join(parts)


def build_station_digest(db: Session) -> str:
    """Ringkasan seluruh stasiun, dikelompokkan per jaringan."""
    rows = db.execute(
        select(
            Station.name,
            Station.code,
            Station.types,
            Station.lines,
            Station.served,
            Station.kecamatan,
        ).order_by(Station.name)
    ).all()

    if not rows:
        return "DAFTAR STASIUN\n(database masih kosong)"

    by_network: dict[str, list] = defaultdict(list)
    for row in rows:
        network = row.types[0] if row.types else "Lainnya"
        by_network[network].append(row)

    blocks = [f"DAFTAR STASIUN DI DATABASE ({len(rows)} titik)"]

    for network in sorted(by_network, key=lambda n: -len(by_network[n])):
        group = by_network[network]
        blocks.append(f"\n{network} ({len(group)} stasiun):")
        blocks.extend(_station_line(row) for row in group)

    return "\n".join(blocks)


def build_chat_context(db: Session, station_id: int | None = None) -> str:
    """Gabungan penjelasan proyek, daftar stasiun, dan stasiun yang dibuka."""
    parts = [PROJECT_BRIEF, "", build_station_digest(db)]

    if station_id is not None:
        focus = db.get(Station, station_id)
        if focus:
            parts.append(
                "\nSTASIUN YANG SEDANG DIBUKA USER DI PANEL: "
                f"{focus.name}. Anggap pertanyaan tanpa penyebutan nama merujuk "
                "ke stasiun ini."
            )

    return "\n".join(parts)
