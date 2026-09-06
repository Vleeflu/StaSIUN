# StaSIUN — Adjustment Pasca-PRD

Dokumen ini membandingkan **PRD final** (`PRD_StaSIUN_Jujursayatidaktahudanjugatidakdiberitahu.pdf`, 24 halaman)
dengan **kondisi repo hari ini** serta dua dokumen perencanaan lama (`LAYER.md`, `OVERVIEW.md`)
yang masih diturunkan dari proposal pra-survey.

Isinya tiga hal: apa yang berubah arahnya, apa yang harus diperbaiki beserta lokasinya,
dan apa yang belum ada sama sekali.

> **Konteks waktu.** Per kalender PRD (Tabel 10), hari ini masuk **M8 (2–8 Sep)** dengan
> target M9 berakhir **13 Sep**. Sisa waktu efektif ±10 hari. Semua prioritas di bawah
> disusun dengan asumsi itu.

> **Status eksekusi (3 Sep).** Paket "Hari 1" sudah dikerjakan: C1–C5, B1, B2, B3, B4, B5,
> C7, dan D1–D9. Tiga catatan penting ada di bagian 6 di bawah — B4 dan B5 tidak dikerjakan
> persis seperti tertulis semula karena tidak ada PostGIS hidup untuk mengujinya, dan A3
> (Supabase) terblokir menunggu kredensial (N11).

---

## 0. Ringkasan: lima pergeseran arah utama

Proposal (yang menjadi dasar `LAYER.md` + `OVERVIEW.md`) dan PRD **tidak lagi sejalan**.
Lima hal berikut berubah setelah survey lapangan, dan semuanya berdampak ke kode.

| # | Topik | Proposal / LAYER.md | PRD final | Dampak |
|---|---|---|---|---|
| 1 | Dataset inti | Empat sumber MAPID setara: StrukGo, MenuGo, PropertiGo, Activity | **Activity Community Maps sebagai satu-satunya dataset utama.** Mission (MenuGo/StrukGo/PropertiGo) *opsional*, cakupannya tidak memadai, "produk tidak menggantungkan variabel manapun pada ketersediaan dataset Mission" (PRD hal. 8) | Semua rencana pipeline berbasis Mission dibatalkan |
| 2 | OCR | Modul inti, model AI #1, tahap #2 build order | **Hilang dari tabel model AI** (PRD hal. 15). Harga diisi dari **riset sumber terbuka** yang dicatat sumber + tanggal akses | Kode OCR jadi di luar lingkup |
| 3 | Isochrone | Dibangkitkan sendiri via **pgRouting** | Dibangkitkan lewat **tools Isochrone GeoMAPID**, hasilnya *disimpan* ke PostGIS untuk diolah ulang (PRD hal. 12) | pgRouting tidak perlu; ganti jadi importer poligon |
| 4 | Sumber ketelitian | OCR + asumsi footfall persona | **Arsitektur dua lapis ekstraksi** + skala keramaian ordinal 1–5 dari narasumber, tiga rentang waktu, median ≥3 narasumber | Model data survey benar-benar baru |
| 5 | Ketidakpastian | Tidak dibahas | **Bootstrap BCa + shrinkage estimator + confidence score wajib tampil di setiap skor** (acceptance criteria, PRD hal. 17) | Kolom metadata wajib di semua tabel skor |

Konsep yang **sama sekali belum tercatat** di `LAYER.md`/`OVERVIEW.md` maupun kode:
Permeability Index, GapScore, formula TSI eksplisit, CEI naming rights, klaster tenant,
pemisahan profil paparan vs profil pembeli, klasifikasi SEPI 0-39/40-69/70-100,
resolusi temporal tiga rentang waktu, dan fitur Ekspor Ringkasan.

---

## 1. Kondisi kode sekarang

### 1.1 Yang benar-benar jalan

| Bagian | Status | Berkas |
|---|---|---|
| Container PostgreSQL 17 + PostGIS 3.5 | Jalan | `docker-compose.yml:2-17` |
| Tabel `stations` (1 tabel, 10 kolom) | Jalan | `backend/app/models/station.py` |
| Seed dari GeoJSON OSM lokal | Jalan | `backend/scripts/seed_stations.py` |
| Ingest dari Geoserver MAPID (5 layer per kota administrasi) | Jalan, butuh kredensial | `backend/scripts/ingest_layers.py`, `backend/data/layers.yml` |
| `GET /api/stations` → GeoJSON FeatureCollection | Jalan | `backend/app/api/routes/stations.py` |
| `GET /api/health` | Jalan | `backend/app/api/routes/health.py` |
| `POST /api/chat` → Gemini via SDK OpenAI-compatible | Jalan | `backend/app/api/routes/chat.py` |
| Peta MapLibre + basemap MAPID + ikon pie multi-lin | Jalan | `frontend/src/components/Map.tsx` |
| Panel kontrol: cari stasiun, filter 6 lin, toggle label, legenda | Jalan | `frontend/src/components/ControlPanel.tsx` |
| Panel stasiun 4 tab (3 tab masih kosong) | Kerangka | `frontend/src/components/StationPanel.tsx` |
| Asisten chat mengambang | Jalan | `frontend/src/components/Assistant.tsx`, `ChatPanel.tsx` |

### 1.2 Flow aplikasi hari ini

