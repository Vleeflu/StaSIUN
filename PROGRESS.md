# Papan Kerja — StaSIUN

Diperbarui **saat itu juga** setiap kali satu pekerjaan selesai, muncul blocker baru, blocker
lama terbuka, atau rencana berubah. Bukan di akhir sesi.

Rencana lengkap beserta alasannya ada di `ADJUSTMENT.md` bagian 7. Berkas ini versi papannya:
apa yang dikerjakan, statusnya apa, dan apa yang menahannya.

**Status terakhir diperbarui:** 6 Sep 2026 (sesi ditutup)
**Mulai sesi berikutnya dari:** F2-1 (importer POI OSM lewat Overpass) — tidak terblokir.
Empat kuis terbuka menunggu jawaban di `KNOWLEDGE.md` bagian bawah.
**Tenggat:** 13 Sep 2026 (akhir M9 per kalender PRD) — sisa 7 hari

## Arti status

| Status | Artinya |
|---|---|
| `Selesai` | Sudah dikerjakan **dan** terverifikasi berjalan |
| `Ditulis` | Kodenya ada, tetapi belum pernah dijalankan atau diuji |
| `Jalan` | Sedang dikerjakan |
| `Terblokir` | Tidak bisa maju sampai sesuatu di luar kode tersedia |
| `Belum` | Belum disentuh |

---

## 1. Papan kerja

### Fase 0 — Membuka blocker lokal

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F0-1 | Nyalakan Docker Desktop, pasang dependensi Python backend | Selesai | — | ADJUSTMENT 7.1 |
| F0-2 | `docker compose up --build` naik bersih setelah MinIO dicabut | Selesai | — | ADJUSTMENT 7.8 |
| F0-3 | Verifikasi asisten chat hidup di jalur Docker (B1) | Selesai | — | ADJUSTMENT 7.8 |
| F0-4 | Verifikasi indeks `idx_stations_location` ada di database (B3) | Selesai | — | ADJUSTMENT 7.8 |
| F0-5 | Revisi Alembic pertama + tukar `create_all` jadi `alembic upgrade head` (B5) | Selesai | — | ADJUSTMENT 7.8 |
| F0-6 | Pastikan id `LLM_MODEL` memang tersedia di Groq (B7) | Selesai | — | ADJUSTMENT 7.7 |

### Fase 1 — Skema analitik

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F1-1a | Mixin (`TimestampMixin`, `SourceMixin`, `ScoreMetadataMixin`) + tabel `isochrones`, `poi`, `passenger_volume`, `area_profile`, `price_references` | Selesai | — | LAYER 1 |
| F1-1b | Tabel rantai Activity (`activity_raw`, `activity_points`, `activity_extractions`, `crowd_ratings`) dan objek stasiun (`station_zones`, `tenants`, `tenant_clusters`, `ad_spots`, `facility_issues`) | Selesai | — | LAYER 1 |
| F1-1c | Perbaikan penyaring indeks spasial di `alembic/env.py` — versi lama hanya mengenali nama berakhiran `_location`, sehingga `idx_isochrones_geom` dan `idx_isochrones_origin_point` akan lolos dan membuat migrasi gagal | Selesai | — | ADJUSTMENT 6 |
| F1-2 | Revisi Alembic untuk skema baru — tiga revisi berantai: `d4a7fc2da6ce` (6 tabel), `8e28c27f6231` (9 tabel), `0883f21f1e5d` (nilai bawaan sisi database) | Selesai | — | ADJUSTMENT 7.8 |
| F1-3 | Materialized view mesin skor sebagai revisi SQL terpisah | Belum | F3 selesai dulu | LAYER 1 |

### Fase 2 — Jalur data

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F2-1 | Importer POI OSM lewat Overpass (N10) | Belum | — **tidak terblokir, kerjakan lebih dulu** | ADJUSTMENT 7.2 |
| F2-2 | Tabel + CSV `passenger_volume` berkolom sumber dan tanggal akses (N4) | Belum | Riset data sekunder | LAYER 1 |
| F2-3 | Tabel + CSV `area_profile` (N5) | Belum | Riset data eksternal | LAYER 1 |
| F2-4 | Importer isochrone dari API GeoMAPID + Permeability Index | Belum | `layer_id` layer isochrone; `MAPID_API_KEY` dan `MAPID_PROJECT_ID` di `backend/.env` | ADJUSTMENT 7.6 |
| F2-5 | Importer Activity: adapter sumber + `activity_raw` + gating | Belum | N1 — ekspor Activity belum ada | ADJUSTMENT 7.3 |
| F2-6 | Tambahkan pustaka analitik ke `requirements.txt` (B6) | Belum | — | ADJUSTMENT 2.4 |

