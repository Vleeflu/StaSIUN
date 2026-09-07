# StaSIUN

Aplikasi peta stasiun di DKI Jakarta. Backend FastAPI + PostGIS menyajikan data
stasiun sebagai GeoJSON, frontend Next.js menampilkannya di atas basemap MAPID
dengan MapLibre GL, lengkap dengan pencarian stasiun.

## Teknologi

| Bagian    | Teknologi                                          |
| --------- | -------------------------------------------------- |
| Database  | PostgreSQL 17 + PostGIS 3.5 (Docker)                |
| Backend   | FastAPI, SQLAlchemy 2, GeoAlchemy2, psycopg 3       |
| Frontend  | Next.js 16 (App Router), React 19, Tailwind CSS 4   |
| Peta      | MapLibre GL JS 5, basemap MAPID                     |

## Prasyarat

- Docker Desktop
- Python 3.10+
- Node.js 20+
- API key MAPID (daftar di https://maps.mapid.io)

## Menjalankan dengan Docker (semua sekaligus)

Cara tercepat: seluruh stack — database, backend, dan frontend — dijalankan
lewat satu perintah.

```bash
cp example.env .env      # Windows: copy example.env .env
docker compose up --build
```

Isi `NEXT_PUBLIC_MAPID_KEY` di `.env` dengan API key MAPID supaya basemap tampil.
Nilai ini disematkan ke frontend saat build, jadi setelah mengubahnya jalankan
`docker compose up --build` lagi.

Setelah semua container hidup:

- Frontend: http://localhost:3000
- Backend + dokumentasi: http://localhost:8000/docs
- Database PostGIS: `localhost:5432`

Saat pertama kali start, container backend menunggu database siap, membuat tabel,
lalu mengisi data stasiun dari berkas GeoJSON bawaan di `backend/data/`
(tanpa perlu kredensial MAPID). Untuk mengambil data langsung dari Geoserver
MAPID, set `SEED_SOURCE=mapid` pada service `backend` dan isi `MAPID_API_KEY`
serta `MAPID_PROJECT_ID` di `.env`. Untuk melewati seeding, set `SEED_ON_START=0`.

Menghentikan: `docker compose down` (tambah `-v` untuk ikut menghapus data
di volume `pgdata`).

## Menjalankan manual (pengembangan)

Tiga proses harus hidup bersamaan, masing-masing di terminal terpisah.

### 1. Database

```bash
docker compose up -d db
```

Container `stasiun-db` akan menyediakan PostGIS di `localhost:5432`. Datanya
tersimpan di volume `pgdata` sehingga tetap ada meski container di-restart.

Pastikan ekstensi PostGIS aktif:

```bash
docker compose exec db psql -U stasiun -d stasiun -c "SELECT postgis_version();"
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
copy example.env .env          # Linux/macOS: cp example.env .env
```

Buat tabelnya:

```bash
python -c "import app.models.station; from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

Lalu isi datanya. Ada **dua cara**, pilih salah satu — keduanya mengosongkan
tabel lebih dulu, jadi aman dijalankan berulang kali.

**Cara 1 — dari berkas GeoJSON lokal (disarankan).** Tidak butuh kredensial
apa pun dan datanya paling mutakhir.

```bash
python -m scripts.seed_stations
```

Sumbernya `backend/data/railway_station_DKI.geojson`, ekspor OpenStreetMap
stasiun kereta di DKI Jakarta. Hasilnya `78 stations stored (77 served, 1 not served)`.

**Cara 2 — tarik langsung dari Geoserver MAPID.**

```bash
python -m scripts.ingest_layers
```

Layer yang ditarik didaftar di `backend/data/layers.yml`, dan butuh
`MAPID_API_KEY` serta `MAPID_PROJECT_ID` yang sah di `backend/.env`. Hasilnya
`48 stations stored` dari sumber yang lebih tua, jadi jumlah dan koordinatnya
sedikit berbeda dengan Cara 1.

Kedua jalur memakai modul yang sama, `app/services/station_import.py`, sehingga
penyaringan jaringan, penempelan lin, dan penandaan stasiun tak terlayani
berlaku identik apa pun sumbernya.


Jalankan servernya:

```bash
uvicorn app.main:app --reload --port 8000
```

Dokumentasi interaktif tersedia di http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
copy example.env.local .env.local   # Linux/macOS: cp example.env.local .env.local
```

Isi `NEXT_PUBLIC_MAPID_KEY` di `.env.local` dengan API key MAPID milikmu, lalu:

```bash
npm run dev
```

Buka http://localhost:3000

## Variabel lingkungan

`backend/.env`

| Variabel       | Keterangan                        |
| -------------- | --------------------------------- |
| `PROJECT_NAME` | Nama aplikasi di judul OpenAPI     |
| `DATABASE_URL` | Koneksi PostGIS (lihat contohnya)  |

`frontend/.env.local`

| Variabel                | Keterangan                            |
| ----------------------- | ------------------------------------- |
| `NEXT_PUBLIC_API_URL`   | Alamat backend, mis. `localhost:8000` |
| `NEXT_PUBLIC_MAPID_KEY` | API key basemap MAPID                 |

## Endpoint

| Method | Path                  | Keterangan                                       |
| ------ | --------------------- | ------------------------------------------------ |
| GET    | `/api/health`         | Status aplikasi dan konfigurasi database         |
| GET    | `/api/stations`       | Semua stasiun sebagai GeoJSON `FeatureCollection` |
| GET    | `/api/stations?type=` | Saring per jaringan, mis. `KAI Commuter`         |

## Struktur

```
stasiun-app/
├─ docker-compose.yml       # PostGIS
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/        # endpoint HTTP
│  │  ├─ core/              # konfigurasi & koneksi database
│  │  ├─ models/            # model SQLAlchemy
│  │  ├─ schemas/           # skema Pydantic
│  │  └─ services/          # logika bisnis
│  ├─ data/
│  │  ├─ railway_station_DKI.geojson   # sumber Cara 1 (OpenStreetMap)
│  │  └─ layers.yml                    # katalog layer untuk Cara 2 (MAPID)
│  └─ scripts/
│     ├─ seed_stations.py              # Cara 1
│     └─ ingest_layers.py              # Cara 2
└─ frontend/src/
   ├─ app/                  # halaman App Router
   ├─ components/           # Map, StationSearch
   ├─ hooks/                # useStations
   ├─ lib/                  # helper API & konstanta lin
   └─ types/                # tipe bersama
```

## Catatan data

Unit analisisnya stasiun KRL di DKI Jakarta, tetapi **seluruh moda rel ikut
disimpan**: 42 KAI Commuter, 13 MRT Jakarta, 12 LRT Jabodebek, 6 LRT Jakarta,
4 KAI, dan 1 Whoosh — total 78 titik, 77 dilayani.

Titik non-KRL tidak ikut sekadar untuk melengkapi peta. PRD menjadikan
**konektivitas antarmoda** salah satu indikator Aksesibilitas (variabel A), jadi
keberadaan MRT, LRT, atau kereta cepat di dekat sebuah stasiun KRL adalah data
yang dipakai perhitungan, bukan hiasan.

Roster lin hanya ditempelkan ke jaringan KAI, lewat penjagaan `KAI_NETWORKS` di
`backend/app/services/station_import.py`. Tanpa itu stasiun senama dari moda lain
ikut kebagian lin KRL — Cawang LRT sempat kena, padahal letaknya 1,4 km dari
Cawang KRL. Nilai `KAI` di samping `KAI Commuter` juga penting: Jakarta Kota,
Jatinegara, dan Pasar Senen ditandai `KAI` di OpenStreetMap padahal ketiganya
stasiun KRL utama. Jakarta Gudang dikecualikan karena emplasemen barang tanpa
layanan penumpang.

Keanggotaan lin tidak berasal dari berkas sumber, melainkan dari roster resmi
peta rute KAI Commuter yang ditanam di `app/services/station_import.py`. Enam
lin dipakai beserta kodenya: `B` Bogor, `C` Lingkar Cikarang, `R` Rangkasbitung,
`T` Tangerang, `TP` Tanjung Priok, dan `A` KA Bandara. Stasiun yang dilewati
lebih dari satu lin ditandai sebagai interchange dan digambar sebagai lingkaran
berjuring banyak warna di peta.

Kolom `served` menandai stasiun yang hanya dilewati KRL tanpa berhenti. Saat ini
hanya **Gambir** yang bernilai `false` — stasiun besar untuk kereta antarkota,
tetapi KRL melintas tanpa berhenti. Titiknya tetap digambar di peta dengan
transparansi lebih rendah, karena footfall antarkotanya tetap relevan untuk
analisis potensi komersial.

Cakupannya terbatas DKI Jakarta, sesuai lingkup studi kasus awal. Stasiun di
Bogor, Depok, Bekasi, Tangerang, dan koridor Rangkasbitung belum termasuk.
