"""Menghasilkan tiga lembar wireframe StaSIUN sebagai SVG.

Jalankan dari mana saja; hasilnya ditulis di sebelah berkas ini.

    python docs/wireframe/make_wireframe.py
"""

from html import escape
from pathlib import Path

INK = "#1f2328"
MID = "#6b7280"
SOFT = "#9aa0a6"
LINE = "#c9ced6"
PALE = "#f1f2f4"
FILL = "#e4e7ec"
ACC = "#ec3013"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
DASH = "5 4"

out: list[str] = []


# --------------------------------------------------------------- perkakas
def add(s: str) -> None:
    out.append(s)


def rect(x, y, w, h, fill="none", stroke=None, sw=1, dash=None, op=None):
    a = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"'
    if stroke:
        a += f' stroke="{stroke}" stroke-width="{sw}"'
    if dash:
        a += f' stroke-dasharray="{dash}"'
    if op is not None:
        a += f' opacity="{op}"'
    add(a + "/>")


def txt(x, y, s, size=11, fill=INK, weight="400", anchor="start", ls=None):
    a = (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"'
    )
    if ls:
        a += f' letter-spacing="{ls}"'
    add(a + f">{escape(s)}</text>")


def line(x1, y1, x2, y2, stroke=LINE, sw=1, dash=None):
    a = (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{stroke}" stroke-width="{sw}"'
    )
    if dash:
        a += f' stroke-dasharray="{dash}"'
    add(a + "/>")


def bar(x, y, w, h=6, fill=FILL):
    """Batang abu-abu sebagai pengganti teks."""
    rect(x, y, w, h, fill=fill)


def badge(x, y, n, tick=None):
    """Bulatan bernomor, dengan garis penunjuk pendek bila perlu."""
    if tick:
        line(tick[0], tick[1], tick[2], tick[3], stroke=ACC, sw=1.4)
    add(f'<circle cx="{x}" cy="{y}" r="10" fill="{ACC}"/>')
    add(
        f'<text x="{x}" y="{y + 3.5}" font-family="{FONT}" font-size="11" '
        f'fill="#ffffff" font-weight="700" text-anchor="middle">{n}</text>'
    )


def caps(x, y, s, size=8, fill=SOFT):
    txt(x, y, s.upper(), size=size, fill=fill, weight="600", ls="1")


def wrap(body: str, px: float, size=9) -> list[str]:
    """Pecah kalimat jadi baris yang muat di lebar px."""
    per_char = size * 0.52
    limit = max(12, int(px / per_char))
    lines, cur = [], ""
    for word in body.split():
        if len(cur) + len(word) + 1 > limit:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    lines.append(cur)
    return lines


# ------------------------------------------------------------ bagian umum
def sheet_header(W, tag, title, subtitle):
    txt(48, 58, title, size=26, weight="700")
    txt(48, 84, subtitle, size=12.5, fill=MID)

    lx = W - 48 - 236
    rect(lx, 40, 20, 13, fill="#ffffff", stroke=INK, sw=1.4)
    txt(lx + 28, 51, "Sudah dibangun & berjalan", size=11, fill=INK)
    rect(lx, 62, 20, 13, fill="#ffffff", stroke=SOFT, sw=1.4, dash=DASH)
    txt(lx + 28, 73, "Belum dibangun (rencana)", size=11, fill=MID)

    line(48, 110, W - 48, 110, stroke=INK, sw=1.2)
    caps(48, 138, tag)


def sheet_footer(W, H, note):
    line(48, H - 44, W - 48, H - 44, stroke=LINE)
    txt(48, H - 26, note, size=9.5, fill=SOFT)
    txt(
        W - 48,
        H - 26,
        "StaSIUN · MAPID WebGIS Competition 2026",
        size=9.5,
        fill=SOFT,
        anchor="end",
    )


def notes_column(x, y, w, items, gap=64):
    """Daftar keterangan bernomor, disusun ke bawah."""
    caps(x, y, "Keterangan", size=9, fill=INK)
    line(x, y + 8, x + w, y + 8, stroke=INK, sw=1.2)
    cy = y + 34
    for n, title, body in items:
        # n = 0 dipakai untuk catatan pendukung yang tidak ditunjuk di gambar.
        if n:
            badge(x + 10, cy, n)
        else:
            rect(x + 6, cy - 4, 8, 8, fill=SOFT)
        txt(x + 28, cy - 2, title, size=10.5, weight="700", fill=INK)
        for k, ln in enumerate(wrap(body, w - 28)):
            txt(x + 28, cy + 13 + k * 12, ln, size=9, fill=MID)
        cy += gap + 12 * max(0, len(wrap(body, w - 28)) - 2)
    return cy


