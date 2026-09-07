# Bank Pengetahuan — Villyan

Berkas ini bukan penilaian, melainkan **peta kalibrasi**: dipakai untuk menentukan seberapa dalam
sebuah konsep perlu dijelaskan sebelum dipakai. Konsep berstatus `Belum` dijelaskan dari nol;
konsep berstatus `Kuasai` cukup dipakai tanpa penjelasan ulang.

Cara membaca dan mengisinya ada di `session_initialization.md` bagian 3.3 dan 3.4.

## Arti status

| Status | Artinya |
|---|---|
| `Kuasai` | Bisa dipakai dan dijelaskan sendiri tanpa bantuan |
| `Dasar` | Paham dan sudah terbukti — pernah memakai sendiri, atau menjawab kuisnya dengan benar |
| `Dijelaskan` | Sudah dijelaskan di sesi dan diikuti, tetapi **belum dibuktikan**. Menunggu kuis atau praktik untuk naik ke `Dasar` |
| `Belum` | Belum pernah dipakai, atau belum paham konsepnya |

Kolom **Dari mana** menerangkan asal status: `awal` (kondisi saat bank ini dibuat, 6 Sep 2026),
`penjelasan` (dijelaskan di sesi, dengan tanggalnya), `kuis` (dijawab benar, dengan tanggalnya),
atau `praktik` (dikerjakan sendiri sampai berhasil).

---

## A. Fundamental dan Bahasa Pemrograman

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| C | Kuasai | awal | Bahasa yang paling dikuasai |
| C++ | Kuasai | awal | — |
| OOP (kelas, pewarisan, polimorfisme) | Dasar | awal | Pernah dipelajari, sebagian besar sudah lupa. Perlu penyegaran saat ketemu kelas Python |
| Mixin | Dijelaskan | penjelasan 6 Sep | Kelas yang tidak pernah menjadi tabel atau objek sendiri; isinya kumpulan kolom atau perilaku yang ditempelkan ke kelas lain lewat pewarisan. Dipakai di `app/models/mixins.py` supaya lima kolom metadata skor tidak ditulis ulang di empat tabel |
| Matematika dan aljabar linear | Kuasai | awal | Latar studi. Berguna untuk mesin skor |
| Statistik inferensial (interval keyakinan, resampling) | Belum | awal | Dibutuhkan untuk bootstrap BCa dan shrinkage |
| Python (sintaks dasar) | Belum | awal | Seluruh backend proyek ini memakai Python |
| Type hints Python (`str \| None`, `list[str]`) | Belum | awal | Dipakai di semua model dan service backend |
| JavaScript / TypeScript | Dasar | awal | Lewat Next.js dan Nest.js, sebagian besar dibantu AI |

## B. Backend dan API

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| Apa itu backend dan bedanya dengan frontend | Belum | awal | Fondasi paling dasar; jelaskan lebih dulu sebelum yang lain |
| Protokol HTTP (request, response, status code) | Belum | awal | — |
| REST dan endpoint (`GET /api/stations`) | Belum | awal | Repo ini punya 3 endpoint aktif |
| JSON sebagai format pertukaran data | Belum | awal | — |
| Laravel | Dasar | awal | Pengalaman webdev pertama |
| Nest.js | Dasar | awal | Masih tahap pemula |
| FastAPI | Belum | awal | Framework backend yang dipakai proyek ini |
| Variabel lingkungan dan berkas `.env` | Dasar | praktik 6 Sep | Sudah membuat dan mengisi `.env` sendiri. Catatan penting: proyek ini punya **dua** berkas `.env` — yang di root dibaca Docker Compose, yang di `backend/` dibaca backend saat dijalankan tanpa Docker |
| Beda API key, basemap key, dan `layer_id` di MAPID | Dijelaskan | penjelasan 6 Sep | Basemap key untuk menggambar peta di browser; API key untuk menarik isi data layer dari Geoserver di server; `layer_id` menunjuk layer mana. API key dan project_id sama untuk semua layer dalam satu proyek, yang berbeda per layer hanya `layer_id` |
| Base URL sebagai penentu tujuan panggilan API | Dijelaskan | penjelasan 6 Sep | Satu SDK bisa dipakai untuk banyak penyedia karena tujuannya ditentukan base URL, bukan oleh SDK-nya. Kunci yang benar tetap ditolak kalau dikirim ke base URL milik penyedia lain |
| CORS | Belum | awal | Sudah aktif di `backend/app/main.py` |
| Sinkron vs asinkron | Belum | awal | — |

