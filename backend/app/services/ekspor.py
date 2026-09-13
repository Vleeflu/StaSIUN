"""Ekspor ringkasan analisis per stasiun, disesuaikan persona pembacanya.

PRD mensyaratkan "fitur ekspor ringkasan analisis per stasiun dalam format yang
dapat dibagikan", berisi skor, rekomendasi, dan metadata (hal. 8 dan Tabel 8).

CARA HEMAT TOKEN: MODEL TIDAK MENULIS DOKUMENNYA
------------------------------------------------
Godaannya menyuruh model bahasa menyusun seluruh dokumen. Itu boros - 3.000
sampai 5.000 token per dokumen - dan lebih buruk lagi, ia menempatkan seluruh
ANGKA di tangan model, yang justru hal yang paling tidak boleh dikarang.

Yang dikerjakan di sini:

1. Seluruh struktur, tabel, dan angka disusun templat dari data. NOL token.
2. Model hanya menulis DUA paragraf pembuka yang berbeda per persona - sekitar
   300 token sekali jalan.
3. Hasilnya disimpan per (stasiun x persona), sehingga ekspor kedua untuk
   kombinasi yang sama tidak memanggil model sama sekali.
4. Kalau kuota model habis, dokumennya TETAP jadi - hanya tanpa paragraf
   pembuka. Fitur ekspor tidak boleh mati gara-gara kuota.

PERSONA MENGUBAH PENEKANAN, BUKAN ANGKA
---------------------------------------
Tiap persona mendapat urutan bagian dan panjang yang berbeda, tetapi angka yang
sama. Yang tidak pernah berubah: blok metadata keyakinan. Ekspor untuk regulator
yang menyembunyikan bahwa confidence-nya 0,60 bukan gaya penyampaian - itu
menyesatkan, dan PRD mewajibkan metadata transparansi di setiap skor.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

# Persona sesuai PRD Tabel 1, ditambah dua yang diminta di luar itu.
#
# `fokus` menentukan bagian mana yang didahulukan; `nada` masuk ke prompt
# paragraf pembuka. Keduanya TIDAK menyentuh angkanya.
PERSONA: dict[str, dict] = {
    "pengelola": {
        "label": "Pengelola aset stasiun",
        "aksen": "#14532d",
        "judul_font": "Georgia, 'Times New Roman', serif",
        "sifat": "dokumen negosiasi: angka rapat, tabel padat, nada resmi",
        "fokus": ["skor", "paparan", "iklan", "sponsorship", "tenant"],
        "nada": (
            "pengelola aset komersial stasiun yang perlu justifikasi terukur "
            "untuk menetapkan tarif sewa dan memilih mitra"
        ),
    },
    "pengiklan": {
        "label": "Pengiklan dan pemilik merek",
        "aksen": "#b91c1c",
        "judul_font": "system-ui, -apple-system, 'Segoe UI', sans-serif",
        "sifat": "materi penawaran: angka besar, kontras tinggi",
        "fokus": ["paparan", "iklan", "skor", "tenant", "sponsorship"],
        "nada": (
            "pengiklan yang menimbang membeli ruang iklan dan perlu tahu siapa "
            "yang melintas serta format apa yang efektif"
        ),
    },
    "umkm": {
        "label": "Pelaku UMKM dan calon tenant",
        "aksen": "#9a3412",
        "judul_font": "system-ui, -apple-system, 'Segoe UI', sans-serif",
        "sifat": "dibaca orang yang bukan analis: huruf lebih besar, jarak lebih lega",
        "fokus": ["tenant", "skor", "paparan", "iklan", "sponsorship"],
        "nada": (
            "pelaku UMKM yang menimbang menyewa lapak dan perlu tahu risiko "
            "serta kelapangan pasarnya sebelum menandatangani sewa"
        ),
    },
    "regulator": {
        "label": "Perencana kawasan dan regulator",
        "aksen": "#1e3a5f",
        "judul_font": "Georgia, 'Times New Roman', serif",
        "sifat": "dokumen kebijakan: serif, catatan metodologi menonjol",
        "fokus": ["skor", "tenant", "paparan", "sponsorship", "iklan"],
        "nada": (
            "perencana kawasan yang menilai metodologi dan keterbatasan data "
            "sebelum memakainya sebagai dasar kebijakan"
        ),
    },
    "investor": {
        "label": "Investor dan mitra",
        "aksen": "#312e81",
        "judul_font": "Georgia, 'Times New Roman', serif",
        "sifat": "materi due diligence: angka menonjol, keterbatasan disebut terang",
        "fokus": ["skor", "paparan", "tenant", "sponsorship", "iklan"],
        "nada": (
            "calon mitra atau investor yang menilai besaran peluang dan "
            "dasar buktinya"
        ),
    },
}


@dataclass
class Bagian:
    judul: str
    isi: str


def _e(teks: object) -> str:
    """Amankan teks apa pun sebelum masuk HTML."""
    return html.escape(str(teks if teks is not None else "-"))


def _tabel(baris: list[tuple[str, object]]) -> str:
    sel = "".join(
        f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in baris if v is not None
    )
    return f"<table>{sel}</table>" if sel else ""


def susun_bagian(data: dict) -> dict[str, Bagian]:
    """Ubah data mentah tiap fitur jadi bagian dokumen. Tanpa model bahasa."""
    skor = data.get("skor") or {}
    paparan = data.get("paparan") or {}
    tenant = data.get("tenant") or {}
    naming = data.get("naming") or {}
    areas = data.get("areas") or {}
    sponsor = data.get("sponsorship") or {}

    bagian: dict[str, Bagian] = {}

    if skor:
        terukur = skor.get("terukur") or {}
        belum = [k for k, v in terukur.items() if v is False]
        bagian["skor"] = Bagian(
            "Potensi ekonomi kawasan",
            _tabel(
                [
                    ("Skor SEPI", f"{skor.get('sepi')} dari 100"),
                    ("Kelas", skor.get("kelas")),
                    (
                        "Peringkat",
                        f"#{skor.get('rank')} dari {skor.get('rank_total')} stasiun KRL"
                        f" (lebih tinggi daripada {skor.get('persentil')}% stasiun)"),
                    ("Keputusan", skor.get("keputusan")),
                    (
                        "Keyakinan data",
                        f"{skor.get('confidence')}, {skor.get('variabel_terpakai')} "
                        f"dari {skor.get('variabel_total')} variabel terukur langsung"
                        + (f", estimasi pada {', '.join(belum)}" if belum else "")),
                ]
            ))

    if paparan.get("cei") is not None:
        bagian["paparan"] = Bagian(
            "Nilai paparan iklan",
            _tabel(
                [
                    ("Composite Exposure Index", f"{paparan.get('cei')} dari 100"),
                    ("Kelas paparan", paparan.get("kelas")),
                    ("Rumus", "0,5 × Transportasi + 0,3 × Ekonomi + 0,2 × Urban"),
                ]
            )
            + "<p class='nota'>Dihitung terpisah dari SEPI. Untuk menilai ruang "
            "iklan, keramaian dan jangkauan transportasi diberi bobot separuh.</p>")

    kategori = tenant.get("categories") or []
    if kategori:
        urut = sorted(kategori, key=lambda c: -c["tsi"])
        baris = "".join(
            f"<tr><td>{_e(c['label'])}</td><td>{_e(round(c['tsi']))}</td>"
            f"<td>{_e(c['supply'])}</td><td>#{_e(c['rank'])}</td></tr>"
            for c in urut
        )
        bagian["tenant"] = Bagian(
            "Kelayakan usaha per sektor",
            "<table><tr><th>Sektor</th><th>Indeks</th><th>Pesaing</th>"
            f"<th>Peringkat</th></tr>{baris}</table>"
            f"<p class='nota'>Basis pelanggan sama untuk semua sektor: "
            f"{_e(urut[0].get('demand'))} titik aktivitas dalam jangkauan. Yang "
            "membedakan adalah jumlah pesaing sejenis.</p>")

    daftar_area = [a for a in (areas.get("areas") or []) if a["iklan"]["per_jenis"]]
    if daftar_area:
        baris = "".join(
            f"<tr><td>{_e(a['nama'])}</td>"
            f"<td>{_e(a['iklan']['total'] or 'tidak dicatat')}</td>"
            f"<td>{_e(a['waktu_singgah'].get('label'))}</td>"
            f"<td>{_e((a.get('format_iklan') or {}).get('bentuk'))}</td></tr>"
            for a in daftar_area
        )
        bagian["iklan"] = Bagian(
            "Inventaris ruang iklan",
            "<table><tr><th>Titik</th><th>Media</th><th>Waktu singgah</th>"
            f"<th>Format yang sesuai</th></tr>{baris}</table>")

    peluang = sponsor.get("peluang") or []
    if peluang:
        baris = "".join(
            f"<tr><td>{_e(p['usulan']['bentuk'])}</td><td>{_e(p['jenis'])}</td>"
            f"<td>{_e(p['usulan']['kewenangan'])}</td></tr>"
            for p in peluang
        )
        bagian["sponsorship"] = Bagian(
            "Peluang sponsorship fasilitas",
            "<table><tr><th>Bentuk kemitraan</th><th>Fasilitas</th>"
            f"<th>Kewenangan</th></tr>{baris}</table>")

    potensi = naming.get("potensi") or {}
    if potensi.get("cei") is not None:
        kandidat = naming.get("kandidat_sponsor") or []
        isi = _tabel(
            [
                ("Nilai paparan", f"{potensi.get('cei')} dari 100"),
                (
                    "Peringkat paparan",
                    f"#{potensi.get('peringkat_paparan')} dari "
                    f"{potensi.get('dari_stasiun_krl')} stasiun KRL"),
                ("Nilai kontrak", "belum tersedia"),
            ]
        )
        if kandidat:
            isi += "<p class='nota'>Calon sponsor terdekat: " + _e(
                ", ".join(f"{k['nama']} ({k['jarak_m']} m)" for k in kandidat[:5])
            ) + "</p>"
        isi += (
            "<p class='nota'>" + _e(naming.get("alasan_nilai_kosong", "")) + "</p>"
        )
        bagian["naming"] = Bagian("Potensi hak penamaan", isi)

    return bagian


# Ukuran huruf dasar per persona. UMKM dibesarkan karena pembacanya bukan
# analis yang terbiasa memindai tabel rapat; investor dan pengelola dirapatkan
# karena keduanya membaca banyak angka sekaligus dan ruang kosong justru
# memperpanjang dokumen tanpa menambah kejelasan.
UKURAN_DASAR = {"umkm": 15, "pengiklan": 14, "regulator": 14}


def gaya(persona: str) -> str:
    """Lembar gaya dokumen, disesuaikan persona pembacanya.

    Yang berubah hanya RUPA, bukan isi maupun urutan angka. Warna aksen, jenis
    huruf judul, dan kerapatan tabel mengikuti kebiasaan baca tiap pembaca:
    dokumen negosiasi aset tidak pantas berwarna semarak, dan lembar penawaran
    untuk pengiklan tidak pantas sekaku dokumen kebijakan.

    Aturan cetaknya dipasang di sini juga, bukan diserahkan ke bawaan browser.
    Tanpa `break-inside`, satu tabel bisa terbelah dua halaman tepat di tengah
    baris, dan tanpa `@page` marginnya mengikuti setelan printer masing-masing
    orang sehingga hasil cetak tiap pembaca berbeda-beda.
    """
    p = PERSONA.get(persona, PERSONA["pengelola"])
    aksen = p.get("aksen", "#1e3a5f")
    judul_font = p.get("judul_font", "system-ui, sans-serif")
    dasar = UKURAN_DASAR.get(persona, 13.5)
    lega = 1.7 if persona == "umkm" else 1.55

    return f"""