```
[ backend/data/railway_station_DKI.geojson ]   atau   [ Geoserver MAPID ]
                 |                                            |
                 +----------> station_import.feature_to_station() <--------+
                                       |  normalisasi nama, tempel roster lin,
                                       |  tandai served/excluded, bikin WKT POINT
                                       v
                              tabel `stations` (PostGIS)
                                       |
                     GET /api/stations |  ST_AsGeoJSON, tanpa skor apa pun
                                       v
                          useStations() ---> Explorer (state pusat)
                                       |
        +------------------------------+-------------------------------+
        v                              v                               v
   Map.tsx                      ControlPanel.tsx                StationPanel.tsx
   ikon per line_key            filter lin (di JS)              tab Ikhtisar terisi,
   klik -> onSelect             2 toggle layer mati             3 tab lain placeholder
        |                                                              |
        +---------------> Assistant/ChatPanel ---> POST /api/chat <-----+
                                                     |  station_id
                                                     v
                                       build_chat_context(db, station_id)
                                       = brief proyek + digest semua stasiun
                                                     v
                                              Gemini -> balasan teks
```

**Bacaan singkatnya:** yang sudah jadi adalah **kulit + satu tabel titik**. Peta bagus,
navigasi bagus, chatbot jujur (prompt-nya melarang mengarang angka). Tetapi **belum ada
satu pun komponen analitik PRD**: tidak ada isochrone, tidak ada Activity, tidak ada skor,
tidak ada zona indoor. Tiga fitur utama produk (Ad-Space, Tenant Valuation, Naming Rights)
masih berupa tab kosong bertuliskan "Modul ini belum dibangun".

Terhadap acceptance criteria PRD (Tabel 8, sembilan fitur): **1 dari 9 terpenuhi sebagian**
— Peta Interaktif, di mana basemap dan interaksi sudah ada, tetapi layer
isochrone/heatmap/indoor belum.

---

## 2. Yang harus diperbaiki (dengan lokasi)

### 2.1 Dokumen perencanaan — sudah usang, wajib ditulis ulang

> **D1–D9 selesai.** `LAYER.md` dan `OVERVIEW.md` sudah ditulis ulang dari PRD. Tabel di
> bawah dipertahankan sebagai rekaman apa yang berubah dan kenapa — nomor barisnya merujuk
> versi lama, jadi jangan dipakai untuk menavigasi berkas yang sekarang.

| # | Lokasi | Masalah | Perbaikan |
|---|---|---|---|
| D1 | `LAYER.md:11` | Menyebut empat sumber MAPID sebagai tabel ingestion inti | Ganti: Activity sebagai dataset utama; Mission jadi bagian "pengayaan lanjutan" |
| D2 | `LAYER.md:15`, `LAYER.md:26`, `LAYER.md:70` | Modul OCR/Vision sebagai model inti dan tahap build #2 | Hapus dari jalur kritis; ganti dengan "riset harga sumber terbuka + pencatatan sumber/tanggal akses" |
| D3 | `LAYER.md:9` | "pgRouting setup for isochrone generation" | Ganti: import poligon isochrone dari tools GeoMAPID lalu simpan di PostGIS |
| D4 | `LAYER.md:22-29` | Tabel empat model AI (OCR, LDA, NER, Sentiment) | Ganti jadi lima baris PRD: LDA, NER, Sentiment, **Parser pola narasumber**, **LLM AI Router** |
| D5 | `LAYER.md:37` | "TSI — confirm exact derivation with the team" | Sudah pasti di PRD hal. 13: `TSI = 100 x [w_D*D + w_F*F + w_S*(1-S) + w_R*(1-R)]` |
| D6 | `LAYER.md` (seluruh) | Tidak memuat Permeability Index, GapScore, CEI, shrinkage/BCa, klaster tenant, profil paparan vs pembeli, ekspor ringkasan | Tambahkan sebagai bagian baru |
| D7 | `OVERVIEW.md:9-19` | Tabel sumber data masih menempatkan StrukGo/MenuGo/PropertiGo sebagai pemasok variabel | Tulis ulang mengikuti PRD Tabel 2 & 3 |
| D8 | `OVERVIEW.md:23` | Merujuk berkas `StaSIUN_Build_List.md` yang **tidak ada di repo** | Ganti rujukan ke `LAYER.md`, atau rename berkasnya |
| D9 | `OVERVIEW.md:35` | Menyebut heatmap + isochrone + indoor seolah sudah tersaji | Pisahkan tegas antara "rencana" dan "sudah jadi" |

### 2.2 Kode — di luar lingkup PRD, harus dipensiunkan

Jalur OCR tidak lagi punya tempat di PRD. Bukan bug, tapi beban rawat dan bisa menyesatkan juri.

| # | Lokasi | Tindakan |
|---|---|---|
| C1 | `backend/app/services/ocr.py` | **Selesai** — dihapus. Masih bisa diambil dari riwayat git (commit `9f00532`) |
| C2 | `backend/app/api/routes/ocr.py` | **Selesai** — dihapus |
| C3 | `backend/app/main.py` | **Selesai** — impor dan router dilepas |
| C4 | `backend/app/core/config.py` | **Selesai** |
| C5 | `backend/example.env` | **Selesai** |

> Kalau mau tetap disimpan sebagai bukti eksplorasi, taruh di branch terpisah dan sebut di
> README sebagai jalur pengayaan Mission dataset — konsisten dengan posisi PRD hal. 8.

### 2.3 Kode — bertentangan dengan PRD, harus diubah isinya

