# StaSIUN — Overview

## Purpose

WebGIS berbasis Spatial Decision Intelligence yang memperlakukan ruang komersial stasiun kereta
api sebagai portofolio aset yang dapat diukur dan diaudit — menjawab bukan cuma "di mana asetnya",
tapi "berapa nilainya, siapa penyewa yang tepat, dan bagaimana nilainya dioptimalkan".

Masalah yang ditarget: pendapatan non-farebox KAI tertahan di kisaran **4% dari total pendapatan**,
sementara operator lain seperti MRT Jakarta dengan volume penumpang jauh lebih kecil mencapai
**30–40%**. Selisih itu bukan karena asetnya lemah, melainkan karena nilainya tidak pernah diukur
secara spasial. Di sisi lain, UMKM yang ingin masuk ke ruang komersial stasiun menanggung risiko
yang tidak terukur: tidak tahu besar permintaan laten, tingkat kejenuhan kompetisi, atau apakah
lokasi yang ditawarkan benar-benar terlihat pengunjung.

Unit analisis: **stasiun KRL di DKI Jakarta**. Arsitekturnya dirancang input-agnostic sehingga
dapat diperluas ke Jabodetabek dan kawasan TOD lain tanpa merombak struktur utama.

## Data yang Dipakai

**Dataset utama dari panitia:**

| Sumber | Isi | Fungsi |
|---|---|---|
| **Activity Community Maps** (MAPID APPS) | Entri survey lapangan berupa narasi + foto + koordinat, termasuk yang dikumpulkan tim lain | **Dataset utama, dua fungsi sekaligus.** Sebagai korpus naratif: input seluruh pipeline NLP. Sebagai basis pemetaan objek: sumber daftar tenant existing, karakteristik koridor dan spot iklan, kondisi fasilitas, titik konektivitas antarmoda |
| **MAPID MAPS** (GEO MAPID) | Basemap | Basemap utama seluruh tampilan peta |
| **Isochrone Tools** (GEO MAPID) | Poligon jangkauan berjalan kaki | Dasar seluruh analisis jangkauan kawasan; hasilnya disimpan ke PostGIS |

**Data pendukung di luar ekosistem MAPID** (diperbolehkan sepanjang dapat dipertanggungjawabkan;
setiap sumber dicatat asal dan tanggal aksesnya):

| Sumber | Fungsi |
|---|---|
| OpenStreetMap | Jaringan pejalan kaki, titik minat sebagai komponen supply dan indikator kepadatan |
| Volume penumpang stasiun | Dasar estimasi paparan dan indikator transportasi |
| Data profil kawasan | Karakterisasi zona: perkantoran, hunian, atau campuran |
| Riset harga menu sumber terbuka | Estimasi rentang harga per klaster tenant. Kanal pesan-antar dihindari karena memuat harga setelah markup |
| Riset listing properti komersial | Benchmark median harga sewa untuk variabel harga relatif pada TSI |
| Laporan industri iklan luar ruang | Benchmark tarif per seribu paparan untuk validasi harga wajar ruang iklan |

**Kedudukan Dataset Mission.** MenuGo, StrukGo, dan PropertiGo bersifat **opsional** dan
cakupannya di wilayah studi belum memadai. Produk **tidak menggantungkan variabel manapun** pada
ketersediaannya; ketiganya diposisikan sebagai jalur pengayaan tahap lanjutan yang bisa masuk
tanpa mengubah struktur perhitungan.

## Cara Kerjanya

**Analisis spasial** memakai isochrone berbasis jaringan jalan, bukan buffer lingkaran, sehingga
jangkauan kawasan mencerminkan hambatan fisik kota — pejalan kaki tidak bisa menembus rel, sungai,
dan jalan arteri. Dari poligon itu diturunkan **Permeability Index**, rasio luas isochrone
terhadap luas lingkaran setara.