## C. Frontend dan Antarmuka

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| React: komponen dan props | Dasar | awal | — |
| React: state dan `useState` | Dasar | awal | — |
| React: efek samping dan `useEffect` | Belum | awal | Dipakai di `frontend/src/hooks/useStations.ts` |
| Next.js App Router | Dasar | awal | Struktur `src/app/` di repo ini |
| `"use client"` dan komponen server vs klien | Belum | awal | Muncul di hampir semua komponen repo ini |
| Tailwind CSS | Belum | awal | Seluruh gaya tampilan repo ini memakainya |
| MapLibre GL JS | Belum | awal | Mesin peta yang dipakai `Map.tsx` |
| Konsep layer dan sumber data pada peta | Belum | awal | Inti dari seluruh tampilan produk |
| Mengambil data dari API di frontend (`fetch`) | Belum | awal | `frontend/src/lib/api.ts` |

## D. Basis Data dan Migrasi

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| SQL dasar (SELECT, WHERE, JOIN) | Dasar | awal | — |
| PostgreSQL | Dasar | awal | Masih tahap pemula |
| Supabase | Dasar | awal | Akan dipakai sebagai database produksi |
| Prisma (ORM) | Dasar | awal | Pembanding yang berguna untuk memahami SQLAlchemy |
| Apa itu ORM dan kenapa dipakai | Belum | awal | — |
| Model harus diimpor supaya terdaftar di ORM | Dasar | kuis 6 Sep | SQLAlchemy hanya tahu sebuah tabel ada kalau berkas modelnya pernah diimpor. Lupa mendaftarkannya bukan menghasilkan error, melainkan tabel yang diam-diam tidak pernah dibuat. Karena itu semua model dikumpulkan di `app/models/__init__.py` |
| SQLAlchemy | Belum | awal | ORM yang dipakai backend proyek ini |
| Migrasi skema dan Alembic | Dijelaskan | penjelasan 6 Sep | Buku catatan perubahan database: tiap perubahan struktur jadi satu berkas revisi berisi langkah maju dan langkah mundur, berantai, sehingga database mana pun bisa dibawa ke bentuk sama dengan `alembic upgrade head`. Bedanya dengan `create_all` yang hanya bisa **membuat** tabel baru dan diam saja saat ada kolom baru di tabel lama |
| Indeks basis data | Belum | awal | — |
| Migrasi bisa mengusulkan menghapus tabel yang bukan milik kita | Dijelaskan | penjelasan 6 Sep | Autogenerate membandingkan model dengan seluruh isi database. Ekstensi seperti `postgis_tiger_geocoder` membawa 36 tabelnya sendiri, dan tanpa penyaring, Alembic menyimpulkan tabel-tabel itu harus dihapus. Aturan penyaringnya: objek hasil refleksi yang tidak punya padanan di model bukan milik kita |
| Berkas migrasi wajib dibaca sebelum dijalankan | Dijelaskan | penjelasan 6 Sep | Autogenerate menghasilkan usulan, bukan kebenaran. Berkasnya diperiksa dulu — hitung `create_table` dan `drop_table`-nya — baru dijalankan |
| Nilai bawaan sisi Python vs sisi database | Dijelaskan | penjelasan 6 Sep | `default=` di SQLAlchemy hanya berlaku kalau data masuk lewat kode kita. Data yang masuk lewat SQL langsung, `COPY`, atau Adminer melewatinya — dan kolom NOT NULL langsung menolak. Yang berlaku untuk semua jalur adalah `server_default=`, karena databasenya sendiri yang mengisinya |
| Pembanding autogenerate harus dinyalakan | Dijelaskan | penjelasan 6 Sep | `compare_type` dan `compare_server_default` mati secara bawaan di Alembic. Matinya tidak menghasilkan error — autogenerate hanya menghasilkan migrasi kosong seolah tidak ada yang berubah. Keduanya dinyalakan di `alembic/env.py` |
| Materialized view | Belum | awal | Wajib menurut PRD untuk hasil komputasi berat |