| # | Lokasi | Masalah | Perbaikan |
|---|---|---|---|
| C6 | `backend/app/services/station_context.py:15-65` | Prompt `PROJECT_BRIEF` menyebut "data mitra MAPID (StrukGo, MenuGo, PropertiGo, Activity)" sebagai jajaran setara, dan menyatakan isochrone dihitung dari jaringan pejalan OSM. Dua-duanya sudah tidak sesuai PRD | Tulis ulang: Activity sebagai dataset utama, isochrone dari GeoMAPID, tambahkan definisi Permeability Index, GapScore, TSI, CEI, dua lapis ekstraksi, dan aturan confidence score |
| C7 | `frontend/src/components/StationPanel.tsx` | `PLANNED_SOURCES` memajang StrukGo/MenuGo/PropertiGo sebagai sumber yang direncanakan | **Selesai** — dikerjakan bersama C1–C5 karena ini sisi tampilan dari jalur yang sama; kalau dibiarkan, aplikasi mengiklankan pipeline yang kodenya sudah tidak ada |
| C8 | `frontend/src/components/StationPanel.tsx:194-200` | Baris "Footfall / hari kerja" dan "Median dwell-time" — PRD **secara eksplisit menolak** pengukuran berbasis identitas/arus individual dan menggantinya dengan skala ordinal keramaian per rentang waktu (PRD hal. 10 dan 20) | Ganti jadi: Keramaian pagi/siang/sore (1–5), Permeability Index, Arketipe (LDA), Confidence score |
| C9 | `frontend/src/components/ControlPanel.tsx:82-83` | Hanya dua toggle layer (heatmap SEPI + isochrone). PRD Tabel 8 mensyaratkan **tiga**: isochrone, heatmap, dan **poligon zona indoor** | Tambahkan toggle ketiga |
| C10 | `frontend/src/components/ChatPanel.tsx:95-100` | Teks pembuka menyatakan mati "Skor SEPI dan turunannya belum dihitung" | Akan jadi keliru begitu skor masuk; ikat teksnya ke status data, jangan ditulis permanen |
| C11 | `README.md:98` | Klaim `46 stations stored (45 served, 1 not served)` | **Sudah tidak akurat sejak `station_import.py` menerima semua jaringan.** Berkas sumber berisi 79 titik bernama: 42 KAI Commuter, 13 MRT Jakarta, 12 LRT Jabodebek, 6 LRT Jakarta, 5 KAI, 1 Whoosh. Perbarui angkanya |
| C12 | `README.md:190-200` | "MRT, LRT Jabodebek, LRT Jakarta, dan Whoosh sengaja tidak diikutkan" | Bertentangan dengan `backend/app/services/station_import.py:86-88` yang kini menerima semua moda. Perbarui, dan sebutkan alasannya sesuai PRD: titik non-KAI dipakai sebagai **konektivitas antarmoda** (indikator A / Aksesibilitas) |

### 2.4 Kode — bug dan lubang infrastruktur

| # | Lokasi | Masalah | Perbaikan |
|---|---|---|---|
| B1 | `docker-compose.yml` | Service `backend` tidak meneruskan `GEMINI_API_KEY`. Chatbot **mati total** di jalur Docker walau `.env` sudah diisi | **Selesai** — diteruskan ke container dan didaftarkan di `example.env` |
| B2 | `docker-compose.yml` | MinIO, bucket, dan lima variabel `S3_*` diteruskan ke backend tanpa ada satu baris kode pun yang membacanya | **Selesai — dicabut** (service `minio`, `minio-init`, volume `minio_data`, dan blok `S3_*`). Kalau nanti butuh simpan foto, padanan produksinya Supabase Storage, bukan MinIO yang dihosting sendiri |
| B3 | `backend/app/models/station.py` | ~~Kolom geometri tanpa indeks GiST~~ — **koreksi:** GeoAlchemy2 memakai `spatial_index=True` sebagai default, jadi indeksnya kemungkinan besar memang sudah dibuat. Belum bisa diverifikasi tanpa PostGIS hidup | **Selesai.** Ditulis eksplisit supaya terbaca dan tidak hilang diam-diam kalau kolomnya diubah |
| B4 | `backend/app/models/station.py` (seluruh) | Tidak ada **proyeksi ganda**. PRD mensyaratkan EPSG:4326 untuk rendering + EPSG:32748 untuk perhitungan metrik dalam meter | Tambah kolom `location_utm`, atau konsisten memakai `ST_Transform` di setiap query metrik |
| B5 | `backend/requirements.txt:1` | `alembic==1.19.1` terpasang tapi **tidak ada direktori `alembic/`** — skema dibuat lewat `Base.metadata.create_all` di `backend/docker-entrypoint.sh:35` | Dengan 10+ tabel baru yang akan datang, migrasi mulai perlu. Inisialisasi Alembic sekarang, selagi tabelnya masih satu |
| B6 | `backend/requirements.txt` | Tidak ada satu pun pustaka analitik: `geopandas`, `shapely`, `scikit-learn`, `numpy`, `scipy`, `pandas`, pustaka NLP Indonesia | Tambahkan saat pipeline mulai dibangun |
| B7 | `backend/app/core/config.py:22` | `GEMINI_MODEL: str = "gemini-3.5-flash"` | Pastikan id model ini memang tersedia di endpoint OpenAI-compatible Gemini. Kalau salah, chat gagal saat runtime, bukan saat start, jadi tidak ketahuan sampai dicoba |
| B8 | `backend/app/api/routes/stations.py:18-33` | Mengirim **seluruh** FeatureCollection tanpa paginasi atau tiling | Aman untuk ~79 titik, tapi begitu POI OSM dan poligon isochrone masuk, wajib pindah ke `ST_AsMVT` (PRD hal. 18) |
| B9 | `backend/app/services/station_import.py:23-24` | `UNSERVED = {"GAMBIR"}` ditanam di kode | Cukup untuk sekarang; catat sebagai utang kalau cakupan diperluas ke luar DKI |

### 2.5 Keputusan arsitektur yang harus diambil tim