:root{{--aksen:{aksen}}}
*{{box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:780px;
margin:0 auto;padding:44px 28px;color:#18181b;line-height:{lega};
font-size:{dasar}px;-webkit-print-color-adjust:exact;print-color-adjust:exact}}

/* Kepala dokumen: satu garis aksen tebal, cukup untuk menandai identitas
   tanpa blok warna penuh yang boros tinta saat dicetak. */
.kepala{{border-top:5px solid var(--aksen);padding-top:14px;margin-bottom:26px}}
h1{{font-family:{judul_font};font-size:30px;margin:0 0 4px;letter-spacing:-.015em;
color:var(--aksen)}}
.kop{{color:#52525b;font-size:{dasar - 1.5}px;margin:0}}
.kop strong{{color:#18181b}}

h2{{font-family:{judul_font};font-size:{dasar + 1}px;text-transform:uppercase;
letter-spacing:.09em;color:var(--aksen);margin:30px 0 10px;
border-bottom:2px solid var(--aksen);padding-bottom:5px;break-after:avoid}}

p{{margin:0 0 11px}}
.pembuka{{font-size:{dasar + 1}px;color:#27272a;border-left:3px solid var(--aksen);
padding-left:14px;margin-bottom:22px}}

table{{width:100%;border-collapse:collapse;font-size:{dasar - 1}px;margin:0 0 10px;
break-inside:avoid}}
th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #e4e4e7;
vertical-align:top}}
th{{color:#3f3f46;font-weight:600;width:38%;background:#fafafa}}
table tr th:only-of-type{{width:auto}}
/* Baris kepala tabel berkolom banyak diberi garis aksen supaya kolomnya
   terbaca sebagai judul, bukan sebagai baris data pertama. */
table tr:first-child th{{border-bottom:2px solid var(--aksen)}}
td:not(:first-child){{font-variant-numeric:tabular-nums}}

.nota{{font-size:{dasar - 2}px;color:#52525b;background:#fafafa;
border-left:3px solid #d4d4d8;padding:8px 11px;margin:0 0 10px}}
.kaki{{margin-top:36px;border-top:1px solid #d4d4d8;padding-top:14px;
font-size:{dasar - 3}px;color:#71717a;break-inside:avoid}}

@page{{margin:18mm 16mm}}
@media print{{
  body{{padding:0;max-width:none;font-size:{dasar - 1}px}}
  h2{{margin-top:22px}}
  a{{color:inherit;text-decoration:none}}
}}
"""


def susun_dokumen(
    stasiun: str, persona: str, data: dict, pembuka: str | None, tanggal: str
) -> str:
    """Rakit dokumen HTML lengkap. Bisa dicetak jadi PDF lewat browser."""
    p = PERSONA.get(persona, PERSONA["pengelola"])
    bagian = susun_bagian(data)

    # Urutan bagian mengikuti persona; yang tidak disebut ikut di belakang,
    # supaya penambahan bagian baru tidak diam-diam hilang dari sebagian
    # dokumen.
    urutan = [k for k in p["fokus"] if k in bagian]
    urutan += [k for k in bagian if k not in urutan]

    isi = "".join(
        f"<h2>{_e(bagian[k].judul)}</h2>{bagian[k].isi}" for k in urutan
    )
    narasi = f'<p class="pembuka">{_e(pembuka)}</p>' if pembuka else ""

    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>StaSIUN, {_e(stasiun)}</title><style>{gaya(persona)}</style></head><body>
<div class="kepala">
<h1>{_e(stasiun)}</h1>
<p class="kop">Ringkasan analisis untuk <strong>{_e(p['label'].lower())}</strong>
· disusun {_e(tanggal)}</p>
</div>
{narasi}
{isi}
<div class="kaki">
Disusun StaSIUN dari data MAPID Activity Community Maps, OpenStreetMap, dan
riset sumber terbuka. Seluruh angka dapat ditelusuri ke sumbernya lewat
antarmuka. Variabel yang belum terukur langsung diisi estimasi shrinkage
terhadap stasiun berkarakter serupa, dan tingkat keyakinannya dicantumkan pada
bagian potensi ekonomi kawasan.
</div></body></html>"""


def prompt_pembuka(stasiun: str, persona: str, data: dict) -> list[dict]:
    """Pesan untuk model - HANYA meminta dua paragraf pembuka.

    Angkanya disisipkan di prompt sebagai fakta yang sudah jadi, dan model
    diminta merangkainya, bukan menghitung apa pun. Batas 160 kata menjaga
    biayanya tetap di kisaran 300 token.
    """
    p = PERSONA.get(persona, PERSONA["pengelola"])
    skor = data.get("skor") or {}
    paparan = data.get("paparan") or {}
    fakta = (
        f"Stasiun {stasiun}. SEPI {skor.get('sepi')} dari 100, kelas "
        f"{skor.get('kelas')}, peringkat {skor.get('rank')} dari "
        f"{skor.get('rank_total')}. Keyakinan data {skor.get('confidence')} "
        f"({skor.get('variabel_terpakai')} dari {skor.get('variabel_total')} "
        f"variabel terukur langsung). Nilai paparan iklan {paparan.get('cei')}."
    )
    return [
        {
            "role": "system",
            "content": (
                "Kamu menulis paragraf pembuka sebuah ringkasan analisis stasiun "
                "untuk " + p["nada"] + ". Tulis MAKSIMAL dua paragraf, total di "
                "bawah 160 kata, dalam bahasa Indonesia yang lugas dan pantas "
                "untuk dokumen resmi. JANGAN menambah angka apa pun di luar yang "
                "diberikan, jangan mengarang temuan, dan sebutkan tingkat "
                "keyakinannya kalau di bawah 1,0. Jangan memakai daftar berpoin."
            ),
        },
        {"role": "user", "content": fakta},
    ]