**AI berperan sebagai penerjemah konteks**, bukan alat prediksi, lewat **arsitektur dua lapis
ekstraksi**. Lapis pertama universal dan berjalan pada seluruh entri Activity apa pun bentuknya,
hanya bermodal teks naratif: Topic Modeling untuk arketipe stasiun, NER untuk kelekatan merek,
Sentiment Analysis untuk polaritas keluhan. Lapis kedua opsional, hanya berjalan pada entri yang
memuat penilaian narasumber. Perancangan ini disengaja agar sistem berfungsi pada seluruh data di
ekosistem MAPID, bukan hanya pada data yang mengikuti format survey tim sendiri. Kontribusi model
berbasis teks dibatasi maksimal **15%** terhadap skor akhir dan wajib melalui validasi silang spasial.

**Skor komposit SEPI** (Spatial Economic Potential Index) meringkas lima variabel — Transport,
Ekonomi, Aksesibilitas, Urban, Komersial — lewat pembobotan Entropy + AHP (CR < 0,10), lalu
diranking dengan TOPSIS.

**Ketidakpastian ditangani secara eksplisit.** Karena jumlah sampel bervariasi antar zona,
confidence interval dihitung dengan bootstrap BCa dan estimasi tiap zona memakai shrinkage
estimator terhadap kelompok pembanding berarketipe serupa. Setiap skor membawa jumlah sampel,
interval keyakinan, dan penanda confidence, sehingga zona berdata terbatas tetap dapat ditampilkan
tanpa menyesatkan.

## Output

| Fitur | Keluaran |
|---|---|
| **Ad-Space Opportunity** | Skor potensi dan profil paparan per zona, kategori iklan yang direkomendasikan beserta alasannya, estimasi harga wajar. Termasuk **Facility Sponsorship**: keluhan fasilitas yang lolos validasi spasial diubah jadi peluang kemitraan CSR |
| **Tenant Valuation** | Peringkat kategori usaha untuk lapak kosong beserta GapScore, dan Tenant Survival Index 0–100 beserta komponen penyusunnya |
| **Naming Rights** | Estimasi nilai kontrak tahunan beserta transaksi pembanding yang diacu, dan kandidat sponsor terurut hasil NER |

Semuanya disajikan sebagai peta interaktif (heatmap SEPI, poligon isochrone, poligon zona indoor)
dengan **panel AI Insight** untuk tanya jawab bebas dan simulasi skenario — misalnya mengubah
asumsi harga sewa dan melihat dampaknya ke TSI tanpa pindah halaman. Ringkasan per stasiun dapat
diunduh.

Target performa: muat peta di bawah 3 detik, kueri spasial di bawah 500 ms, biaya infrastruktur
mendekati nol lewat free tier (Vercel, Supabase, MapLibre, OSM).

## Yang Di Luar Lingkup

- Pengolahan data identitas atau data pribadi penumpang. Selain terbatas oleh UU No. 27 Tahun 2022,
  ini juga bukan praktik standar pengukuran audiens iklan luar ruang. Produk sepenuhnya memakai
  indikator agregat dan variabel proxy.
- Indoor mapping dan routing di dalam gedung. Pemetaan indoor terbatas pada penandaan zona dan
  keberadaan tenant, bukan pencarian rute.
- Integrasi sensor real-time seperti penghitung arus footfall otomatis.
- Transaksi, pemesanan, atau kontrak sewa di dalam platform. Produk berhenti di tahap rekomendasi
  dan valuasi.
- Integrasi langsung dengan sistem internal operator yang butuh akses khusus pihak ketiga.

## Status Pengerjaan

Yang sudah berjalan hari ini: PostGIS dengan satu tabel titik stasiun, dua jalur pengisian data
(GeoJSON OSM lokal dan Geoserver MAPID), tiga endpoint API, peta MapLibre di atas basemap MAPID
dengan pencarian dan filter lin, serta asisten chat berbasis LLM.

Yang belum: seluruh lapisan analitik — Activity, isochrone, zona indoor, mesin skor, dan tiga
fitur utamanya.

Rincian per berkas, daftar yang harus diperbaiki, dan blocker data ada di **`ADJUSTMENT.md`**.
Daftar build task per lapisan ada di **`LAYER.md`**.
