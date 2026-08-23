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

## Menjalankan

Tiga proses harus hidup bersamaan, masing-masing di terminal terpisah.

### 1. Database

```bash
docker compose up -d
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

Buat tabel lalu isi datanya:

```bash
python -c "import app.models.station; from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"
python -m scripts.ingest_layers
```

Skrip ingest menarik data langsung dari Geoserver MAPID sesuai katalog di
`backend/data/layers.yml`. Sifatnya idempoten — aman dijalankan berulang kali.
Hasilnya `74 stations stored`.

Perlu `MAPID_API_KEY` dan `MAPID_PROJECT_ID` yang sah di `backend/.env`.

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
| GET    | `/api/stations?type=` | Saring per jenis layanan, mis. `KERETA API`      |

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
│  ├─ data/layers.yml       # katalog layer MAPID
│  └─ scripts/ingest_layers.py
└─ frontend/src/
   ├─ app/                  # halaman App Router
   ├─ components/           # Map, StationSearch
   ├─ hooks/                # useStations
   ├─ lib/                  # helper pemanggilan API
   └─ types/                # tipe bersama
```

## Catatan data

Data ditarik langsung dari Geoserver MAPID lewat endpoint `get_layer`, satu
layer per kota administrasi DKI Jakarta, sesuai katalog di
`backend/data/layers.yml`.

Berkas mentahnya memuat **121 fitur**, tetapi hanya ada **74 stasiun fisik**.
Satu stasiun yang melayani beberapa moda tercatat sebagai beberapa fitur pada
koordinat yang sama, dibedakan oleh atribut `TIPE_3`. Skrip seed
menggabungkannya menjadi satu baris dengan kolom `types` berupa array.

Deduplikasi memakai **koordinat**, bukan nama. Stasiun Cawang membuktikan
pentingnya hal ini: ada dua stasiun fisik berbeda dengan nama sama, satu di
Tebet (Commuter dan Kereta Api) dan satu lagi LRT di Kramatjati berjarak sekitar
1,5 km. Deduplikasi berbasis nama akan menggabungkan keduanya secara keliru.

**Peringatan kualitas data.** Subset LRT bermasalah pada sumbernya: beberapa
baris memakai nama stasiun di Kota Bekasi (`STASIUN BEKASI BARAT`,
`JATI BENING BARU`, `CIKUNIR 1`, `CIKUNIR 2`, `JATI MULYA`) padahal koordinat
dan atribut administratifnya berada di Jakarta. Subset MRT, Commuter, dan
Kereta Api sudah diperiksa dan konsisten. Verifikasi ulang data LRT sebelum
menampilkannya ke pengguna.


## Data Eksternal

1. ESRI Arcgis - data point stasiun https://sigcfe.maps.arcgis.com/home/item.html?id=ed2de5332c8240268bb27c2e1500b141&dataTabView=fields#data