def planned_block(x, y, w, h):
    caps(x, y - 10, "Modul yang belum dibangun")
    rect(x, y, w, h, fill="#fbfbfc", stroke=SOFT, sw=1.4, dash=DASH)
    items = [
        ("Ad-Space Opportunity", "belum ada pembanding harga sewa"),
        ("Naming Rights", "belum ada data merek + nilai kontrak"),
        ("Footfall & dwell-time", "menunggu data operasional KAI"),
        ("Arketipe stasiun (LDA)", "menunggu korpus Activity terisi"),
        ("Ekspor laporan", "unduhan PDF ringkasan stasiun"),
        ("Sentimen & NER", "menunggu korpus ulasan penumpang"),
    ]
    colw = (w - 28) / 3
    for i, (a, b) in enumerate(items):
        col, row = i % 3, i // 3
        ix = x + 14 + col * colw
        iy = y + 30 + row * 46
        rect(ix, iy - 8, 5, 5, fill=SOFT)
        txt(ix + 14, iy - 3, a, size=9.5, weight="700", fill=MID)
        txt(ix + 14, iy + 10, b, size=8, fill=SOFT)


# ----------------------------------------------------------- kerangka isi
TABS = ["Ikhtisar", "Ad-Space", "Tenant", "Naming"]


def draw_station_panel_inline(SPX, MPY, SPW, MPH):
    """Panel stasiun versi kecil, dipakai di dalam kerangka layar utama."""
    rect(SPX, MPY, SPW, MPH, fill="#ffffff")
    caps(SPX + 14, MPY + 24, "Stasiun", fill=ACC)
    bar(SPX + 14, MPY + 32, 150, 13, fill="#d7dade")
    rect(SPX + SPW - 32, MPY + 14, 18, 18, fill="#ffffff", stroke=LINE)
    txt(SPX + SPW - 23, MPY + 27, "×", size=11, anchor="middle", fill=MID)
    for ox, w in [(0, 64), (68, 72), (144, 58)]:
        rect(SPX + 14 + ox, MPY + 54, w, 13, fill="#5a616b")
    rect(SPX + 14, MPY + 72, 62, 13, fill="#ffffff", stroke=INK)
    line(SPX, MPY + 96, SPX + SPW, MPY + 96, stroke=LINE)

    tw = SPW / 4
    for i, t in enumerate(TABS):
        txt(
            SPX + tw * i + tw / 2, MPY + 114, t, size=8, anchor="middle",
            fill=ACC if i == 0 else SOFT, weight="600",
        )
    rect(SPX, MPY + 120, tw, 2, fill=ACC)
    line(SPX, MPY + 122, SPX + SPW, MPY + 122, stroke=LINE)

    s = MPY + 122
    rect(SPX + 12, s + 12, SPW - 24, 62, fill="#ffffff", stroke=INK)
    caps(SPX + 22, s + 30, "Indeks SEPI")
    txt(SPX + 22, s + 46, "peringkat #2 dari 46", size=7.5, fill=MID)
    txt(SPX + SPW - 22, s + 60, "63,7/100", size=17, anchor="end", fill=ACC, weight="700")

    rect(SPX + 12, s + 84, SPW - 24, 102, fill="#ffffff", stroke=INK)
    caps(SPX + 22, s + 102, "Komponen SEPI")
    # Panjang bar dan angka di bawah ini contoh nyata dari stasiun Sawah Besar.
    shares = [0.11, 0.80, 0.15, 0.75, 1.00]
    values = ["11%", "80", "1,46", "75", "100"]
    for i in range(5):
        yy = s + 112 + i * 15
        txt(SPX + 22, yy + 7, "TEAUC"[i], size=8, weight="700", fill=MID)
        rect(SPX + 34, yy + 2, SPW - 74, 5, fill=FILL)
        rect(SPX + 34, yy + 2, (SPW - 74) * shares[i], 5, fill=ACC)
        txt(SPX + SPW - 20, yy + 7, values[i], size=7, anchor="end", fill=MID)

    rect(SPX + 12, s + 204, SPW - 24, 108, fill="#ffffff", stroke=INK)
    caps(SPX + 22, s + 222, "Profil stasiun")
    for i in range(5):
        yy = s + 232 + i * 17
        bar(SPX + 22, yy, 66, 6)
        bar(SPX + SPW - 22 - 74, yy, 74, 6, fill="#d7dade")

    rect(SPX + 12, s + 318, SPW - 24, 64, fill="#ffffff", stroke=SOFT, dash=DASH)
    caps(SPX + 22, s + 336, "Menunggu data")
    for i in range(3):
        yy = s + 344 + i * 13
        bar(SPX + 22, yy, 78, 5, fill="#eceef1")
        txt(SPX + SPW - 22, yy + 5, "—", size=8, anchor="end", fill=SOFT)


