"""Isi tabel stations, isochrones, dan poi dari Geoserver GEO MAPID.

Layer yang ditarik didaftar di data/layers.yml. Kredensialnya di backend/.env.
Hasil stasiun diproses lewat modul yang sama dengan seed lokal, supaya bentuk
barisnya identik apa pun sumbernya.

    python -m scripts.ingest_layers                 # semuanya
    python -m scripts.ingest_layers isochrones      # satu bagian saja
    python -m scripts.ingest_layers isochrones poi
    python -m scripts.ingest_layers --dry-run poi   # tarik dan hitung, jangan simpan
"""

import argparse
import sys
from pathlib import Path

import yaml

from app.services.isochrone_import import (
    IsochroneError,
    features_to_rows,
    save_isochrones,
    validate_layer,
)
from app.services.mapid import MapidError, extract_features, fetch_layer, fetch_layer_list
from app.services.poi_import import PoiError, dedupe, feature_to_poi, save_pois
from app.services.station_import import feature_to_station, report, save_stations

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "layers.yml"

SECTIONS = ("stations", "isochrones", "poi")

# Variabel SEPI yang boleh disuapi titik minat di luar stasiun, menurut PRD
# Tabel 6. Variabel C dan E TIDAK termasuk: keduanya bersumber dari kondisi di
# dalam stasiun lewat survey Activity. Katalog yang memetakan kategori ke C
# atau E ditolak di sini, bukan didiamkan - itu persis kekeliruan yang sedang
# diperbaiki, dan kalau lolos hasilnya tetap keluar tanpa ada yang protes.
VARIABEL_SAH = {"U", "T"}


def load_catalog() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}


def catalog_layer_ids(catalog: dict) -> set[str]:
    ids = {e["layer_id"] for e in catalog.get("stations") or [] if e.get("layer_id")}
    ids |= {e["layer_id"] for e in catalog.get("isochrones") or [] if e.get("layer_id")}
    for mapping in (catalog.get("poi") or catalog.get("pois") or {}).values():
        ids |= {v for v in (mapping or {}).values() if v}
    return ids


def warn_about_trash(catalog: dict) -> None:
    """Ingatkan kalau ada id di katalog yang layernya sudah dibuang di MAPID.

    API-nya tetap melayani layer yang ada di tempat sampah, jadi impornya
    kelihatan berhasil sampai suatu hari isinya benar-benar dibersihkan.
    Sengaja cuma peringatan, bukan kegagalan: datanya masih terpakai.
    """
    try:
        layers = {layer.get("_id"): layer for layer in fetch_layer_list()}
    except MapidError:
        return

    trashed, missing = [], []
    for layer_id in sorted(catalog_layer_ids(catalog)):
        layer = layers.get(layer_id)
        if layer is None:
            missing.append(layer_id)
        elif (layer.get("trash") or {}).get("status") == "inside":
            trashed.append(f"{layer_id}  {layer.get('name')}")

    if trashed:
        print(f"\n! {len(trashed)} layer di katalog sudah ada di tempat sampah MAPID:")
        for line in trashed:
            print(f"    {line}")
    if missing:
        print(f"\n! {len(missing)} layer tidak muncul di daftar (premium, atau dihapus permanen):")
        for line in missing:
            print(f"    {line}")


def ingest_stations(catalog: dict, dry_run: bool) -> int:
    rows: list[dict] = []

    for entry in catalog.get("stations") or []:
        features = extract_features(fetch_layer(entry["layer_id"]))
        matched = [s for f in features if (s := feature_to_station(f))]
        print(f"  - {entry['label']}: {len(features)} fitur, {len(matched)} dipakai")
        rows.extend(matched)

    # Satu stasiun bisa muncul di beberapa layer. Dikunci pakai osm_id, bukan
    # koordinat: sumber yang berbeda menaruh titiknya di tempat yang sedikit
    # berbeda, jadi koordinat tidak menjamin apa-apa.
    unique: dict[str, dict] = {}
    for row in rows:
        unique.setdefault(row["osm_id"] or str(row["location"]), row)
    rows = list(unique.values())

    if not rows:
        print("  ! tidak ada data terambil, tabel stations tidak diubah")
        return 1

    tanpa_osm = sum(1 for r in rows if not r["osm_id"])
    if tanpa_osm:
        print(f"  ! {tanpa_osm} stasiun tanpa osm_id - tidak akan kebagian isochrone")

    if dry_run:
        print(f"  --dry-run: {len(rows)} stasiun tidak disimpan")
        return 0

    save_stations(rows)
    report(rows)
    return 0


