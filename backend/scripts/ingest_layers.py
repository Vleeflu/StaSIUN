"""Isi tabel stations, isochrones, dan pois dari Geoserver MAPID.

Layer yang ditarik didaftar di data/layers.yml. Kredensialnya di backend/.env.
Hasil stasiun diproses lewat modul yang sama dengan seed lokal.

Pakai:
    python -m scripts.ingest_layers              # semuanya
    python -m scripts.ingest_layers stations     # satu bagian saja
    python -m scripts.ingest_layers isochrones pois
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
from app.services.mapid import (
    MapidError,
    extract_features,
    fetch_layer,
    fetch_layer_list,
)
from app.services.poi_import import PoiError, dedupe, feature_to_poi, save_pois
from app.services.station_import import feature_to_station, report, save_stations

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "layers.yml"

SECTIONS = ("stations", "isochrones", "pois")


def load_catalog() -> dict:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}


def catalog_layer_ids(catalog: dict) -> set[str]:
    ids = {e["layer_id"] for e in catalog.get("stations") or [] if e.get("layer_id")}
    ids |= {e["layer_id"] for e in catalog.get("isochrones") or [] if e.get("layer_id")}
    for mapping in (catalog.get("pois") or {}).values():
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
        print(f"\n! {len(missing)} layer tidak muncul di daftar (premium, atau sudah dihapus permanen):")
        for line in missing:
            print(f"    {line}")


def ingest_stations(catalog: dict) -> int:
    entries = catalog.get("stations") or []
    rows: list[dict] = []

    for entry in entries:
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

    save_stations(rows)
    report(rows)
    return 0


def ingest_isochrones(catalog: dict) -> int:
    entries = catalog.get("isochrones") or []
    rows: list[dict] = []

    for entry in entries:
        label = f"{entry['key']} {entry['minutes']} menit"
        features = extract_features(fetch_layer(entry["layer_id"]))

        # Sengaja tidak dilewati diam-diam: layer yang salah lebih berbahaya
        # daripada impor yang gagal, karena skornya tetap keluar tapi keliru.
        validate_layer(features, entry["minutes"], label)

        batch = features_to_rows(features, entry["minutes"])
        print(f"  - {label}: {len(batch)} poligon")
        rows.extend(batch)

    if not rows:
        print("  ! tidak ada poligon terambil, tabel isochrones tidak diubah")
        return 1

    stored, orphans = save_isochrones(rows)
    print(f"{stored} isochrone tersimpan")
    if orphans:
        print(f"  {orphans} poligon belum ketemu stasiunnya (di luar cakupan KRL)")
    return 0


def ingest_pois(catalog: dict) -> int:
    variables = {c["category"]: c["variable"] for c in catalog.get("poi_categories") or []}
    regions = catalog.get("pois") or {}

    rows: list[dict] = []
    blanks: list[str] = []

    for key, mapping in regions.items():
        for category, layer_id in (mapping or {}).items():
            if not layer_id:
                blanks.append(f"{key}/{category}")
                continue

            variable = variables.get(category)
            if variable is None:
                raise PoiError(f"{key}/{category}: kategorinya tidak ada di poi_categories")

            features = extract_features(fetch_layer(layer_id))
            batch = [
                poi
                for f in features
                if (poi := feature_to_poi(f, category, variable))
            ]
            print(f"  - {key} / {category}: {len(batch)} titik")
            rows.extend(batch)

    if blanks:
        print(f"  ({len(blanks)} kategori dilewati, layer_id-nya masih kosong)")

    unique = dedupe(rows)
    dropped = len(rows) - len(unique)

    if not unique:
        print("  ! tidak ada titik terambil, tabel pois tidak diubah")
        return 1

    save_pois(unique)
    print(f"{len(unique)} POI tersimpan ({dropped} duplikat dibuang)")

    per_variable: dict[str, int] = {}
    for row in unique:
        per_variable[row["variable"]] = per_variable.get(row["variable"], 0) + 1
    print("  per variabel: " + ", ".join(f"{k}={v}" for k, v in sorted(per_variable.items())))
    return 0


RUNNERS = {
    "stations": ingest_stations,
    "isochrones": ingest_isochrones,
    "pois": ingest_pois,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sections",
        nargs="*",
        choices=SECTIONS,
        default=list(SECTIONS),
        help="bagian katalog yang ditarik; kosong berarti semuanya",
    )
    args = parser.parse_args()

    catalog = load_catalog()
    warn_about_trash(catalog)

    for section in args.sections:
        print(f"\n{section}")
        try:
            code = RUNNERS[section](catalog)
        except (MapidError, IsochroneError, PoiError) as exc:
            print(f"  ! {exc}")
            return 1
        if code:
            return code

    return 0


if __name__ == "__main__":
    sys.exit(main())