| # | Perkara | Isi | Rekomendasi |
|---|---|---|---|
| A1 | Backend | PRD hal. 18 menulis "**Next.js API Routes** untuk lapisan penyajian data", kode nyatanya **FastAPI**. PRD juga menulis "Python juga digunakan untuk komputasi", jadi ini bisa dibaca sebagai satu lapisan Python yang sah | **Pertahankan FastAPI.** Menulis ulang jadi API Routes membuang waktu yang tidak ada. Sebut FastAPI sebagai realisasi lapisan komputasi Python saat presentasi |
| A2 | Hosting backend | PRD hal. 22 hanya menyebut **Vercel + Supabase**. FastAPI tidak punya tempat di rencana itu | Frontend → Vercel, database → Supabase, **backend FastAPI → Railway / Render / Fly (free tier)**. Tambahkan ke bagian deployment |
| A3 | Database | Kode memakai PostgreSQL Docker lokal, PRD memakai **Supabase** | Migrasikan lebih awal, jangan di hari terakhir. `DATABASE_URL` sudah terkonfigurasi, jadi ini sebagian besar soal ekstensi PostGIS + kredensial |
| A4 | Isochrone | PRD: dibangkitkan dari tools GeoMAPID | Konfirmasi bentuk keluarannya — unduhan GeoJSON atau API. Kalau unduhan manual, simpan di `backend/data/isochrones/` dan buat skrip importer; jangan menunggu API |
| A5 | Sumber Activity | Belum ada satu pun jalur pengambilan data Activity di kode | `backend/app/services/mapid.py` sekarang hanya bisa `layers_new/get_layer` per `layer_id`. Perlu `layer_id` Activity, termasuk milik tim lain sesuai PRD hal. 8 |

---

## 3. Yang belum dibuat sama sekali

Diurutkan mengikuti Acceptance Criteria PRD (Tabel 8). **Nol dari sembilan** terpenuhi penuh.

### 3.1 Lapisan data — 0%

Yang ada baru satu tabel (`stations`). Yang dibutuhkan minimal:

| Tabel | Isi | Sumber |
|---|---|---|
| `activity_points` | Titik Activity mentah: narasi, foto, kategori, waktu pengamatan, koordinat | MAPID Activity |
| `activity_extractions` | Hasil lapis 1 (arketipe, entitas merek, sentimen) per titik | LDA / NER / Sentiment |
| `crowd_ratings` | Skala 1–5 x tiga rentang waktu x atribusi narasumber (lapis 2) | Parser pola |
| `isochrones` | Poligon 5/10/15 menit per stasiun + `permeability_index` | GeoMAPID → PostGIS |
| `station_zones` | Poligon zona indoor stasiun | Digitasi manual dari survey |
| `tenants` | Tenant existing: nama, kategori, status, posisi relatif gerbang dan peron | Activity survey |
| `tenant_clusters` | Klaster: kedekatan spasial + kesamaan kategori (PRD hal. 14, kriteria eksplisit dulu) | Turunan |
| `ad_spots` | Spot iklan: lokasi, jumlah media terpasang, status terpakai/kosong | Activity survey |
| `facility_issues` | Keluhan fasilitas + bukti fisik + hasil validasi silang spasial | Activity + Sentiment |
| `poi` | Titik minat OSM di sekitar stasiun | OSM |
| `passenger_volume` | Volume penumpang per stasiun | Data sekunder |
| `area_profile` | Profil kawasan: perkantoran / hunian / campuran | Data eksternal |
| `price_references` | Harga menu dan listing sewa + **sumber + tanggal akses** (wajib menurut PRD) | Riset terbuka |
| `mv_sepi_scores` | Materialized view: T, E, A, U, C, SEPI, rank TOPSIS | Mesin skor |
| `mv_gap_scores` | GapScore per kategori usaha per zona | Mesin skor |
| `mv_tsi` | TSI per lapak + komponen penyusunnya | Mesin skor |
| `mv_naming_rights` | CEI, estimasi nilai kontrak, kandidat sponsor | Mesin skor |

Ditambah, di setiap tabel skor: **`n_sample`, `ci_low`, `ci_high`, `confidence`, `estimated_share`**.
Ini bukan tambahan opsional — PRD menjadikannya acceptance criteria tersendiri (Metadata Transparansi).

### 3.2 Pipeline pengolahan — 0%

- [ ] Penarikan Activity dari MAPID, termasuk entri tim lain
- [ ] Cleaning: koordinat tak wajar, titik duplikat, penyeragaman nama dan kategori, normalisasi satuan harga
- [ ] **Lapis 1 (universal):** LDA arketipe → NER merek → Sentiment keluhan, berjalan pada semua entri bermodal teks naratif
- [ ] **Lapis 2 (opsional):** parser pola narasumber → skala keramaian + atribusi, dilewati kalau pola tidak ditemukan
- [ ] Spatial cross-validation: setiap temuan berbasis teks diuji terhadap kondisi spasial (PRD hal. 12)
- [ ] Pembatas kontribusi model teks **maksimal 15%** terhadap skor akhir
- [ ] Import poligon isochrone GeoMAPID ke PostGIS
- [ ] Hitung **Permeability Index** = luas isochrone dibagi luas lingkaran setara
- [ ] Spatial join seluruh titik ke zona isochrone
- [ ] Agregasi ke tingkat zona dan stasiun (bukan penggabungan antar-entri secara langsung)

### 3.3 Mesin skor — 0%