### Fase 3 — Mesin skor

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F3-1 | Normalisasi variabel ke 0–1, termasuk ordinal narasumber | Belum | — (numpy murni, bisa diuji dengan data sintetis) | LAYER 5 |
| F3-2 | Entropy Weighting | Belum | — | LAYER 5 |
| F3-3 | AHP + pemeriksaan CR < 0,10 | Belum | N9 — matriks perbandingan berpasangan dari tim | LAYER 5 |
| F3-4 | Penggabungan bobot dan TOPSIS | Belum | — | LAYER 5 |
| F3-5 | Klasifikasi SEPI tiga rentang + kalimat keputusan bisnis | Belum | — | LAYER 5 |
| F3-6 | Bootstrap BCa | Belum | — | LAYER 5 |
| F3-7 | Shrinkage estimator | Belum | Kelompok pembanding butuh arketipe LDA (F5-1) | LAYER 5 |

### Fase 4–5 — Isochrone dan SEPI sampai tampil di peta

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F4-1 | `GET /api/stations/{id}/isochrones` | Belum | F2-4 | ADJUSTMENT 3.4 |
| F4-2 | Layer poligon isochrone di peta | Belum | F4-1 | LAYER 6 |
| F4-3 | Toggle ketiga: poligon zona indoor (C9) | Belum | — (toggle bisa dulu, isinya menyusul) | ADJUSTMENT 2.3 |
| F5-1 | Lapis 1 NLP: LDA, NER, Sentiment + validasi silang spasial + pembatas 15% | Belum | N1, N12 (pilihan pustaka NLP) | LAYER 3 |
| F5-2 | `mv_sepi_scores` + `GET /api/stations/{id}/sepi` | Belum | F3, F1-3 | ADJUSTMENT 3.4 |
| F5-3 | Pewarnaan titik stasiun berdasarkan SEPI + heatmap | Belum | F5-2 | LAYER 6 |
| F5-4 | Komponen metadata keyakinan yang dipakai ulang di semua panel | Belum | F5-2 | LAYER 9 |
| F5-5 | Isi tab Ikhtisar dengan angka asli, ganti baris footfall/dwell-time (C8) | Belum | F5-2 | ADJUSTMENT 2.3 |

### Fase 6 — Tiga fitur utama dan penyelesaian

| ID | Pekerjaan | Status | Blocker | Acuan |
|---|---|---|---|---|
| F6-1 | Ad-Space Opportunity: zona indoor, `ad_spots`, profil paparan, estimasi harga | Belum | N3 (zona indoor), N7 (benchmark OOH) | LAYER 7 |
| F6-2 | Facility Sponsorship Trigger | Belum | F5-1 | LAYER 7 |
| F6-3 | Tenant Valuation: GapScore + TSI + simulator what-if | Belum | N6 (riset harga) | LAYER 7 |
| F6-4 | Naming Rights: CEI + kandidat sponsor | Belum | N8 (transaksi pembanding) | LAYER 7 |
| F6-5 | AI Router: tulis ulang `PROJECT_BRIEF` + suntik skor terhitung (C6) | Belum | F5-2 | ADJUSTMENT 2.3 |
| F6-6 | Ekspor ringkasan per stasiun | Belum | F5-2 | LAYER 9 |
| F6-7 | Uji tampilan mobile | Belum | — | LAYER 6 |
| F6-8 | Deploy: frontend Vercel, database Supabase, backend host terpisah (A2) | Belum | N11 (kredensial Supabase) | ADJUSTMENT 2.5 |

---

## 2. Blocker aktif

| # | Yang dibutuhkan | Menahan | Siapa | Status |
|---|---|---|---|---|
| L1 | ~~Docker Desktop + dependensi Python~~ | — | Villyan | **Tertutup 6 Sep** |
| L2 | ~~`.env` berisi kredensial~~ | — | Villyan | **Tertutup 6 Sep.** `backend/.env` diisi Villyan; `.env` root dibuat menyalin nilainya, karena itu yang dibaca Docker Compose |
| N2 | **PALING MENDESAK.** `layer_id` layer isochrone GeoMAPID + daftar stasiun yang sudah di-generate. Wajib **tiga durasi** (5, 10, 15 menit) per stasiun; durasi harus bisa dibedakan, lewat kolom atribut atau lewat nama layer. Catat juga kecepatan berjalan yang dipakai saat generate — dibutuhkan Permeability Index | Variabel A, gate spasial Activity, satu acceptance criteria penuh | Villyan | Sebagian terjawab — jalur API sudah pasti, `layer_id` belum diberikan, jumlah durasi per layer belum diperiksa |
| N1 | Ekspor data Activity hasil survey tim + akses entri tim lain | Variabel E dan C, seluruh lapis 1 NLP | Villyan / tim | Terbuka |
| N9 | Matriks perbandingan berpasangan AHP (CR < 0,10) | F3-3, bobot SEPI | Tim | Terbuka |
| N11 | Kredensial Supabase produksi | F6-8, migrasi database | Villyan | Terbuka |
| N3 | Zona indoor stasiun dalam bentuk terdigitasi | F6-1, klaster tenant | Tim | Terbuka |
| N4 | Data volume penumpang stasiun KRL DKI | F2-2, variabel T | Riset | Terbuka |
| N5 | Data profil kawasan | F2-3, variabel U | Riset | Terbuka |
| N6 | Riset harga menu + listing sewa komersial | F6-3, variabel E dan R | Riset | Terbuka |
| N7 | Benchmark tarif per seribu paparan industri OOH | F6-1 | Riset | Terbuka |
| N8 | Transaksi pembanding naming rights di Indonesia | F6-4 | Riset | Terbuka |
| N12 | Pilihan pustaka NLP Bahasa Indonesia terlatih | F5-1 | Keputusan bersama | Rekomendasi sudah ada di ADJUSTMENT 7.4, belum diputuskan |