def draw_main_frame(AX, AY, AW, AH):
    rect(AX, AY, AW, AH, fill="#ffffff", stroke=INK, sw=1.4)

    # bilah aplikasi
    rect(AX, AY, AW, 34, fill=PALE)
    line(AX, AY + 34, AX + AW, AY + 34, stroke=INK)
    rect(AX + 12, AY + 9, 16, 16, fill=INK)
    txt(AX + 36, AY + 22, "StaSIUN", size=13, weight="700")
    line(AX + 92, AY + 10, AX + 92, AY + 24, stroke=LINE)
    bar(AX + 102, AY + 14, 200, 6)
    bar(AX + 600, AY + 14, 108, 6)
    rect(AX + 726, AY + 8, 96, 18, fill="#ffffff", stroke=SOFT, dash=DASH)
    txt(AX + 774, AY + 21, "Ekspor Laporan", size=8, fill=MID, anchor="middle")
    bar(AX + 838, AY + 14, 62, 6)

    MPX, MPY = AX, AY + 34
    MPW, MPH = 668, AH - 34
    rect(MPX, MPY, MPW, MPH, fill=PALE)
    for i in range(1, 7):
        line(MPX, MPY + i * 76, MPX + MPW, MPY + i * 76, stroke="#e2e5ea")
    for i in range(1, 9):
        line(MPX + i * 74, MPY, MPX + i * 74, MPY + MPH, stroke="#e2e5ea")
    line(MPX + MPW, MPY, MPX + MPW, MPY + MPH, stroke=INK)

    dots = [
        (250, 90), (300, 132), (352, 118), (398, 176), (330, 214), (268, 258),
        (420, 250), (486, 208), (520, 296), (356, 320), (300, 372), (250, 430),
        (430, 402), (500, 452), (196, 190), (150, 300), (566, 140), (600, 380),
    ]
    for dx, dy in dots:
        add(
            f'<circle cx="{MPX + dx}" cy="{MPY + dy}" r="5" fill="#5a616b" '
            f'stroke="#ffffff" stroke-width="1.6"/>'
        )
    for dx, dy in [(352, 118), (356, 320), (486, 208)]:
        add(
            f'<path d="M{MPX + dx} {MPY + dy - 5} A5 5 0 0 1 '
            f'{MPX + dx} {MPY + dy + 5} Z" fill="#22262b"/>'
        )
    sx, sy = MPX + 398, MPY + 176
    add(f'<circle cx="{sx}" cy="{sy}" r="15" fill="none" stroke="{ACC}" stroke-width="2"/>')
    add(f'<circle cx="{sx}" cy="{sy}" r="5" fill="{ACC}" stroke="#ffffff" stroke-width="1.6"/>')

    # panel kontrol mengambang
    CPX, CPY, CPW, CPH = MPX + 14, MPY + 14, 176, 312
    rect(CPX + 4, CPY + 4, CPW, CPH, fill="#000000", op=0.05)
    rect(CPX, CPY, CPW, CPH, fill="#ffffff", stroke=INK, sw=1.3)

    caps(CPX + 10, CPY + 20, "Cari stasiun")
    rect(CPX + 10, CPY + 28, CPW - 20, 20, fill="#ffffff", stroke=LINE)
    bar(CPX + 16, CPY + 35, 70, 6)
    line(CPX, CPY + 60, CPX + CPW, CPY + 60, stroke=LINE)

    caps(CPX + 10, CPY + 78, "Filter lin")
    for i, c in enumerate(["B", "C", "R", "T", "TP", "A"]):
        col, row = i % 2, i // 2
        bx, by = CPX + 10 + col * 80, CPY + 86 + row * 22
        rect(bx, by, 74, 17, fill="#ffffff", stroke=SOFT)
        rect(bx + 5, by + 6, 6, 6, fill="#5a616b")
        txt(bx + 16, by + 12, c + " · Lin", size=7.5, fill=INK)
    line(CPX, CPY + 158, CPX + CPW, CPY + 158, stroke=LINE)

    caps(CPX + 10, CPY + 176, "Layer")
    # Ketiga saklar sudah berfungsi: label stasiun, skor SEPI, dan isochrone.
    # Yang isochrone baru bisa dinyalakan setelah ada stasiun terpilih.
    for dy, width in ((183, 94), (200, 108), (217, 116)):
        rect(CPX + 10, CPY + dy, 9, 9, fill="#ffffff", stroke=INK)
        bar(CPX + 25, CPY + dy + 3, width, 5)
    line(CPX, CPY + 236, CPX + CPW, CPY + 236, stroke=LINE)

    caps(CPX + 10, CPY + 254, "Legenda")
    for i, (col, half, wd) in enumerate(
        [("#5a616b", False, 96), ("#5a616b", True, 110), ("#b9bec6", False, 104)]
    ):
        yy = CPY + 264 + i * 15
        add(
            f'<circle cx="{CPX + 16}" cy="{yy + 3}" r="4.5" fill="{col}" '
            f'stroke="#ffffff" stroke-width="1.2"/>'
        )
        if half:
            add(
                f'<path d="M{CPX + 16} {yy - 1.5} A4.5 4.5 0 0 1 '
                f'{CPX + 16} {yy + 7.5} Z" fill="#22262b"/>'
            )
        bar(CPX + 28, yy, wd, 5, fill="#dfe2e6")

    # kontrol zoom + kredit peta
    ZX, ZY = MPX + 14, MPY + MPH - 92
    rect(ZX, ZY, 22, 66, fill="#ffffff", stroke=INK)
    line(ZX, ZY + 22, ZX + 22, ZY + 22, stroke=LINE)
    line(ZX, ZY + 44, ZX + 22, ZY + 44, stroke=LINE)
    txt(ZX + 11, ZY + 15, "+", size=11, anchor="middle", fill=INK)
    txt(ZX + 11, ZY + 37, "–", size=11, anchor="middle", fill=INK)
    txt(ZX + 11, ZY + 59, "N", size=9, anchor="middle", fill=INK)
    rect(ZX + 30, ZY + 44, 22, 22, fill="#ffffff", stroke=INK)
    txt(ZX + 41, ZY + 59, "i", size=10, anchor="middle", weight="700", fill=INK)

    # tombol asisten mengambang
    FBX, FBY = MPX + MPW - 46, MPY + MPH - 46
    rect(FBX + 3, FBY + 3, 32, 32, fill="#000000", op=0.06)
    rect(FBX, FBY, 32, 32, fill=INK)
    add(
        f'<path d="M{FBX + 8} {FBY + 10} h16 v10 h-10 l-6 5 z" fill="none" '
        f'stroke="#ffffff" stroke-width="1.6" stroke-linejoin="round"/>'
    )

    draw_station_panel_inline(MPX + MPW, MPY, AW - MPW, MPH)

    SPX = MPX + MPW
    badge(AX + 520, AY + 17, 1)
    badge(CPX + CPW + 16, CPY + 14, 2, tick=(CPX + CPW + 2, CPY + 14, CPX + CPW + 7, CPY + 14))
    badge(MPX + 470, MPY + 58, 3)
    badge(ZX + 66, ZY + 56, 4, tick=(ZX + 54, ZY + 56, ZX + 58, ZY + 56))
    badge(FBX - 16, FBY + 16, 5, tick=(FBX - 6, FBY + 16, FBX - 2, FBY + 16))
    badge(SPX - 18, MPY + 24, 6, tick=(SPX - 8, MPY + 24, SPX - 2, MPY + 24))


