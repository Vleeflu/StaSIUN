# StaSIUN — What Needs to Be Built

Diturunkan dari **PRD StaSIUN** (MAPID WebGIS Competition 2026), bagian 7 (Metode
Pengolahan Data, AI, dan Analisis Spasial), 8 (Fitur dan Acceptance Criteria), dan
9 (Persyaratan Teknis).

> Versi sebelumnya dokumen ini diturunkan dari **proposal pra-survey** dan sudah tidak
> berlaku. Empat hal yang berubah setelah survey lapangan: Activity jadi dataset utama
> tunggal, OCR keluar dari jalur kritis, isochrone diambil dari GeoMAPID (bukan
> dibangkitkan sendiri dengan pgRouting), dan seluruh mekanisme penanganan
> ketidakpastian jadi wajib. Rekaman perbandingannya ada di `ADJUSTMENT.md`.

---

## 1. Data Layer — PostgreSQL + PostGIS (Supabase)

- Proyeksi ganda: **EPSG:4326** untuk penyimpanan dan rendering, **EPSG:32748** (UTM 48S)
  untuk semua perhitungan dalam meter. Konvensinya dipusatkan di `backend/app/core/geo.py`.
- Indeks **GiST** pada setiap kolom geometri, supaya kueri kedekatan terhadap ratusan ribu
  titik minat tetap cepat.
- **Materialized views** untuk hasil komputasi berat, diperbarui hanya saat data sumber berubah.
- **Tidak memakai pgRouting.** Poligon isochrone datang jadi dari tools GeoMAPID lalu
  disimpan di PostGIS agar bisa diolah berulang tanpa memanggil service eksternal.

Seluruh tabel dasar di bawah **sudah ada di database** per 6 Sep 2026, lewat tiga revisi
Alembic berantai (`d4a7fc2da6ce`, `8e28c27f6231`, `0883f21f1e5d`). Yang belum dibuat tinggal
empat materialized view di bagian bawah tabel, karena isinya menunggu mesin skor.
Rinciannya di `ADJUSTMENT.md` bagian 7.9.

Kolom berdefault memakai `server_default` sisi database, bukan hanya `default` sisi Python,
supaya impor massal lewat `COPY` tidak gagal.

| Tabel | Isi |
|---|---|
| `stations` | Titik stasiun, roster lin, status dilayani |
| `activity_raw` | Payload entri Activity apa adanya + provenance (sumber, adapter, waktu tarik). Staging sebelum gating |
| `activity_points` | Titik Activity lolos gate: narasi, foto, kategori, waktu pengamatan, koordinat |
| `activity_extractions` | Keluaran lapis 1 per titik: arketipe, entitas merek, polaritas sentimen |
| `crowd_ratings` | Skala keramaian 1–5 x tiga rentang waktu x atribusi narasumber (lapis 2) |
| `isochrones` | Poligon 5/10/15 menit per stasiun + `permeability_index` |
| `station_zones` | Poligon zona indoor stasiun |
| `tenants` | Tenant existing: nama, kategori, status operasional, posisi relatif gerbang dan peron |
| `tenant_clusters` | Klaster tenant: kedekatan spasial + kesamaan kategori |
| `ad_spots` | Spot iklan: lokasi, jumlah media terpasang, status terpakai atau kosong |
| `facility_issues` | Keluhan fasilitas + bukti fisik + hasil validasi silang spasial |
| `poi` | Titik minat OSM di sekitar stasiun |
| `passenger_volume` | Volume penumpang per stasiun (data sekunder) |
| `area_profile` | Profil kawasan: perkantoran, hunian, atau campuran |
| `price_references` | Harga menu dan listing sewa, **wajib beserta sumber dan tanggal akses** |
| `mv_sepi_scores` | T, E, A, U, C, SEPI, peringkat TOPSIS |
| `mv_gap_scores` | GapScore per kategori usaha per zona |
| `mv_tsi` | TSI per lapak beserta komponen penyusunnya |
| `mv_naming_rights` | CEI, estimasi nilai kontrak, kandidat sponsor |