## E. GIS dan Analisis Spasial

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| PostGIS | Belum | awal | Ekstensi spasial PostgreSQL, inti proyek ini |
| Sistem koordinat dan SRID | Belum | awal | — |
| EPSG:4326 vs EPSG:32748 dan kenapa dibedakan | Belum | awal | Konvensinya ada di `backend/app/core/geo.py` |
| GeoJSON | Belum | awal | Format data stasiun di repo ini |
| WKT (`POINT(...)`) | Belum | awal | Dipakai `station_import.py` |
| Fungsi `ST_*` (ST_Area, ST_Distance, ST_Contains, ST_Difference) | Belum | awal | — |
| Indeks spasial GiST | Belum | awal | Disyaratkan PRD untuk kecepatan kueri |
| Isochrone dan bedanya dengan buffer lingkaran | Belum | awal | Analisis jangkauan inti produk |
| Poligon isochrone bersarang dan bahaya perhitungan ganda | Dijelaskan | penjelasan 6 Sep | Isochrone 10 menit sudah memuat seluruh area 5 menit. Menghitung titik langsung di tiap poligon membuat satu titik terhitung berkali-kali, dan penggelembungannya tidak merata antar-stasiun sehingga peringkat ikut kacau |
| Cincin eksklusif dengan `ST_Difference` | Dijelaskan | penjelasan 6 Sep | `cincin 10 = poligon 10 dikurangi poligon 5`. Dipakai untuk agregasi per zona. Bentuk kumulatif (poligon apa adanya) tetap benar untuk pertanyaan "berapa total yang terjangkau dalam N menit" — kesalahannya bukan memilih salah satu, melainkan tertukar |
| Permeability Index | Dijelaskan | penjelasan 6 Sep | Luas isochrone dibagi luas lingkaran setara. Radius lingkaran pembandingnya = kecepatan jalan kaki x waktu, jadi angka kecepatan yang dipakai saat generate wajib dicatat |
| Spatial join | Belum | awal | Menempelkan titik ke zona |
| Vector tile dan `ST_AsMVT` | Belum | awal | Untuk performa peta saat data membesar |
| OpenStreetMap dan Overpass API | Belum | awal | Sumber titik minat untuk variabel U |

## F. Infrastruktur, Docker, dan Deployment

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| Apa itu container dan kenapa dipakai | Belum | awal | — |
| Docker: image, container, volume, port | Belum | awal | — |
| Docker Compose dan berkas `docker-compose.yml` | Belum | awal | Menjalankan seluruh stack proyek ini |
| Meneruskan variabel lingkungan ke container | Belum | awal | Penyebab bug B1 di `ADJUSTMENT.md` |
| Deployment ke Vercel | Belum | awal | Rencana untuk frontend |
| Hosting backend (Railway, Render, Fly) | Belum | awal | Lihat keputusan A2 di `ADJUSTMENT.md` |
| Membaca log dan menelusuri penyebab error | Belum | awal | Keterampilan paling sering dipakai saat sesuatu gagal |
| Image harus dibangun ulang setelah kode berubah | Dijelaskan | penjelasan 6 Sep | Container menjalankan salinan kode di dalam image, bukan berkas di folder proyek. Setiap ada revisi Alembic baru wajib `docker compose up -d --build backend`; tanpa itu container start dengan image yang tidak mengenali versi tercatat di database, lalu gagal |
| Dua berkas `.env` di proyek ini | Dasar | praktik 6 Sep | `.env` root dibaca Docker Compose dan diteruskan ke container; `backend/.env` hanya dipakai saat backend dijalankan tanpa Docker. `backend/.dockerignore` sengaja melarang `.env` masuk image supaya kunci rahasia tidak ikut terbakar ke dalamnya |

## G. Data dan Mesin Skor

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| NumPy dan pandas | Belum | awal | — |
| Normalisasi variabel ke rentang 0–1 | Belum | awal | Langkah pertama seluruh mesin skor |
| Entropy Weighting | Belum | awal | Bobot dari variabilitas data |
| AHP dan rasio konsistensi (CR) | Belum | awal | Bobot dari penilaian ahli |
| TOPSIS | Belum | awal | Metode perankingan akhir |
| Bootstrap dan metode BCa | Belum | awal | Interval keyakinan tanpa asumsi distribusi normal |
| Shrinkage estimator | Belum | awal | Penanganan zona bersampel kecil |
| Indeks komposit (SEPI, GapScore, TSI, CEI) | Belum | awal | Rumusnya ada di `LAYER.md` bagian 5 |