def draw_station_frame(BX, BY, BW, BH):
    rect(BX, BY, BW, BH, fill="#ffffff", stroke=INK, sw=1.4)

    caps(BX + 16, BY + 28, "Stasiun", fill=ACC)
    txt(BX + 16, BY + 52, "Nama Stasiun", size=17, weight="700")
    rect(BX + BW - 36, BY + 16, 20, 20, fill="#ffffff", stroke=LINE)
    txt(BX + BW - 26, BY + 31, "×", size=12, anchor="middle", fill=MID)
    for ox, w in [(0, 66), (70, 74), (148, 60)]:
        rect(BX + 16 + ox, BY + 62, w, 15, fill="#5a616b")
        txt(BX + 16 + ox + w / 2, BY + 73, "Lin", size=7.5, anchor="middle", fill="#ffffff")
    rect(BX + 16, BY + 82, 68, 15, fill="#ffffff", stroke=INK)
    txt(BX + 50, BY + 93, "Interchange", size=7.5, anchor="middle", fill=INK)
    line(BX, BY + 110, BX + BW, BY + 110, stroke=LINE)

    tw = BW / 4
    for i, t in enumerate(TABS):
        txt(
            BX + tw * i + tw / 2, BY + 130, t, size=8.5, anchor="middle",
            fill=ACC if i == 0 else SOFT, weight="600",
        )
    rect(BX, BY + 136, tw, 2, fill=ACC)
    line(BX, BY + 138, BX + BW, BY + 138, stroke=LINE)
    badge(BX - 18, BY + 128, 7, tick=(BX - 8, BY + 128, BX - 2, BY + 128))

    s = BY + 138
    rect(BX + 14, s + 14, BW - 28, 64, fill="#ffffff", stroke=INK)
    caps(BX + 24, s + 32, "Indeks SEPI")
    rect(BX + BW - 108, s + 22, 80, 13, fill="#ffffff", stroke=INK)
    txt(BX + BW - 68, s + 31, "pita 10 menit", size=6.5, anchor="middle", fill=MID)
    txt(BX + 24, s + 50, "Peringkat #2 dari 46 stasiun KRL", size=7.5, fill=MID)
    txt(BX + 24, s + 62, "TOPSIS di atas bobot Entropy + AHP", size=7, fill=SOFT)
    txt(BX + BW - 26, s + 66, "63,7/100", size=20, anchor="end", fill=ACC, weight="700")
    badge(BX - 18, s + 30, 8, tick=(BX - 8, s + 30, BX - 2, s + 30))

    rect(BX + 14, s + 90, BW - 28, 112, fill="#ffffff", stroke=INK)
    caps(BX + 24, s + 108, "Komponen SEPI · 5 variabel")
    # Angka contoh dari stasiun Sawah Besar, pita 10 menit. Satuannya sengaja
    # ditulis karena tiap variabel beda: T skala 0-1, A luas, sisanya jumlah.
    shares = [0.11, 0.80, 0.15, 0.75, 1.00]
    values = ["11%", "80 titik", "1,46 km²", "75 titik", "100 titik"]
    for i, lb in enumerate(
        ["Transportasi", "Ekonomi", "Aksesibilitas", "Urban", "Komersial"]
    ):
        yy = s + 118 + i * 16
        txt(BX + 24, yy + 8, "TEAUC"[i], size=8.5, weight="700", fill=MID)
        txt(BX + 38, yy + 8, lb, size=7.5, fill=MID)
        rect(BX + 38, yy + 11, BW - 96, 5, fill=FILL)
        rect(BX + 38, yy + 11, (BW - 96) * shares[i], 5, fill=ACC)
        txt(BX + BW - 26, yy + 8, values[i], size=7, anchor="end", fill=MID)

    rect(BX + 14, s + 214, BW - 28, 116, fill="#ffffff", stroke=INK)
    caps(BX + 24, s + 232, "Profil stasiun")
    for i, r in enumerate(
        ["Kode KAI", "Lin dilayani", "Status", "Kecamatan", "Alamat", "Koordinat"]
    ):
        yy = s + 242 + i * 15
        txt(BX + 24, yy + 7, r, size=7.5, fill=MID)
        bar(BX + BW - 24 - 76, yy + 2, 76, 6, fill="#cfd3d9")

    rect(BX + 14, s + 342, BW - 28, 64, fill="#ffffff", stroke=SOFT, dash=DASH)
    caps(BX + 24, s + 360, "Menunggu data")
    for i, r in enumerate(
        ["Footfall / hari kerja", "Median dwell-time", "Arketipe (LDA)"]
    ):
        yy = s + 368 + i * 13
        txt(BX + 24, yy + 6, r, size=7.5, fill=SOFT)
        txt(BX + BW - 24, yy + 6, "—", size=8, anchor="end", fill=SOFT)