Setiap tabel skor wajib membawa kolom metadata: `n_sample`, `ci_low`, `ci_high`,
`confidence`, `estimated_share`. Ini acceptance criteria tersendiri di PRD, bukan tambahan.

## 2. Data Ingestion & Preprocessing

- Penarikan **Activity Community Maps** dari MAPID, termasuk entri yang dikumpulkan tim lain.
  Ini dataset utama, bukan salah satu dari empat sumber setara seperti pada proposal lama.
- **Cakupan penarikan: wilayah yang dipilih, bukan entrinya.** Kurasi manual dilarang — begitu
  entri dipilih satu per satu, yang bekerja adalah penilaian manusia dan klaim universalitas
  gugur. Penyaringan seluruhnya berupa aturan yang dieksekusi kode: gate spasial (di dalam
  isochrone 15 menit stasiun studi; radius 1 km selama isochrone belum ada), gate wilayah
  (bbox DKI, koordinat bukan nol), gate kualitas (ada teks naratif di atas panjang minimum,
  duplikat dibuang), dan gate temporal (entri lawas ditandai, keluhannya divalidasi ke
  pengamatan terkini). Jumlah yang lolos dan gugur di setiap gate dicatat — angka itu yang
  jadi bukti universalitas, bukan klaimnya.
- **Alur ingest:** adapter sumber (berkas lokal, `layer_id` MAPID, atau query bbox bila API-nya
  tersedia) → `activity_raw` menyimpan payload apa adanya beserta provenance → gating dan
  cleaning → `activity_points` → lapis 1. Entri tim sendiri dan entri tim lain melewati jalur
  yang sama persis; tidak boleh ada cabang kode yang membedakannya.
- **Cleaning:** koordinat tidak wajar atau bernilai nol disingkirkan, titik duplikat dihapus,
  penulisan nama dan kategori diseragamkan, satuan harga dinormalisasi.
- **Validasi silang spasial:** setiap temuan berbasis teks diuji terhadap kondisi spasial yang
  dapat diverifikasi. Keluhan soal sulitnya menemukan suatu kategori usaha hanya diterima kalau
  kueri spasial memang menunjukkan kategori itu tidak ada atau terbatas pada radius relevan.
  Keluhan lama juga divalidasi ke pengamatan terkini, karena fasilitas bisa saja sudah diperbaiki.
- **Import isochrone** dari GeoMAPID ke PostGIS, lalu spatial join berbasis jaringan: setiap
  titik ditempelkan ke zona isochrone stasiun terdekat.
- **Dataset Mission (MenuGo, StrukGo, PropertiGo)** diposisikan sebagai jalur pengayaan tahap
  lanjutan. Tidak ada satu variabel pun yang boleh bergantung pada ketersediaannya. Kalau
  cakupannya bertambah, MenuGo menggantikan riset harga internet, StrukGo memperkuat indikator
  karakteristik transaksi, dan PropertiGo menggantikan riset listing properti — semuanya
  tanpa mengubah struktur perhitungan.

## 3. Lapisan AI — arsitektur dua lapis ekstraksi

Dua lapis yang berjalan sejajar dan tidak saling bergantung. Ini kunci agar produk berfungsi
pada seluruh data Activity di ekosistem MAPID, bukan hanya pada data yang mengikuti format
survey tim sendiri.

- **Lapis 1 (universal).** Berjalan pada semua entri, hanya bermodal teks naratif — yang memang
  kewajiban dasar setiap entri Activity.
- **Lapis 2 (opsional).** Hanya berjalan pada entri yang memuat pola penilaian narasumber, yaitu
  skala keramaian berikut atribusinya. Kalau pola tidak ditemukan, entri dilewati tanpa
  menghentikan proses; nilainya ditandai sebagai data berpresisi tinggi kalau ditemukan.