## H. AI, NLP, dan LLM

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| Memakai LLM sebagai alat bantu koding | Dasar | awal | Sudah terbiasa |
| Prompt dan konteks yang dikirim ke model | Belum | awal | `backend/app/services/station_context.py` |
| Topic modeling / LDA | Belum | awal | Untuk arketipe stasiun |
| Named Entity Recognition (NER) | Belum | awal | Untuk kandidat sponsor |
| Analisis sentimen | Belum | awal | Untuk keluhan fasilitas |
| Pre-computation vs komputasi saat permintaan masuk | Belum | awal | Aturan mengikat di PRD |

## I. Alat dan Alur Kerja

| Konsep | Status | Dari mana | Catatan |
|---|---|---|---|
| Git dasar (commit, branch) | Dasar | awal | — |
| Terminal dan perintah dasar | Dasar | awal | — |
| Markdown | Dasar | awal | — |
| Membaca pesan error dan menerjemahkannya jadi tindakan | Belum | awal | — |
| Menguji endpoint API dari terminal | Belum | awal | — |

---

## Riwayat Kuis

Ditulis lengkap supaya bisa dibaca ulang sendiri tanpa membuka percakapan aslinya: pertanyaan
utuh, semua pilihannya, jawaban yang benar, dan intinya.

---

### Kuis #1 — 6 Sep 2026 — kategori E (GIS)

**Pertanyaan.** Isochrone 5, 10, dan 15 menit untuk satu stasiun bentuknya bersarang — yang
5 menit ada di dalam yang 10, dan yang 10 ada di dalam yang 15. Kita ingin menghitung berapa
titik minat (POI) di tiap zona, dan melakukannya dengan cara paling lurus: hitung semua titik
yang berada di dalam tiap poligon. Apa yang terjadi?

- **A.** Titik di zona 5 menit ikut terhitung lagi di zona 10 dan 15, jadi satu titik dihitung sampai tiga kali
- **B.** Titik di zona 15 menit tidak terhitung sama sekali karena tertutup poligon yang lebih kecil
- **C.** Hasilnya sudah benar, karena PostGIS otomatis membuang perhitungan ganda
- **D.** PostGIS menolak poligon yang saling bersarang

**Jawaban benar: A.**

**Jawaban Villyan:** tidak dijawab, minta penjelasan lebih dulu.

**Inti jawabannya.** Kalau sebuah tempat bisa dicapai dalam 3 menit, otomatis ia juga bisa
dicapai dalam 10 dan 15 menit — jadi ketiga poligon bukan wilayah bersebelahan, melainkan
lapisan bersarang seperti bawang. Tiga titik A (dalam 5 menit), B (dalam 10), C (dalam 15)
akan tercatat 1 + 2 + 3 = 6 kali. Akibat terburuknya bukan sekadar angka membengkak, tetapi
membengkaknya tidak merata: stasiun berisochrone lebar kena penggelembungan lebih besar,
sehingga peringkat antar-stasiun ikut salah. Perbaikannya memotong tiap cincin dengan
`ST_Difference` sehingga tidak tumpang tindih.

**Dampak ke bank.** Tidak naik ke `Dasar` karena belum dijawab sendiri, tetapi konsepnya masuk
kategori E dengan status `Dijelaskan`. Boleh diuji ulang di sesi berikutnya.

---

### Kuis #2 — 6 Sep 2026 — kategori E (GIS)

**Pertanyaan.** Untuk menjawab "berapa banyak titik minat yang bisa dicapai pejalan kaki dari
Stasiun Manggarai dalam 15 menit?", bentuk mana yang benar dipakai?

- **A.** Cincin eksklusif — poligon 15 menit dikurangi poligon 10 menit
- **B.** Poligon 15 menit apa adanya, yang memang sudah mencakup area 5 dan 10 menit
- **C.** Jumlahkan hasil hitungan ketiga poligon
- **D.** Poligon 5 menit saja, karena itu yang paling akurat