def draw_assistant_frame(CX, CY, CW, CH):
    rect(CX, CY, CW, CH, fill="#ffffff", stroke=INK, sw=1.4)
    rect(CX, CY, CW, 26, fill=PALE)
    line(CX, CY + 26, CX + CW, CY + 26, stroke=LINE)
    caps(CX + 12, CY + 17, "Asisten StaSIUN", fill=INK)
    rect(CX + CW - 30, CY + 6, 16, 14, fill="#ffffff", stroke=LINE)
    txt(CX + CW - 22, CY + 17, "×", size=10, anchor="middle", fill=MID)

    rect(CX + CW - 150, CY + 40, 136, 28, fill="#f1f2f4", stroke=LINE)
    bar(CX + CW - 142, CY + 48, 118, 5, fill="#d0d4da")
    bar(CX + CW - 142, CY + 58, 78, 5, fill="#d0d4da")

    rect(CX + 14, CY + 80, 2, 72, fill=ACC)
    caps(CX + 24, CY + 88, "Asisten")
    for i, w in enumerate([196, 186, 172, 198, 128]):
        bar(CX + 24, CY + 96 + i * 11, w, 5, fill="#d7dade")
    badge(CX + 236, CY + 118, 9)

    rect(CX + CW - 130, CY + 164, 116, 24, fill="#f1f2f4", stroke=LINE)
    bar(CX + CW - 122, CY + 172, 98, 5, fill="#d0d4da")

    rect(CX + 14, CY + 200, 2, 46, fill=ACC)
    caps(CX + 24, CY + 208, "Asisten")
    for i, w in enumerate([200, 184, 148]):
        bar(CX + 24, CY + 216 + i * 11, w, 5, fill="#d7dade")

    line(CX, CY + CH - 62, CX + CW, CY + CH - 62, stroke=LINE)
    caps(CX + 12, CY + CH - 46, "Konteks")
    txt(CX + 62, CY + CH - 45, "Stasiun Manggarai", size=8, fill=INK)
    rect(CX + CW - 28, CY + CH - 56, 14, 13, fill="#ffffff", stroke=LINE)
    txt(CX + CW - 21, CY + CH - 46, "×", size=8, anchor="middle", fill=MID)
    line(CX, CY + CH - 36, CX + CW, CY + CH - 36, stroke=LINE)
    rect(CX + 12, CY + CH - 28, CW - 74, 20, fill="#ffffff", stroke=LINE)
    bar(CX + 18, CY + CH - 21, 92, 5)
    rect(CX + CW - 56, CY + CH - 28, 44, 20, fill=INK)
    txt(CX + CW - 34, CY + CH - 15, "Kirim", size=8, anchor="middle", fill="#ffffff")