| Model | Lapis | Input | Keluaran dan kontribusi |
|---|---|---|---|
| **Topic Modeling (LDA)** | 1 | Korpus naratif seluruh Activity, termasuk dari tim lain | Arketipe stasiun. Menentukan profil pembobotan yang dipakai, dan menjadi **kelompok pembanding pada mekanisme shrinkage** |
| **Named Entity Recognition** | 1 | Korpus naratif + penyebutan merek di sekitar stasiun | Kelekatan merek terhadap kawasan → kandidat sponsor hak penamaan |
| **Sentiment Analysis** | 1 | Teks keluhan dan catatan kondisi fasilitas | Polaritas kenyamanan sebagai penalti zona, sekaligus pemicu Facility Sponsorship |
| **Parser pola narasumber** | 2 | Entri yang memuat penilaian skala + atribusi | Nilai keramaian per rentang waktu dengan confidence lebih tinggi. Opsional |
| **LLM pada AI Router** | — | Skor terhitung, metadata, pertanyaan pengguna | Jawaban naratif panel AI Insight dan hasil simulasi skenario |

Aturan yang mengikat seluruh lapisan ini:

- Semua model adalah **model terlatih yang tersedia publik untuk Bahasa Indonesia**; LDA
  unsupervised. Tim tidak melatih model dari awal. Data Activity adalah bahan olahan, bukan data latih.
- Keluaran model berbasis teks diperlakukan sebagai **modifier dengan kontribusi maksimal 15%**
  terhadap skor akhir, dan **wajib** melalui validasi silang spasial.
- Seluruh komputasi model dijalankan sebagai **pre-computation di luar sesi pengguna**. Panel AI
  Insight hanya memanggil AI Router dengan konteks skor yang sudah dihitung.
- **OCR tidak lagi ada di jalur ini.** Atribut harga diisi dari riset sumber terbuka yang dicatat
  sumber dan tanggal aksesnya.

## 4. Analisis Spasial

**Isochrone.** Tiga poligon jangkauan berjalan kaki 5, 10, dan 15 menit per stasiun, mengikuti
jaringan jalan pejalan kaki dan bukan buffer lingkaran. Seluruh agregasi transaksi dan kepadatan
titik minat dihitung berdasarkan batas isochrone.

Poligonnya **ditarik lewat API GeoMAPID** (`layers_new/get_layer`, jalur yang sudah dipakai
`scripts/ingest_layers.py`), dijalankan sebagai skrip importer — tidak pernah dipanggil dari
endpoint yang diakses pengguna, sesuai PRD hal. 12. Satu kali generate menghasilkan dua layer,
point dan polygon; layer point adalah titik asal isochrone dan dipakai untuk mencocokkan
poligon ke stasiun. Poligon 5/10/15 bersarang, jadi agregasi titik wajib memakai cincin
eksklusif (`ST_Difference`) supaya satu titik tidak terhitung tiga kali. Rinciannya di
`ADJUSTMENT.md` bagian 7.6.

**Permeability Index.** Rasio luas isochrone terhadap luas lingkaran setara. Makin kecil rasionya,
makin besar hambatan fisik (rel, sungai, jalan arteri) yang membatasi jangkauan nyata pejalan kaki.
Wajib tampil di panel informasi stasiun.

**Klaster tenant.** Analisis ekonomi mikro dilakukan pada tingkat klaster, bukan pada tingkat
stasiun maupun tenant individual. Klaster ditetapkan dengan kriteria eksplisit: kedekatan spasial
dalam radius tertentu ditambah kesamaan kategori usaha. Otomatisasi lewat algoritma pengelompokan
spasial ditunda sampai jumlah titik data mencukupi.

**Pemisahan profil paparan dan profil pembeli.** Populasi yang melintas tidak identik dengan
populasi yang bertransaksi. Profil paparan (dasar Ad-Space) disusun dari pola keramaian antar
rentang waktu dan karakteristik kawasan. Profil pembeli (dasar Tenant Valuation) disusun dari
keterangan pelaku usaha soal produk terlaris dan waktu ramainya, plus rentang harga klaster.

**Resolusi temporal.** Bukan real-time. Data sentimen diagregasi bulanan atau mingguan; kepadatan
pengunjung diprofilkan pada tiga rentang waktu baku: pagi 06.00–09.00, siang 09.00–16.00,
sore 16.00–19.00.