**Jawaban benar: B.**

**Jawaban Villyan:** C — kurang tepat.

**Inti jawabannya.** Pertanyaannya bersifat kumulatif ("dalam 15 menit"), dan poligon 15 menit
**sudah** memuat seluruh area 5 dan 10 menit. Jadi cukup hitung titik di dalam poligon 15 menit
apa adanya — tidak perlu diproses lagi. Pilihan C justru mengulang persis kesalahan pada Kuis #1:
menjumlahkan hitungan ketiga poligon membuat titik yang dekat stasiun terhitung tiga kali,
sehingga hasilnya lebih besar daripada jumlah titik yang sebenarnya ada. Pilihan A menjawab
pertanyaan yang berbeda, yaitu "titik yang jaraknya antara 10 sampai 15 menit", bukan "seluruh
titik dalam 15 menit".

Cara mengingatnya: **`ST_Difference` dipakai kalau zona-zonanya mau dibandingkan satu sama lain;
poligon apa adanya dipakai kalau yang ditanya cakupan totalnya.** Kalau salah pilih, jawabannya
bukan sekadar meleset — ia menjawab pertanyaan lain.

**Dampak ke bank.** Tidak naik ke `Dasar`. Konsep "cincin eksklusif vs kumulatif" tetap
`Dijelaskan`, dan pantas diuji ulang di sesi berikutnya karena sudah dua kali disinggung.

---

### Kuis #3 — 6 Sep 2026 — kategori D (Database dan ORM)

**Pertanyaan.** SQLAlchemy hanya tahu sebuah tabel ada kalau berkas modelnya pernah diimpor.
Kalau ada berkas model baru, misalnya `tenants.py`, yang lupa didaftarkan di
`app/models/__init__.py` — apa yang terjadi?

- **A.** Tabelnya tetap dibuat, hanya prosesnya lebih lambat karena SQLAlchemy harus memindai foldernya
- **B.** Tabelnya tidak akan dibuat dan tidak akan muncul di autogenerate Alembic, tanpa ada pesan error sama sekali
- **C.** Aplikasi menolak jalan dan menampilkan error "model tidak terdaftar"
- **D.** Alembic otomatis memindai seluruh isi folder `models/`, jadi tidak masalah

**Jawaban benar: B.**

**Jawaban Villyan: B — benar.**

**Inti jawabannya.** SQLAlchemy tidak memindai folder. Ia hanya mengenal kelas yang benar-benar
dieksekusi Python, dan sebuah kelas baru dieksekusi kalau berkasnya diimpor. Kalau tidak
diimpor, kelasnya tidak pernah terdaftar di `Base.metadata`, sehingga `create_all` melewatinya
dan Alembic menganggapnya tidak ada. Bahayanya justru karena **tidak ada error**: tabelnya
hilang diam-diam, dan baru ketahuan jauh di kemudian hari saat ada kueri yang gagal.

**Dampak ke bank.** Konsep "model harus diimpor supaya terdaftar di ORM" masuk kategori D
dengan status `Dasar`.

---

### Kuis #4 — 6 Sep 2026 — kategori B (Backend dan API)

**Pertanyaan.** Misalkan kunci Groq hanya ditempelkan ke setelan lama (`GEMINI_API_KEY`), tanpa
mengubah apa pun yang lain. Chatnya gagal. Kenapa?

- **A.** Karena format kunci Groq berbeda dari format kunci Google, jadi SDK-nya menolak sebelum mengirim apa pun
- **B.** Karena kuncinya tetap dikirim ke alamat server Google, dan Google menolak kunci yang bukan terbitannya
- **C.** Karena SDK OpenAI hanya bisa dipakai untuk memanggil OpenAI, bukan penyedia lain
- **D.** Karena `gemini-3.5-flash` tidak ada di Groq — hanya itu satu-satunya masalahnya

**Jawaban benar: B.**

**Jawaban Villyan:** A — kurang tepat.