- [ ] Normalisasi seluruh variabel ke rentang 0–1, termasuk indikator ordinal narasumber
- [ ] **Entropy Weighting**
- [ ] **AHP** + pemeriksaan rasio konsistensi CR < 0,10
- [ ] Penggabungan bobot `w = lambda*w_entropy + (1-lambda)*w_AHP`
- [ ] **TOPSIS** untuk ranking akhir
- [ ] Klasifikasi SEPI: 0–39 Low, 40–69 Moderate, 70–100 Premium Transit Hub, lengkap dengan kalimat keputusan bisnisnya
- [ ] **Bootstrap BCa** untuk confidence interval
- [ ] **Shrinkage estimator** `theta_zona = w*theta(zona) + (1-w)*theta(grup)`, `w = n/(n+k)`, grup pembanding = arketipe hasil LDA
- [ ] **GapScore = D x (1 - S) x F**, dua tingkat skala (kawasan lalu mikro); komponen supply mencakup POI luar stasiun **dan** tenant di dalam stasiun
- [ ] **TSI = 100 x [w_D*D + w_F*F + w_S*(1-S) + w_R*(1-R)]**, dengan R = harga sewa yang diuji dibagi median pasar sejenis pada radius sama
- [ ] Penalti visibilitas dari fitur Ad-Space ikut masuk ke TSI
- [ ] **CEI = 0,5*T + 0,3*E + 0,2*U** dan penskalaannya ke transaksi pembanding nyata di Indonesia
- [ ] Ranking kandidat sponsor via TOPSIS di atas hasil NER
- [ ] Pemisahan **profil paparan** (dasar Ad-Space) dan **profil pembeli** (dasar Tenant Valuation)

### 3.4 API — 3 dari ~14 endpoint

Sudah ada: `/api/health`, `/api/stations`, `/api/chat` (plus `/api/ocr/extract` yang dibuang).
Belum ada:

- [ ] `GET /api/stations/{id}/sepi` — skor + rincian T/E/A/U/C + metadata keyakinan
- [ ] `GET /api/stations/{id}/isochrones` — tiga poligon + Permeability Index
- [ ] `GET /api/stations/{id}/zones` — poligon zona indoor
- [ ] `GET /api/zones/{id}/adspace` — skor, profil paparan, kategori iklan + alasan, estimasi harga wajar
- [ ] `GET /api/zones/{id}/gap` — peringkat kategori usaha + GapScore
- [ ] `GET /api/lapak/{id}/tsi` — TSI + komponen penyusunnya
- [ ] `POST /api/scenario/tsi` — **hitung ulang TSI dari asumsi sewa yang diubah user**, jalur ringan yang dipanggil saat itu juga
- [ ] `GET /api/stations/{id}/naming-rights` — nilai kontrak tahunan + transaksi pembanding + kandidat sponsor
- [ ] `GET /api/facility-issues` — keluhan yang lolos validasi + usulan bentuk sponsorship
- [ ] `GET /api/stations/{id}/export` — ringkasan yang dapat diunduh
- [ ] `GET /api/tiles/{z}/{x}/{y}.mvt` — vector tile via `ST_AsMVT`

### 3.5 Frontend — kerangka ada, isi belum

- [ ] Layer heatmap SEPI (toggle sudah ada, statusnya mati)
- [ ] Layer poligon isochrone (toggle sudah ada, statusnya mati)
- [ ] **Layer poligon zona indoor** (toggle belum ada sama sekali)
- [ ] Pewarnaan titik stasiun berdasarkan skor SEPI — PRD hal. 18 menjadikan ini **titik awal user flow**
- [ ] Isi tab **Ad-Space**: skor potensi, profil paparan, kategori iklan + alasan, estimasi harga wajar, rincian variabel yang bisa dibuka
- [ ] Isi tab **Tenant**: peringkat kategori + GapScore, TSI 0–100 + komponen
- [ ] Isi tab **Naming**: nilai tahunan + transaksi pembanding + kandidat sponsor terurut
- [ ] Penanda **Facility Sponsorship** di peta + usulan bentuk sponsorship dan lokasi fasilitasnya
- [ ] Komponen **metadata keyakinan** yang dipakai ulang di semua skor (n sampel, interval, confidence)
- [ ] **Simulator what-if**: ubah asumsi sewa, TSI berubah tanpa pindah halaman
- [ ] Tombol **Ekspor ringkasan** per stasiun
- [ ] Uji tampilan **mobile**. PRD hal. 18 mensyaratkan responsif; layout sekarang (panel kiri mengambang + panel kanan 400px + peta) belum diuji di layar sempit

### 3.6 Panel AI Insight — baru setengah

Chat sudah ada dan sudah sadar stasiun mana yang sedang dibuka. Yang belum:

- [ ] **AI Router** — konteks yang dikirim ke LLM masih hanya daftar stasiun (`backend/app/services/station_context.py:120-133`); PRD mensyaratkan skor terhitung beserta metadatanya ikut masuk
- [ ] Jawaban wajib **merujuk skor yang sedang ditampilkan** (acceptance criteria PRD Tabel 8)
- [ ] **Simulasi skenario** — belum ada jalur hitung ulang sama sekali

---

## 4. Yang dibutuhkan (blocker di luar koding)

Tidak ada satu pun angka bisa keluar tanpa mereka.