## 5. Mesin Skor

**SEPI (Spatial Economic Potential Index)** — `SEPI = w1*T + w2*E + w3*A + w4*U + w5*C`

| Variabel | Indikator kunci | Sumber |
|---|---|---|
| **T** Transportasi | Volume penumpang, jumlah moda terhubung, status interchange, penilaian keramaian per rentang waktu | Data sekunder, OSM, survey |
| **E** Ekonomi | Rentang harga tingkat klaster tenant, komposisi kategori usaha, tingkat keterisian ruang komersial | Activity + riset harga terbuka |
| **A** Aksesibilitas | Permeability Index | Isochrone GeoMAPID, OSM |
| **U** Urban | Kepadatan titik minat, indeks keberagaman fungsi lahan, jumlah pembangkit perjalanan besar | OSM, profil kawasan |
| **C** Komersial | Jumlah media iklan + statusnya, jumlah lapak terisi dan kosong, indeks sentimen fasilitas | Activity, keluaran NLP |

Alurnya: normalisasi semua variabel ke 0–1 (termasuk ordinal narasumber) → **Entropy Weighting**
dari variabilitas data + **AHP** dari penilaian ahli dengan syarat **CR < 0,10** → gabung
`w = lambda*w_entropy + (1-lambda)*w_AHP` → **TOPSIS** untuk ranking akhir.

Klasifikasi hasil, untuk pengambilan keputusan B2B:

| Rentang | Label | Keputusan bisnis |
|---|---|---|
| 0–39 | Low Potential | Hindari tenant menetap. Cocok untuk vending machine atau iklan OOH informatif berbiaya rendah |
| 40–69 | Moderate Potential | Layak untuk UMKM tipe grab-and-go dengan harga sewa standar pasar |
| 70–100 | Premium Transit Hub | Target Naming Rights, brand korporat besar, justifikasi sewa kelas premium |

**Penanganan ketidakpastian.** Confidence interval dihitung dengan **bootstrap resampling metode
BCa** yang tidak mengasumsikan distribusi normal. Estimasi tiap zona memakai **shrinkage
estimator** `theta(zona) = w*theta(zona) + (1-w)*theta(grup)` dengan `w = n/(n+k)`; kelompok
pembanding adalah zona lain dengan arketipe stasiun serupa hasil LDA. Sampel kecil condong ke
rata-rata kelompok, sampel besar lebih memercayai data zona sendiri.

**GapScore** — `GapScore = D x (1 - S) x F`. Berbentuk perkalian, jadi kategori dengan permintaan
yang tidak terbukti otomatis gugur. Komponen supply mencakup titik minat di luar stasiun **dan**
tenant yang sudah beroperasi di dalam stasiun, supaya kategori yang sebenarnya sudah tersedia
tidak muncul sebagai kesenjangan semu. Dikerjakan pada dua tingkat: tingkat kawasan memilih
kategori, tingkat mikro memilih lapaknya berdasarkan arus pengunjung dan visibilitas.

**TSI (Tenant Survival Index)** — `TSI = 100 x [w_D*D + w_F*F + w_S*(1-S) + w_R*(1-R)]`.
Formulasi tersendiri, **tidak memakai skor SEPI**, hanya berbagi sumber data yang sama.
Variabel R adalah rasio harga sewa yang sedang diuji terhadap median harga pasar sejenis pada
radius yang sama, disusun dari riset listing properti. Kalau pembandingnya terlalu sedikit,
R ditangani lewat shrinkage dan outputnya ditandai berkeyakinan rendah — **bukan diisi angka
asumsi**. Skor visibilitas dari Ad-Space masuk sebagai penalti.

**Valuasi Hak Penamaan** — `CEI = 0,5*T + 0,3*E + 0,2*U`, yaitu rekomposisi SEPI yang menekankan
dimensi eksposur. Diacu ke transaksi pembanding nyata di Indonesia lalu diskalakan. Kandidat
sponsor dipilih dari kelekatan merek hasil NER dan diranking dengan TOPSIS.

## 6. Presentation Layer (Next.js + MapLibre GL JS)

