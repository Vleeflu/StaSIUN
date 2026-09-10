"""Cetak layer di proyek GEO MAPID beserta id-nya.

Dipakai buat mengisi data/layers.yml tanpa menyalin id satu-satu dari dasbor.
Endpoint-nya tidak terdokumentasi, tapi itu yang dipakai dasbor MAPID sendiri.

Bawaannya cuma layer aktif yang ditampilkan. API MAPID tetap melayani layer
yang sudah dibuang ke tempat sampah, jadi tanpa penyaringan ini gampang
tertempel id yang sebenarnya sudah dihapus.

Pakai:
    python -m scripts.list_layers                  # semua layer aktif
    python -m scripts.list_layers alfamart pusat   # saring per kata
    python -m scripts.list_layers --yaml halte     # siap tempel ke layers.yml
    python -m scripts.list_layers --all            # ikut yang di tempat sampah
"""

import argparse
import sys

from app.services.mapid import MapidError, fetch_layer_list


def is_trashed(layer: dict) -> bool:
    return (layer.get("trash") or {}).get("status") == "inside"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "terms",
        nargs="*",
        help="saring nama layer, tidak peduli huruf besar-kecil; semua kata harus cocok",
    )
    parser.add_argument("--yaml", action="store_true", help="cetak sebagai baris katalog")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="include_trashed",
        help="ikut tampilkan layer yang ada di tempat sampah",
    )
    args = parser.parse_args()

    try:
        layers = fetch_layer_list()
    except MapidError as exc:
        print(f"! {exc}")
        return 1

    needles = [t.lower() for t in args.terms]
    rows = [
        layer
        for layer in layers
        if all(n in (layer.get("name") or "").lower() for n in needles)
        and (args.include_trashed or not is_trashed(layer))
    ]
    rows.sort(key=lambda layer: (layer.get("name") or "").lower())

    for layer in rows:
        name = layer.get("name") or "(tanpa nama)"
        if args.yaml:
            print(f'    ganti_kategori: "{layer.get("_id")}"   # {name}')
        else:
            tags = []
            if layer.get("is_premium"):
                tags.append("premium")
            if is_trashed(layer):
                tags.append("DI TEMPAT SAMPAH")
            suffix = f"  [{', '.join(tags)}]" if tags else ""
            print(f'{layer.get("_id")}  {layer.get("type", "?"):8}  {name}{suffix}')

    active = sum(1 for layer in layers if not is_trashed(layer))
    scope = "layer" if args.include_trashed else "layer aktif"
    total = len(layers) if args.include_trashed else active
    print(f"\n{len(rows)} dari {total} {scope}", file=sys.stderr)

    if not args.include_trashed and len(layers) != active:
        print(
            f"({len(layers) - active} layer disembunyikan karena ada di tempat sampah, "
            f"pakai --all buat melihatnya)",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