**Inti jawabannya.** SDK tidak memeriksa bentuk kunci sama sekali; ia hanya membungkus kunci itu
ke dalam permintaan HTTP lalu mengirimkannya ke alamat yang tertulis di `base_url`. Selama
`base_url` masih menunjuk `generativelanguage.googleapis.com`, kunci Groq mendarat di server
Google, dan Google menolaknya karena bukan kunci terbitannya. Kegagalannya terjadi **di sisi
server penyedia**, bukan di komputer kita.

Pilihan D benar sebagian tetapi bukan penyebab utamanya: kalaupun id modelnya diperbaiki,
selama alamatnya masih ke Google, kuncinya tetap ditolak lebih dulu. Urutannya penting — kunci
diperiksa sebelum nama model.

Pelajaran umumnya: **satu SDK bisa melayani banyak penyedia karena tujuan panggilan ditentukan
base URL, bukan oleh SDK-nya.** Kunci, alamat, dan nama model adalah tiga hal terpisah yang
harus cocok bertiga.

**Dampak ke bank.** Tidak naik ke `Dasar`. Konsep "base URL sebagai penentu tujuan panggilan
API" masuk kategori B dengan status `Dijelaskan`.

---

## Kuis terbuka — menunggu jawaban sesi berikutnya

Empat kuis di bawah sudah diajukan tetapi belum dijawab. Ditutup di sesi 6 Sep atas permintaan
Villyan, untuk dijawab di sesi berikutnya. Jawaban benar menaikkan status konsepnya ke `Dasar`.

### Kuis #5 — kategori D — debug

Besok Anda menambah satu kolom ke model `Poi`, lalu menjalankan `docker compose up` tanpa
membuat revisi Alembic baru. Apa yang terjadi?

- **A.** Kolomnya otomatis ditambahkan, karena Alembic membandingkan model dengan database setiap kali start
- **B.** Container gagal start dengan error "skema tidak cocok"
- **C.** Container start normal, tabelnya tetap tanpa kolom baru, dan errornya baru muncul saat ada kode yang memakai kolom itu
- **D.** Seluruh tabel `poi` dibuat ulang dengan struktur baru, isinya hilang

### Kuis #6 — kategori D — konsep

Setiap berkas revisi Alembic punya dua fungsi: `upgrade()` dan `downgrade()`. Untuk apa
`downgrade()`?

- **A.** Menurunkan versi PostgreSQL kalau versinya terlalu baru
- **B.** Membatalkan perubahan revisi itu, mengembalikan skema ke bentuk sebelumnya
- **C.** Membuat cadangan data sebelum migrasi dijalankan
- **D.** Menjalankan migrasi dalam mode uji tanpa benar-benar mengubah database

### Kuis #7 — kategori E — konsep

Kolom geometri diberi indeks **GiST**, bukan indeks biasa (B-tree) seperti kolom `category` di
tabel `poi`. Kenapa harus jenis yang berbeda?

- **A.** Karena kolom geometri ukurannya besar, dan GiST menyimpannya lebih hemat
- **B.** Karena B-tree bekerja dengan mengurutkan nilai dari kecil ke besar, sementara "poligon ini lebih kecil dari poligon itu" tidak punya arti — yang ditanyakan adalah bersinggungan, memuat, atau berdekatan
- **C.** Karena PostGIS tidak mendukung B-tree sama sekali
- **D.** Karena GiST lebih cepat untuk semua jenis kolom, jadi sebaiknya dipakai di mana-mana

### Kuis #8 — kategori D — debug

Tabel `poi` punya kolom `osm_tags` yang tidak boleh kosong, dengan `default=dict` di model.
Besok Anda mengimpor 5.000 titik OSM memakai perintah `COPY` PostgreSQL langsung, tanpa lewat
kode Python, dan tidak mengisi kolom `osm_tags`. Apa yang terjadi — **seandainya perbaikan
`server_default` belum dilakukan**?

- **A.** Semua 5.000 baris masuk dengan `osm_tags` berisi `{}`, karena SQLAlchemy sudah mendaftarkan nilai bawaannya ke database saat tabel dibuat
- **B.** Semua 5.000 baris ditolak, karena nilai bawaan `default=dict` hanya diterapkan saat data masuk lewat ORM
- **C.** Baris masuk dengan `osm_tags` berisi NULL, dan aturan NOT NULL diabaikan untuk `COPY`
- **D.** `COPY` otomatis memanggil kode Python untuk mengisi kolom yang kosong