- Basemap **MAPID MAPS**, geometri disajikan sebagai vector tile biner lewat `ST_AsMVT`.
- Tiga layer overlay: **heatmap SEPI**, **poligon isochrone**, **poligon zona indoor stasiun**.
- Titik stasiun diwarnai berdasarkan skor SEPI — ini titik awal user flow.
- Interaksi standar: zoom, klik untuk atribut, nyalakan/matikan layer, filter per stasiun.
- Layout empat komponen: kanvas peta di tengah, panel kiri berisi kontrol layer dan filter,
  panel kanan berisi rincian skor objek terpilih, panel AI Insight dibuka dari kanan bawah
  sebagai lapisan di atas peta supaya konteks spasial tidak hilang.
- Responsif untuk desktop dan seluler.

## 7. Tiga Fitur Utama

1. **Ad-Space Opportunity** — skor potensi per zona, profil paparan, kategori iklan yang
   direkomendasikan beserta alasannya, estimasi harga wajar, rincian variabel pembentuk yang
   dapat dibuka pengguna. Termasuk **Facility Sponsorship Trigger**: keluhan yang lolos validasi
   spasial tampil sebagai penanda di peta, lengkap dengan usulan bentuk sponsorship dan lokasi
   fasilitasnya.
2. **Tenant Valuation** — peringkat kategori usaha beserta GapScore untuk lapak kosong, dan
   skor TSI 0–100 beserta komponen penyusunnya.
3. **Naming Rights** — estimasi nilai kontrak tahunan beserta transaksi pembanding yang dipakai
   sebagai acuan, dan daftar kandidat sponsor terurut beserta dasar pemilihannya.

## 8. Panel AI Insight

- **AI Router** yang menerima skor terhitung + metadata + pertanyaan pengguna, lalu menjawab
  dengan merujuk skor yang sedang ditampilkan.
- **Simulator what-if**: pengguna mengubah asumsi harga sewa dan melihat perubahan TSI tanpa
  berpindah halaman. Ini satu-satunya jalur hitung yang dipicu pengguna, jadi butuh path
  recompute ringan tersendiri di luar batch pre-computation.

## 9. Metadata Transparansi dan Ekspor

- Setiap skor menampilkan jumlah sampel, interval keyakinan, dan penanda confidence. Zona dengan
  data terbatas ditandai eksplisit, bukan disembunyikan.
- Ringkasan analisis per stasiun dapat diunduh, berisi skor, rekomendasi, dan metadatanya.

## 10. Target Non-Fungsional

- Muat peta di bawah 3 detik, respons kueri spasial di bawah 500 ms.
- Komputasi berat dijalankan sebagai pre-computation, hasilnya disimpan sebagai Materialized
  Views, geometri disajikan sebagai vector tile sehingga peramban hanya memuat bagian yang dibuka.
- Deployment: frontend **Vercel**, database **Supabase**. Lapisan komputasi Python (FastAPI)
  butuh host tersendiri — lihat `ADJUSTMENT.md` bagian A2.

---

## Urutan Build

Mengikuti prioritas mitigasi risiko PRD: dahulukan yang sumber datanya paling lengkap, yaitu
SEPI menuju Ad-Space Opportunity, sehingga ada fitur yang dipastikan berfungsi penuh lebih dulu.
Fitur berikutnya dibangun di atas fondasi yang sama — penambahan, bukan membuat ulang.

1. Tarik dan bersihkan data Activity beserta data pendukung
2. Import isochrone GeoMAPID + hitung Permeability Index
3. Lapis 1 NLP (LDA, NER, Sentiment) + validasi silang spasial + pembatas 15%
4. SEPI: Entropy + AHP → TOPSIS, lengkap dengan BCa dan shrinkage
5. Ad-Space Opportunity + Facility Sponsorship
6. Tenant Valuation (GapScore + TSI) dan Naming Rights (CEI)
7. Panel AI Insight + simulator skenario + ekspor ringkasan

Status pengerjaan terkini dan daftar blocker ada di `ADJUSTMENT.md`.
