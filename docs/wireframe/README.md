# Wireframe antarmuka StaSIUN

Lampiran PRD, dipecah jadi tiga lembar supaya tiap gambar bisa ditaruh di dekat
bagian PRD yang membahasnya.

| Lembar | Isi |
|---|---|
| `1-layar-utama` | Peta, panel kontrol mengambang, panel stasiun, plus daftar modul yang belum dibangun. Keterangan 1–6. |
| `2-panel-stasiun` | Dok kanan pada tab Ikhtisar, lengkap sampai baris terakhir. Keterangan 7–8. |
| `3-asisten-ai` | Panel asisten mengambang beserta chip konteksnya. Keterangan 9. |

Penomoran keterangan berlanjut antar lembar, jadi rujukan silang di PRD tetap
konsisten.

## Format tiap lembar

| Akhiran | Untuk apa |
|---|---|
| `.png` | Dua kali lipat. Pakai untuk dokumen cetak dan slide. |
| `@1x.png` | Ukuran asli. Cukup untuk dokumen layar dan Google Docs. |
| `.svg` | Vektor, tajam di ukuran berapa pun. Word dan Figma bisa membacanya; Google Docs belum. |

## Kalau perlu diubah

Sunting `make_wireframe.py`, lalu jalankan dari mana saja:

```bash
python docs/wireframe/make_wireframe.py
```

Ketiga SVG ditimpa di folder yang sama. Untuk memperbarui PNG-nya, dari folder
`frontend` — paket `sharp` sudah ikut terpasang bersama Next.js:

```bash
node -e "const s=require('sharp'),f=require('fs');for(const [n,w] of [['1-layar-utama',1400],['2-panel-stasiun',940],['3-asisten-ai',940]]){const v=f.readFileSync('../docs/wireframe/'+n+'.svg');s(v,{density:144}).resize({width:w*2}).flatten({background:'#ffffff'}).png().toFile('../docs/wireframe/'+n+'.png');s(v,{density:72}).resize({width:w}).flatten({background:'#ffffff'}).png().toFile('../docs/wireframe/'+n+'@1x.png');}"
```

## Yang perlu diingat

Garis utuh berarti sudah dibangun dan berjalan. Garis putus-putus berarti masih
rencana.

Blok skor SEPI sekarang bergaris utuh: mesin skoringnya sudah jalan, dan angka
yang tergambar — 63,7 dari 100, peringkat #2 — contoh nyata dari stasiun Sawah
Besar pada pita 10 menit, bukan angka karangan. Yang masih sementara justru
bobot AHP-nya; itu ditandai sebagai catatan tersendiri di lembar 2.

Ini wireframe rendah-fidelitas: proporsinya mengikuti tata letak yang sudah
jalan, tetapi warna dan tipografi final sengaja tidak diwakili.