def ingest_isochrones(catalog: dict, dry_run: bool) -> int:
    rows: list[dict] = []

    for entry in catalog.get("isochrones") or []:
        label = f"{entry['key']} {entry['minutes']} menit"
        features = extract_features(fetch_layer(entry["layer_id"]))

        # Sengaja tidak dilewati diam-diam: layer yang salah lebih berbahaya
        # daripada impor yang gagal, karena skornya tetap keluar tapi keliru.
        validate_layer(features, entry["minutes"], label)

        batch = features_to_rows(features, entry["minutes"], entry["layer_id"])
        print(f"  - {label}: {len(batch)} poligon")
        rows.extend(batch)

    if not rows:
        print("  ! tidak ada poligon terambil, tabel isochrones tidak diubah")
        return 1

    if dry_run:
        print(f"  --dry-run: {len(rows)} poligon tidak disimpan")
        return 0

    stored, orphans = save_isochrones(rows)
    print(f"{stored} isochrone tersimpan")
    if orphans:
        print(f"  ! {orphans} poligon tidak ketemu stasiunnya (tersimpan sebagai unmatched)")
    return 0


def ingest_poi(catalog: dict, dry_run: bool) -> int:
    katalog_kategori = catalog.get("poi_categories") or []

    salah = [c for c in katalog_kategori if c.get("variable") not in VARIABEL_SAH]
    if salah:
        rincian = ", ".join(f"{c['category']}->{c.get('variable')}" for c in salah)
        raise PoiError(
            f"katalog memetakan kategori ke variabel di luar {sorted(VARIABEL_SAH)}: {rincian}. "
            "PRD Tabel 6: variabel C dan E bersumber dari survey Activity di dalam stasiun."
        )

    fungsi_map = {c["category"]: c["fungsi"] for c in katalog_kategori}
    regions = catalog.get("poi") or catalog.get("pois") or {}

    rows: list[dict] = []
    blanks: list[str] = []

    for key, mapping in regions.items():
        for category, layer_id in (mapping or {}).items():
            if not layer_id:
                blanks.append(f"{key}/{category}")
                continue

            fungsi = fungsi_map.get(category)
            if fungsi is None:
                raise PoiError(f"{key}/{category}: kategorinya tidak ada di poi_categories")

            features = extract_features(fetch_layer(layer_id))
            batch = [p for f in features if (p := feature_to_poi(f, category, fungsi))]
            print(f"  - {key:7s} / {category:16s}: {len(features):5d} fitur, {len(batch):5d} dipakai")
            rows.extend(batch)

    if blanks:
        print(f"  ({len(blanks)} kategori dilewati, layer_id-nya masih kosong)")

    unique = dedupe(rows)
    dropped = len(rows) - len(unique)

    if not unique:
        print("  ! tidak ada titik terambil, baris MAPID tidak diubah")
        return 1

    print(f"\n  {len(unique)} titik unik ({dropped} duplikat dibuang)")
    per_fungsi: dict[str, int] = {}
    for row in unique:
        per_fungsi[row["fungsi"]] = per_fungsi.get(row["fungsi"], 0) + 1
    for f, n in sorted(per_fungsi.items(), key=lambda x: -x[1]):
        print(f"    {n:6d}  {f}")

    if dry_run:
        print("  --dry-run: database tidak disentuh.")
        return 0

    stored = save_pois(unique)
    print(f"\n{stored} titik minat MAPID tersimpan (baris Overpass tidak disentuh)")
    return 0


RUNNERS = {
    "stations": ingest_stations,
    "isochrones": ingest_isochrones,
    "poi": ingest_poi,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sections", nargs="*", choices=SECTIONS, default=list(SECTIONS))
    parser.add_argument("--dry-run", action="store_true", help="tarik dan hitung, jangan simpan")
    args = parser.parse_args()

    catalog = load_catalog()
    warn_about_trash(catalog)

    for section in args.sections:
        print(f"\n{section}")
        try:
            code = RUNNERS[section](catalog, args.dry_run)
        except (MapidError, IsochroneError, PoiError) as exc:
            print(f"  ! {exc}")
            return 1
        if code:
            return code

    return 0


if __name__ == "__main__":
    sys.exit(main())