---

## 3. Utang teknis yang masih tercatat

Bukan blocker, tetapi harus ditutup sebelum presentasi.

| # | Isi | Status | Catatan |
|---|---|---|---|
| C6 | `PROJECT_BRIEF` di `station_context.py` masih memakai peta dataset versi proposal | Belum | — |
| C8 | Baris footfall dan dwell-time di `StationPanel.tsx` — ditolak eksplisit oleh PRD | Belum | — |
| C9 | Toggle ketiga (poligon zona indoor) belum ada di `ControlPanel.tsx` | Belum | — |
| C10 | Teks pembuka `ChatPanel.tsx` menyatakan skor belum dihitung secara permanen | Belum | — |
| C11 | Angka stasiun di `README.md` salah — yang benar 78 tersimpan, 1 tidak dilayani | Selesai | Diperbaiki dengan angka dari keluaran API sungguhan |
| C12 | `README.md` menyebut MRT/LRT/Whoosh tidak diikutkan, padahal sudah diikutkan | Selesai | Ditulis ulang, sekalian menjelaskan titik non-KRL dipakai sebagai konektivitas antarmoda (variabel A) |
| B6 | Belum ada pustaka analitik di `requirements.txt` | Belum | — |
| B8 | `/api/stations` mengirim seluruh FeatureCollection tanpa tiling | Belum, aman sampai poligon masuk | — |
| B9 | `UNSERVED = {"GAMBIR"}` ditanam di kode | Dicatat sebagai utang, cukup untuk sekarang | — |

---

## 4. Riwayat milestone

| Tanggal | Yang selesai |
|---|---|
| 3 Sep 2026 | Paket Hari 1: OCR dipensiunkan (C1–C5, C7), `GEMINI_API_KEY` diteruskan ke container (B1), MinIO dicabut (B2), indeks spasial dieksplisitkan (B3), konvensi proyeksi ganda di `core/geo.py` (B4), kerangka Alembic dipasang (B5), `LAYER.md` dan `OVERVIEW.md` ditulis ulang dari PRD (D1–D9) |
| 6 Sep 2026 | Rencana 7 hari disusun (ADJUSTMENT 7); desain pengambilan Activity berbasis gate wilayah, bukan kurasi manual (7.3); keputusan isochrone lewat API GeoMAPID, A4 terjawab (7.6); koreksi angka stasiun 79 menjadi 78; berkas alur kerja sesi dibuat (`session_initialization.md`, `session_termination.md`, `PROGRESS.md`, `KNOWLEDGE.md`) |
| 6 Sep 2026 | Fase 0 tuntas kecuali verifikasi jalur Docker: revisi Alembic pertama dibuat dan diterapkan, `create_all` diganti `alembic upgrade head`, indeks GiST terverifikasi ada, model Groq diperbaiki ke `openai/gpt-oss-120b` dan diuji dengan panggilan sungguhan, penyaring `include_object` diperbaiki supaya tidak menghapus 36 tabel PostGIS tiger |
| 6 Sep 2026 | Fase 1 tuntas: 15 tabel hidup di database, 11 indeks GiST. Dua lubang konfigurasi Alembic ditutup (`include_object` yang meloloskan 36 tabel PostGIS, dan `compare_server_default` yang mati sehingga perubahan nilai bawaan tidak pernah terdeteksi). Bug `default` sisi Python diperbaiki jadi `server_default` sisi database |
| 6 Sep 2026 | Fase 1 giliran pertama: mixin + 5 tabel (`isochrones`, `poi`, `passenger_volume`, `area_profile`, `price_references`), impornya terverifikasi; penyaring indeks spasial Alembic diperbaiki (F1-1c); penyedia LLM diganti Gemini ke Groq dan setelannya dibuat netral penyedia (ADJUSTMENT 7.7) |
