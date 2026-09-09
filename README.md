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

Lalu siapkan skemanya. Aman dijalankan berulang — tanpa argumen, cuma tabel
yang belum ada yang dibuat.

```bash
python -m scripts.init_db
```

Kalau bentuk tabelnya berubah (ada kolom baru di model), skrip ini berhenti dan
menyebutkan kolom mana yang ketinggalan. `--reset` menghapus lalu membuat ulang
ketiga tabel proyek; isinya bisa ditarik penuh lagi dari MAPID, jadi tidak ada
yang hilang permanen.

Lalu isi datanya dari Geoserver MAPID. Butuh `MAPID_API_KEY` dan
`MAPID_PROJECT_ID` yang sah di `backend/.env`.

```bash
python -m scripts.ingest_layers                    # stasiun, isochrone, POI
python -m scripts.ingest_layers stations           # satu bagian saja
python -m scripts.ingest_layers isochrones pois
```

Layer yang ditarik didaftar di `backend/data/layers.yml`. Stasiun dan isochrone
sudah terisi lengkap: 75 stasiun dan 228 poligon. Bagian `pois` sengaja
dikosongkan — id-nya diisi sendiri sambil layernya diunggah ke GEO MAPID.

Katalog POI-nya berpatokan Jakarta Pusat: `poi_categories` mendaftar kategori
baku beserta variabel SEPI yang disuapinya, lalu tiap wilayah mengisi id per
kategori yang sama. Kategori yang `layer_id`-nya masih `""` dilewati dengan
catatan, jadi katalognya boleh diisi bertahap tanpa bikin impor gagal.

Id dipatok satu per satu, tidak dicari otomatis, karena proyek GEO MAPID
menyimpan beberapa layer dengan nama yang sama persis dan sebagian di antaranya
salah. Dua penjagaan dipasang untuk itu:

- Tiap layer isochrone divalidasi sebelum dipakai — harus ada isinya, berprofil
  `foot`, dan `time_limit`-nya cocok dengan `minutes`. Kalau gagal, impornya
  berhenti dengan pesan, bukan dilewati diam-diam.
- Sebelum menarik apa pun, katalognya dicocokkan dengan daftar layer yang hidup.
  API MAPID tetap melayani layer yang sudah dibuang ke tempat sampah, jadi
  "bisa ditarik" bukan jaminan layernya masih ada.

Nama layer di GEO MAPID berpola tetap, jadi id-nya bisa dijodohkan sendiri ke
katalog — tidak perlu menyalin 75 id satu per satu:

```bash
python -m scripts.match_layers           # lihat dulu hasil jodohnya
python -m scripts.match_layers --write   # tulis ke data/layers.yml
```

Kalau satu kategori punya beberapa terbitan (misalnya halte edisi 2024 dan
2025), yang tahunnya paling baru yang dipakai. Untuk mencari id satuan tanpa
membuka dasbor — bawaannya cuma layer aktif yang ditampilkan:

```bash
python -m scripts.list_layers alfamart pusat   # saring per kata
python -m scripts.list_layers --all            # ikut yang di tempat sampah
```

Layer bertanda premium tidak muncul di daftar itu; id-nya harus disalin dari
dasbor.

**Alternatif tanpa kredensial** — isi tabel stasiun saja dari berkas lokal
`backend/data/railway_station_DKI.geojson`:

```bash
python -m scripts.seed_stations
```

Keduanya memakai modul yang sama, `app/services/station_import.py`, sehingga
penempelan lin dan penandaan stasiun tak terlayani berlaku identik apa pun
sumbernya. Bedanya berkas lokal tidak punya isochrone maupun POI.


Terakhir, hitung skornya:

```bash
python -m scripts.compute_sepi              # pita 10 menit
python -m scripts.compute_sepi --minutes 15
python -m scripts.compute_sepi --dry-run    # tampilkan saja, jangan simpan
```

Alurnya mengikuti proposal: matriks keputusan disusun dari isi tiap isochrone,
bobotnya entropy dipadu AHP, peringkatnya lewat TOPSIS. Perbandingan
berpasangan AHP ada di `backend/data/ahp.yml` — **angkanya masih sementara dan
harus diganti hasil kesepakatan tim.** Consistency ratio diperiksa tiap kali
dijalankan; kalau mencapai 0,10 skoringnya berhenti.

Skornya lalu ikut menempel di `/api/stations` sebagai `sepi` dan `sepi_rank`,
dengan rinciannya di `/api/stations/{id}/score`.

Lalu Tenant Survival Index, yang mengambil pengali konektivitasnya dari skor
SEPI — jadi jalankan setelahnya:

```bash
python -m scripts.compute_tsi              # pita 10 menit
python -m scripts.compute_tsi --minutes 5
```

TSI membandingkan calon pelanggan yang bisa berjalan kaki ke sebuah stasiun
dengan pesaing sejenis yang sudah ada di sana. Calon pelanggan dihitung dari
titik variabel E dan U saja; titik komersial sengaja tidak ikut, supaya daerah
yang sudah padat warung tidak tercatat butuh lebih banyak warung. Hasilnya
dibentangkan ke 0–100 **per kategori**, jadi peringkatnya berarti "stasiun ini
urutan ke berapa untuk usaha jenis itu" — bukan perbandingan antar kategori.

Lima kategori yang diskor: makanan & minuman, kedai kopi merek, Alfamart,
Indomaret, dan apotek. Hasilnya tersedia di `/api/stations/{id}/tenants`.


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

Unit analisisnya stasiun jaringan **KAI** di DKI Jakarta: KRL Commuter beserta
stasiun antarkota yang juga dilewati KRL. MRT, LRT Jabodebek, LRT Jakarta, dan
Whoosh sengaja tidak diikutkan.

Penyaringan memakai tag `network` bernilai `KAI Commuter` **atau** `KAI`. Nilai
kedua itu penting: Jakarta Kota, Jatinegara, dan Pasar Senen ditandai `KAI` di
OpenStreetMap padahal ketiganya stasiun KRL utama, dan Jakarta Kota bahkan
terminus dua lin. Menyaring dengan satu nilai saja akan membuang mereka.
Jakarta Gudang dikecualikan karena emplasemen barang tanpa layanan penumpang.

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