| # | Kebutuhan | Untuk | Status |
|---|---|---|---|
| N1 | **Ekspor data Activity** hasil survey tim, plus akses entri tim lain | Seluruh pipeline NLP dan pemetaan objek | Belum ada di repo |
| N2 | **Poligon isochrone GeoMAPID** 5/10/15 menit untuk tiap stasiun studi | Permeability Index, semua agregasi zona | Belum ada |
| N3 | **Denah/zona indoor** stasiun yang disurvey, dalam bentuk terdigitasi | Layer indoor, Ad-Space per zona, klaster tenant | Belum ada |
| N4 | **Data volume penumpang** stasiun KRL DKI | Variabel T, dasar estimasi paparan | Belum ada |
| N5 | **Data profil kawasan** (perkantoran / hunian / campuran) | Variabel U, penyusunan profil paparan | Belum ada |
| N6 | **Riset harga menu + listing sewa komersial** beserta sumber dan tanggal akses | Variabel E, variabel R pada TSI | Belum ada |
| N7 | **Benchmark tarif per seribu paparan** dari laporan industri OOH | Validasi harga wajar Ad-Space | Belum ada |
| N8 | **Transaksi pembanding naming rights di Indonesia** | Penskalaan CEI ke rupiah | Belum ada |
| N9 | **Penilaian ahli untuk AHP** (matriks perbandingan berpasangan, CR < 0,10) | Bobot SEPI | Belum ada |
| N10 | **Ekstrak POI OSM** di sekitar stasiun | Variabel U dan komponen supply GapScore | Belum ada |
| N11 | Kredensial **Supabase** produksi | Deployment | Belum ada |
| N12 | Pilihan **pustaka NLP Bahasa Indonesia** terlatih (sentimen + NER) | Lapis 1 ekstraksi | Belum diputuskan |

---

## 5. Urutan kerja yang disarankan (sisa ±10 hari)

PRD hal. 21 sudah memberi kunci prioritasnya sendiri: *"Prioritas pengembangan dari yang
sumber datanya paling lengkap, yaitu SEPI menuju Ad-Space Opportunity, sehingga terdapat
fitur yang dipastikan berfungsi penuh lebih dahulu."* Ikuti itu secara harfiah.

**Hari 1 — bersih-bersih dan pondasi (murah, menghilangkan kontradiksi)** — **SELESAI**, kecuali A3
1. ~~C1–C5 (pensiunkan OCR), B1, B2~~ selesai
2. ~~D1–D9 (tulis ulang `LAYER.md` dan `OVERVIEW.md`)~~ selesai
3. ~~B3, B4, B5~~ selesai dengan penyesuaian, lihat bagian 6
4. **A3 (Supabase) — terblokir**, menunggu kredensial (N11). Ini yang paling perlu dikejar duluan

**Hari 2–4 — data masuk (tanpa ini semuanya berhenti)**
5. N1, N2 → tabel `activity_points` dan `isochrones`, lalu hitung Permeability Index
6. N4, N5, N10 → `passenger_volume`, `area_profile`, `poi`
7. Endpoint isochrone + layer isochrone di peta → **satu acceptance criteria selesai penuh**

**Hari 4–7 — SEPI sampai tampil di peta**
8. Lapis 1 NLP (LDA → NER → Sentiment) + spatial cross-validation + pembatas 15%
9. Entropy + AHP (butuh N9) + TOPSIS + klasifikasi tiga rentang
10. `mv_sepi_scores` lengkap dengan kolom keyakinan; bootstrap BCa + shrinkage
11. Heatmap SEPI + pewarnaan titik stasiun + isi tab Ikhtisar dengan angka asli

**Hari 7–9 — fitur di atas fondasi yang sama**
12. Ad-Space: zona indoor (N3) + `ad_spots` + profil paparan + estimasi harga (N7)
13. Facility Sponsorship trigger — menempel ke output Sentiment, jadi relatif murah
14. Tenant Valuation: GapScore + TSI (N6) + simulator what-if
15. Naming Rights: CEI + kandidat sponsor dari NER (N8)

**Hari 9–10 — penyelesaian**
16. AI Router: suntikkan skor terhitung ke konteks LLM (C6)
17. Ekspor ringkasan, komponen metadata keyakinan di semua panel, uji tampilan mobile
18. Deploy (A2), perbarui README dan dokumentasi cara menjalankan lokal — PRD hal. 22 menyebut ini bagian dari rencana repositori

**Kalau waktu habis:** yang wajib utuh adalah Peta Interaktif + Isochrone + SEPI + Ad-Space,
persis urutan mitigasi risiko di PRD. Tenant dan Naming boleh tampil sebagai hasil terbatas
dengan confidence rendah yang **ditandai jujur**. Mekanisme itu memang sudah dirancang di
PRD, jadi memakainya bukan kompromi, melainkan menjalankan metode yang dijanjikan.


---

## 6. Catatan eksekusi paket Hari 1

Dikerjakan 3 Sep. Mesin tempat pengerjaan **tidak punya dependensi Python terpasang dan
Docker tidak berjalan**, jadi tidak ada satu pun perubahan skema yang bisa diuji terhadap
PostGIS yang hidup. Itu mengubah dua item dari rencana semula.

### Yang berubah dari rencana

**B4 — proyeksi ganda.** Rencana awal menambah kolom `location_utm` sebagai generated column
`ST_Transform(location, 32748)`. Tidak jadi: kalau ekspresi itu ditolak PostgreSQL saat
pembuatan tabel, `create_all` gagal dan **seluruh stack tidak bisa start** — terlalu mahal
untuk perubahan yang tidak bisa diuji dulu. Gantinya, konvensinya dipusatkan di
`backend/app/core/geo.py`: konstanta `SRID_RENDER` (4326) dan `SRID_METRIC` (32748) plus
helper `metric()` yang membungkus `ST_Transform`. Semua `ST_Area`, `ST_Distance`, `ST_Buffer`,
dan `ST_DWithin` wajib lewat helper itu, jangan memanggil `ST_Transform` lepasan. Kolom UTM
tersimpan bisa ditambahkan nanti kalau profiling menunjukkan transformasi per-query jadi beban.