# --------------------------------------------------------------- rendering
def render(W, H, name):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">\n'
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n'
        + "\n".join(out)
        + "\n</svg>\n"
    )
    dest = Path(__file__).resolve().parent / name
    dest.write_text(svg, encoding="utf-8")
    print(f"  {name:34s} {W}x{H}  {len(svg):>6d} byte")
    out.clear()


# ------------------------------------------------------- lembar 1: layar
def sheet_main():
    W, H = 1400, 1000
    sheet_header(
        W,
        "Lembar 1 dari 3",
        "1 · Layar Utama",
        "StaSIUN — peta, panel kontrol, dan panel stasiun  ·  Lampiran PRD",
    )
    draw_main_frame(48, 152, 930, 566)
    notes_column(
        1010, 152, 342,
        [
            (1, "Bilah aplikasi", "Identitas produk, hitungan stasiun aktif, dan tombol ekspor laporan yang belum berfungsi."),
            (2, "Panel kontrol", "Pencarian stasiun dengan saran ketik, filter enam lin KRL, tiga saklar layer — label nama, skor SEPI, dan isochrone stasiun terpilih — serta legenda yang ikut berganti mengikuti saklar mana yang menyala."),
            (3, "Peta", "MapLibre GL dengan basemap MAPID. Titik berwarna mengikuti lin; stasiun interchange digambar sebagai lingkaran multiwarna. Saat layer SEPI menyala, cincin berwarna skor muncul di belakang tiap penanda — penandanya sendiri tetap terlihat, jadi lin dan skor terbaca sekaligus."),
            (4, "Kontrol peta", "Zoom, kompas, dan kredit basemap. Kredit wajib tampil karena lisensi OpenStreetMap."),
            (5, "Tombol asisten", "Mengambang di pojok peta, tidak menempel pada stasiun mana pun. Lihat lembar 3."),
            (6, "Panel stasiun", "Dok kanan selebar 400 px, muncul setelah satu stasiun dipilih. Lihat lembar 2."),
        ],
        gap=70,
    )
    planned_block(48, 768, 930, 128)
    sheet_footer(
        W, H,
        "Wireframe rendah-fidelitas. Proporsi mengikuti tata letak yang sudah berjalan; warna dan tipografi final tidak diwakili.",
    )
    render(W, H, "1-layar-utama.svg")


