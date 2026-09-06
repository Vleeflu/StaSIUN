# Migrasi database

Kerangka Alembic ini sudah tersambung ke `app.core.config.settings` dan
`Base.metadata`, tapi **belum ada satu revisi pun** dan `docker-entrypoint.sh`
masih memakai `Base.metadata.create_all`.

Alasannya: scaffolding ini ditulis tanpa PostGIS yang hidup untuk diuji, dan
menukar cara pembuatan skema tanpa pengujian berisiko membuat backend gagal
start untuk semua orang.

## Langkah menyelesaikannya (sekali saja, oleh siapa pun yang punya database jalan)

```bash
cd backend
docker compose up -d db
alembic revision --autogenerate -m "initial schema"
```

Periksa berkas yang muncul di `alembic/versions/`. Yang perlu dipastikan:

- Tabel `stations` ada, dengan kolom `location` bertipe `geoalchemy2.types.Geometry`.
- **Tidak ada** `op.create_index` untuk indeks spasial `idx_stations_location` —
  GeoAlchemy2 membuatnya sendiri saat tabel dibuat, jadi kalau ikut tertulis
  hasilnya indeks ganda dan migrasinya gagal. `include_object` di `env.py`
  seharusnya sudah menyaringnya; kalau tetap muncul, hapus manual.
- Tidak ada `op.drop_table("spatial_ref_sys")` atau tabel PostGIS lain.

Lalu uji terhadap database kosong:

```bash
docker compose down -v && docker compose up -d db
alembic upgrade head
```

Kalau lolos, ganti langkah 2 di `backend/docker-entrypoint.sh`:

```sh
# lama
python -c "import app.models.station; from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"

# baru
alembic upgrade head
```

## Setelahnya

Setiap perubahan model diikuti `alembic revision --autogenerate -m "..."`.
Jangan lupa: model baru harus diimpor di `alembic/env.py`, kalau tidak tabelnya
tidak akan terlihat oleh autogenerate.