**B5 — Alembic.** Terpasang `backend/alembic.ini` + `backend/alembic/env.py` (sudah tersambung
ke `settings.DATABASE_URL` dan `Base.metadata`, lengkap dengan penyaring tabel bawaan PostGIS
dan indeks spasial GeoAlchemy2 supaya autogenerate tidak menghasilkan indeks ganda) + template
revisi. **Belum ada satu revisi pun, dan `docker-entrypoint.sh` masih memakai
`Base.metadata.create_all`** — menukar cara pembuatan skema tanpa bisa mengujinya berisiko
membuat backend gagal start untuk semua orang. Langkah penyelesaiannya, tiga perintah, ada di
`backend/alembic/README.md`; siapa pun yang punya database jalan bisa menuntaskannya dalam
lima menit. `Dockerfile` sudah menyalin berkas Alembic supaya peralihannya nanti cukup satu baris.

### Yang perlu diverifikasi orang dengan database jalan

1. `docker compose up --build` masih naik bersih setelah MinIO dicabut dan `GEMINI_API_KEY`
   ditambahkan. Berkas compose sudah lolos `docker compose config`, tapi itu hanya memvalidasi
   sintaks, bukan menjalankan container.
2. Asisten AI benar-benar hidup di jalur Docker sekarang — ini yang diperbaiki B1.
3. Indeks `idx_stations_location` memang ada di database (`\d stations` di psql). Kalau ternyata
   tidak ada, berarti default GeoAlchemy2 tidak seperti dugaan dan koreksi pada baris B3 di atas
   yang keliru, bukan temuan aslinya.
4. Tuntaskan Alembic mengikuti `backend/alembic/README.md`.

### Yang belum disentuh dan tetap tercatat

C6, C8, C9, C10, C11, C12, B6, B7, B8, B9 — semuanya masih berlaku persis seperti tertulis di
bagian 2. Dua yang paling mengganggu di antaranya: `README.md` masih menyebut angka dan aturan
penyaringan jaringan yang sudah tidak akurat (C11, C12), dan prompt asisten di
`station_context.py` masih memakai peta dataset versi proposal (C6).

---

## 7. Rencana lanjutan (6–13 Sep)

Ditulis 6 Sep, menggantikan urutan di bagian 5 yang disusun 3 Sep dengan asumsi sisa
±10 hari. Sisa waktu efektif sekarang **7 hari**.

### 7.1 Kondisi yang mengubah rencana

1. **Blocker Hari 1 belum terbuka.** Mesin pengerjaan masih tanpa Docker yang berjalan
   dan tanpa dependensi Python terpasang, jadi empat verifikasi di bagian 6 masih
   menggantung dan `alembic/versions/` masih kosong. Ini bukan blocker data — bisa
   dibuka sendiri dalam belasan menit, dan menahan seluruh kerja skema di belakangnya.
2. **N1 dan N2 masih nol.** Ekspor Activity hasil survey tim dan poligon isochrone
   GeoMAPID belum dilakukan sama sekali. Keduanya tindakan manual yang hanya bisa
   dikerjakan tim, dan sekarang jadi risiko jadwal terbesar.
3. **Koreksi angka pada C11.** Berkas sumber berisi 79 titik bernama, tetapi yang
   tersimpan **78** karena `JAKARTAGUDANG` disaring `EXCLUDED`. Pecahan jaringan yang
   benar: 42 KAI Commuter, 13 MRT Jakarta, 12 LRT Jabodebek, 6 LRT Jakarta, **4** KAI,
   1 Whoosh; 1 tidak dilayani. Angka "79" dan "5 KAI" pada baris C11 di bagian 2.3
   menghitung emplasemen barang yang tidak pernah masuk database.

### 7.2 Tiga variabel SEPI tidak menunggu siapa pun

Dari lima variabel, **T, A, dan U tidak bergantung pada Activity**. U seluruhnya dari
titik minat OSM yang bisa ditarik sendiri lewat Overpass hari ini juga; T dari volume
penumpang dan moda terhubung; A dari Permeability Index, yang hanya menunggu satu berkas
isochrone. Hanya E dan C yang benar-benar butuh Activity.

Konsekuensinya: **mulai dari U, jangan menunggu N1.** SEPI bisa punya angka asli untuk
tiga dari lima variabel sebelum satu entri Activity pun masuk, dan E/C menyusul lewat
mekanisme confidence rendah yang memang sudah dirancang PRD.

### 7.3 Cara data Activity diambil

Menjawab kalimat PRD hal. 10 soal "data Activity universal". Yang dijanjikan di sana
adalah **kemampuan pipeline memproses entri apa pun bentuknya**, bukan cakupan
pengambilan. PRD tidak pernah menjanjikan seluruh Activity se-ekosistem ditarik, dan
menariknya pun akan melanggar aturan cleaning di hal. 12 yang menyingkirkan titik di
luar wilayah studi.

Yang wajib dihindari hanya satu: **kurasi manual**. Begitu entri dipilih satu per satu,
yang bekerja adalah penilaian manusia, bukan sistemnya, dan klaim universalitas gugur.

Karena itu **entri tidak dipilih, wilayah yang dipilih.** Seluruh penyaringan berupa
aturan yang dieksekusi kode:

| Gate | Aturan | Dasar |
|---|---|---|
| Spasial | Titik berada di dalam isochrone 15 menit stasiun studi; selama isochrone belum ada, radius 1 km | PRD hal. 12 — agregasi dihitung berdasarkan batas isochrone |
| Wilayah | Koordinat di dalam bbox DKI, tidak bernilai nol, tidak di luar wilayah studi | PRD hal. 12 — cleaning |
| Kualitas | Ada teks naratif di atas panjang minimum; titik duplikat dibuang | PRD hal. 12 — penghapusan duplikat |
| Temporal | Entri di luar jendela kebaruan ditandai; keluhannya wajib divalidasi ke pengamatan terkini | PRD hal. 12 — keluhan lama bisa sudah tidak berlaku |

