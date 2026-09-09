"""Cocokkan layer POI di MAPID dengan katalog, lalu isi layers.yml.

Nama layer di GEO MAPID berpola tetap — "<KATEGORI> DI KOTA ADMINISTRASI
<WILAYAH> TAHUN <n> IMPORTED AT <tanggal>" — jadi id-nya bisa dijodohkan
sendiri ke kategori dan wilayah di katalog. Jauh lebih cepat daripada menyalin
70 id satu per satu, dan tidak bisa salah tempel.

Layer yang ada di tempat sampah MAPID diabaikan.

Pakai:
    python -m scripts.match_layers            # lihat dulu hasil jodohnya
    python -m scripts.match_layers --write     # tulis ke data/layers.yml
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

from app.services.mapid import MapidError, fetch_layer_list

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "layers.yml"

# Nama wilayah seperti tertulis di layer MAPID, dipetakan ke key di katalog.
REGIONS = {
    "JAKARTA PUSAT": "jakpus",
    "JAKARTA BARAT": "jakbar",
    "JAKARTA SELATAN": "jaksel",
    "JAKARTA TIMUR": "jaktim",
    "JAKARTA UTARA": "jakut",
}


def normalize(name: str) -> str:
    """Rapikan nama layer supaya bisa dicocokkan apa adanya."""
    return re.sub(r"\s+", " ", (name or "").upper()).strip()


def match_region(name: str) -> str | None:
    for label, key in REGIONS.items():
        if label in name:
            return key
    return None


def match_category(name: str, hints: dict[str, str]) -> str | None:
    """Cari kategori yang petunjuknya cocok di awal nama layer.

    Diurut dari petunjuk terpanjang supaya "KANTOR SWASTA" menang atas
    "KANTOR" — kalau tidak, keduanya jatuh ke kategori yang sama.
    """
    for hint, category in sorted(hints.items(), key=lambda kv: -len(kv[0])):
        if name.startswith(hint):
            return category
    return None


def layer_rank(layer: dict, name: str) -> tuple:
    """Urutan menang kalau satu slot diperebutkan beberapa layer.

    Satu kategori sering punya beberapa terbitan — misalnya halte edisi 2024
    dan 2025. Yang tahunnya paling baru menang; kalau seri, yang diunggah
    belakangan. Tanpa aturan ini pemenangnya ikut urutan balasan API, jadi
    hasilnya bisa berubah-ubah tiap dijalankan.
    """
    year = re.search(r"TAHUN (\d{4})|(20\d{2})", name)
    tahun = int(next(g for g in (year.groups() if year else ()) if g)) if year else 0
    return (tahun, layer.get("date") or "")


def render_pois(catalog: dict, found: dict[str, dict[str, str]]) -> str:
    """Susun ulang blok pois, tetap memakai urutan kategori dari katalog."""
    categories = [c["category"] for c in catalog.get("poi_categories") or []]
    width = max(len(c) for c in categories) + 1

    lines = ["pois:"]
    for key in catalog.get("pois") or {}:
        lines.append(f"  {key}:")
        for category in categories:
            layer_id = (found.get(key, {}).get(category) or (0, ""))[1]
            lines.append(f'    {(category + ":").ljust(width)} "{layer_id}"')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="tulis hasilnya ke layers.yml")
    args = parser.parse_args()

    raw = CATALOG_PATH.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    catalog = yaml.safe_load(text) or {}

    hints = {
        normalize(c.get("hint") or c["category"]): c["category"]
        for c in catalog.get("poi_categories") or []
    }

    try:
        layers = fetch_layer_list()
    except MapidError as exc:
        print(f"! {exc}")
        return 1

    found: dict[str, dict[str, str]] = {}
    clashes: list[str] = []

    for layer in layers:
        if (layer.get("trash") or {}).get("status") == "inside":
            continue

        name = normalize(layer.get("name"))
        region = match_region(name)
        category = match_category(name, hints)

        if not region or not category:
            continue

        slot = found.setdefault(region, {})
        rank = layer_rank(layer, name)

        if category in slot:
            clashes.append(f"{region}/{category}")
            if rank <= slot[category][0]:
                continue

        slot[category] = (rank, layer.get("_id"))

    categories = [c["category"] for c in catalog.get("poi_categories") or []]
    regions = list(catalog.get("pois") or {})

    print(f"{'':16}" + "".join(f"{r:9}" for r in regions))
    missing = 0
    for category in categories:
        marks = ""
        for region in regions:
            hit = found.get(region, {}).get(category)
            marks += f"{'  ok':9}" if hit else f"{'   -':9}"
            missing += 0 if hit else 1
        print(f"{category:16}{marks}")

    total = len(categories) * len(regions)
    print(f"\n{total - missing} dari {total} slot terisi")

    if clashes:
        print(f"\n! {len(clashes)} layer bentrok, yang pertama dipakai:")
        for line in clashes:
            print(f"    {line}")

    if not args.write:
        print("\n(belum ditulis, tambahkan --write kalau hasilnya sudah benar)")
        return 0

    head = text[: text.index("pois:")]
    updated = head + render_pois(catalog, found)
    CATALOG_PATH.write_bytes(
        updated.replace("\n", "\r\n" if crlf else "\n").encode("utf-8")
    )
    print(f"\ndata/layers.yml diperbarui")
    return 0


if __name__ == "__main__":
    sys.exit(main())