# ----------------------------------------------- lembar 2: panel stasiun
def sheet_station():
    W, H = 940, 810
    sheet_header(
        W,
        "Lembar 2 dari 3",
        "2 · Panel Stasiun",
        "Dok kanan, tab Ikhtisar  ·  Muncul setelah satu stasiun dipilih",
    )
    draw_station_frame(48, 152, 250, 566)
    notes_column(
        360, 152, 532,
        [
            (7, "Tab modul", "Ikhtisar dan Tenant sudah berisi data asli. Tenant menampilkan Tenant Survival Index lima kategori usaha: perbandingan calon pelanggan yang bisa berjalan kaki ke sini dengan pesaing sejenis yang sudah ada. Ad-Space dan Naming masih kosong, masing-masing dengan keterangan data apa yang kurang."),
            (8, "Blok skor SEPI", "Skor dan peringkatnya berasal dari mesin skoring yang sudah berjalan: TOPSIS di atas bobot gabungan Entropy dan AHP, dihitung di dalam poligon isochrone. Panjang bar dibandingkan dengan komponen tertinggi di stasiun itu sendiri, dan angka mentahnya tetap ditulis di sebelahnya lengkap dengan satuannya."),
            (0, "Bobot AHP", "Perbandingan berpasangannya masih angka sementara dan harus diganti hasil kesepakatan tim. Consistency ratio diperiksa tiap kali dihitung; kalau mencapai 0,10 skoringnya berhenti."),
            (0, "Profil stasiun", "Satu-satunya blok bergaris utuh di panel ini: kode KAI, lin dilayani, status dilayani atau dilintasi, kecamatan, alamat, dan koordinat. Semuanya diambil langsung dari basis data."),
            (0, "Menunggu data", "Footfall, dwell-time, dan arketipe LDA sengaja ditampilkan kosong supaya kebutuhan datanya terbaca sejak awal, bukan disembunyikan."),
        ],
        gap=72,
    )
    sheet_footer(
        W, H,
        "Garis utuh berarti sudah berjalan; garis putus-putus berarti masih rencana.",
    )
    render(W, H, "2-panel-stasiun.svg")


# --------------------------------------------------- lembar 3: asisten AI
def sheet_assistant():
    W, H = 940, 580
    sheet_header(
        W,
        "Lembar 3 dari 3",
        "3 · Asisten AI",
        "Panel mengambang di pojok kanan bawah peta  ·  Tidak terikat pada satu stasiun",
    )
    draw_assistant_frame(48, 152, 260, 336)
    notes_column(
        370, 152, 522,
        [
            (9, "Asisten berbasis data", "Model bahasa dibekali isi basis data: daftar stasiun, skor SEPI ketiga pita waktu, dan hitungan titik minat di dalam tiap isochrone. Nama stasiun yang disebut di pertanyaan dikenali, lalu rincian sekitarnya ikut disertakan — jadi pertanyaan seperti gerai apa yang belum ada bisa dijawab dari angka, bukan dikarang. Konteksnya disusun ulang setiap pertanyaan."),
            (0, "Chip konteks", "Stasiun yang sedang dibuka otomatis menjadi konteks, sehingga pertanyaan seperti “lin apa saja di sini” punya rujukan. Bisa dilepas lewat tanda silang untuk bertanya hal umum."),
            (0, "Pagar kejujuran", "Asisten dilarang mengarang angka. Ditanya hal yang datanya memang belum ada — footfall, arketipe LDA — dia menyatakannya belum ada lalu menjelaskan bagaimana nanti dihitung."),
        ],
        gap=76,
    )
    sheet_footer(
        W, H,
        "Percakapan tersimpan selama sesi; panelnya disembunyikan, bukan dilepas, saat ditutup.",
    )
    render(W, H, "3-asisten-ai.svg")


if __name__ == "__main__":
    print("menulis lembar wireframe:")
    sheet_main()
    sheet_station()
    sheet_assistant()