Yang lolos masuk ke lapis 1 **tanpa perlakuan khusus** — tidak boleh ada cabang kode yang
membedakan entri tim sendiri dari entri tim lain. Jumlah yang lolos dan gugur di setiap
gate dicatat, karena angka itu yang jadi bukti universalitas saat presentasi: dari sekian
entri di dalam bbox milik siapa pun, sekian lolos, sekian di antaranya memuat pola
narasumber.

**Arsitektur ingest:** adapter sumber (berkas lokal / `layer_id` MAPID / query bbox bila
API-nya tersedia) → tabel `activity_raw` yang menyimpan payload apa adanya beserta
provenance → gating dan cleaning → `activity_points` → lapis 1. Bentuk ini membuat satu
hal yang belum diketahui — apakah MAPID mengekspos endpoint query Activity publik, atau
Activity tim lain hanya bisa diambil per `layer_id` — berhenti menjadi blocker: yang
berubah hanya adapternya.

**Kalau Activity tim lain sama sekali tidak bisa diakses,** universalitas tetap dapat
dibuktikan tanpa data eksternal lewat **uji ablasi**: ambil entri tim sendiri, buang
bagian terstrukturnya (pola penilaian narasumber), jalankan pipeline yang sama. Kalau
lapis 1 tetap menghasilkan arketipe, NER, dan sentimen dengan confidence lebih rendah,
itu persis perilaku yang dijanjikan untuk entri tidak terstruktur — dan tersaji sebagai
angka, bukan klaim. PRD hal. 13 sudah menyebut kondisi ini eksplisit: shrinkage dirancang
antara lain untuk "zona yang titiknya berasal dari entri tidak terstruktur sehingga hanya
melewati lapis ekstraksi universal".

### 7.4 Urutan kerja

Prioritas yang dipilih: **dalam dulu, SEPI menuju Ad-Space**, sesuai mitigasi risiko PRD
hal. 21. Tenant dan Naming tampil terbatas dengan confidence rendah yang ditandai jujur.

| Hari | Isi |
|---|---|
| 6 Sep (Fase 0) | Nyalakan Docker, pasang dependensi, `docker compose up --build`. Tuntaskan empat verifikasi bagian 6: compose naik bersih, chat hidup di jalur Docker (B1), `idx_stations_location` ada (B3), revisi awal Alembic + tukar `create_all` jadi `alembic upgrade head` (B5). Sekalian B7, pastikan id `GEMINI_MODEL` sah |
| 6–7 Sep (Fase 1) | Satu revisi Alembic berisi 13 tabel dasar `LAYER.md` bagian 1, dengan mixin metadata skor (`n_sample`, `ci_low`, `ci_high`, `confidence`, `estimated_share`). Semua geometri lewat `SRID_RENDER` + GiST eksplisit. Materialized view menyusul sebagai revisi SQL setelah mesin skornya jadi |
| 7–8 Sep (Fase 2) | Jalur data mandiri: **POI OSM lewat Overpass** lebih dulu (N10, tidak terblokir), lalu CSV `passenger_volume` (N4) dan `area_profile` (N5) berkolom `source` + `accessed_at`. Importer isochrone dari `backend/data/isochrones/` (A4) dan importer Activity dua jalur, ditulis sekarang supaya jalan seketika begitu berkasnya datang. Semua importer idempotent dan punya `--dry-run` |
| 8–10 Sep (Fase 3) | Mesin skor di `app/services/scoring/`: normalisasi → entropy → AHP (matriks pakar YAML + cek CR < 0,10) → TOPSIS → klasifikasi tiga rentang, plus bootstrap BCa dan shrinkage. Numpy murni, diuji unit dengan data sintetis, tidak menunggu data sungguhan |
| 10–11 Sep (Fase 4–5) | Permeability Index lewat `geo.metric()`, endpoint isochrone, layer poligon + toggle ketiga zona indoor (C9). Lalu `/stations/{id}/sepi`, pewarnaan titik stasiun, heatmap, komponen metadata keyakinan yang dipakai ulang, dan isi tab Ikhtisar — sekalian mengganti baris footfall/dwell-time (C8) |
| 11–12 Sep (Fase 6) | Ad-Space + Facility Sponsorship. Tenant dan Naming menyusul dengan degradasi jujur |
| 12–13 Sep | AI Router (C6), ekspor ringkasan, uji tampilan mobile, deploy (A2), README (C11, C12), teks pembuka ChatPanel (C10) |

### 7.5 Yang hanya bisa dikerjakan tim, bukan oleh kode

Diurut menurut seberapa besar ia menahan yang lain:

1. **Ekspor poligon isochrone GeoMAPID** untuk stasiun studi (N2). Membuka variabel A,
   gate spasial Activity, dan satu acceptance criteria penuh. Paling murah, paling besar
   dampaknya — kerjakan pertama.
2. **Ekspor Activity hasil survey tim** (N1). Membuka E, C, dan seluruh lapis 1.
3. **Kredensial Supabase** (N11). Menahan A3, dan A3 tidak boleh jatuh di hari terakhir.
4. **Matriks perbandingan berpasangan AHP** (N9). Dibutuhkan Fase 3; tanpa ini bobot
   hanya bisa dari entropy.
5. Konfirmasi apakah Activity tim lain dapat diakses, dan lewat jalur apa. Menentukan
   adapter mana yang dipakai, bukan menahan pipeline.
