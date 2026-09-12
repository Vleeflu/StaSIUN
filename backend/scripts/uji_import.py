"""Uji logika murni isochrone_import dan poi_import. Tidak menyentuh database.

Yang diuji adalah bagian yang paling gampang salah diam-diam: penguraian osm_id,
pengubahan geometri, validasi layer, dan penyaring duplikat. Semuanya fungsi
murni, jadi bisa diuji tanpa PostGIS, tanpa jaringan, dan tanpa kredensial.

    python -m scripts.uji_import

Bisa dijalankan di dalam container maupun di Python biasa di luar container.
Di luar container sqlalchemy dan geoalchemy2 belum tentu terpasang, jadi
keduanya diganti boneka seperlunya - fungsi yang diuji memang tidak memakainya.
"""

import math
import sys
import types
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

try:  # di dalam container, dependensinya sungguhan
    import geoalchemy2  # noqa: F401
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:  # di luar container, dipasangi boneka
    sys.path.insert(0, str(BACKEND))

    def _boneka(nama: str, **isi) -> types.ModuleType:
        modul = types.ModuleType(nama)
        for kunci, nilai in isi.items():
            setattr(modul, kunci, nilai)
        sys.modules[nama] = modul
        return modul

    class _WKT:
        def __init__(self, wkt, srid=None):
            self.wkt, self.srid = wkt, srid

    _boneka("geoalchemy2", WKTElement=_WKT, Geometry=object)
    _boneka("sqlalchemy", select=lambda *a: None, text=lambda s: s)
    _boneka("sqlalchemy.orm", Session=object, Mapped=object, mapped_column=lambda *a, **k: None)
    # Paket app dan app.services tetap dimuat dari berkas aslinya lewat __path__;
    # hanya app.core.* dan app.models.* yang benar-benar diganti boneka.
    _boneka("app", __path__=[str(BACKEND / "app")])
    _boneka("app.services", __path__=[str(BACKEND / "app" / "services")])
    _boneka("app.core", __path__=[str(BACKEND / "app" / "core")])
    _boneka("app.models", __path__=[str(BACKEND / "app" / "models")])
    _boneka("app.core.database", SessionLocal=lambda: None, Base=object)
    _boneka("app.core.geo", SRID_RENDER=4326, SRID_METRIC=32748)
    _boneka("app.models.isochrone", Isochrone=object)
    _boneka("app.models.station", Station=object)
    _boneka("app.models.reference", Poi=object)

from app.services import isochrone_import as iso  # noqa: E402
from app.services import poi_import as poi  # noqa: E402

_lulus = 0
_gagal = 0


def cek(nama: str, hasil, harapan) -> None:
    global _lulus, _gagal
    if hasil == harapan:
        _lulus += 1
        print(f"  ok    {nama}")
    else:
        _gagal += 1
        print(f"  GAGAL {nama}")
        print(f"          dapat   : {hasil!r}")
        print(f"          harusnya: {harapan!r}")


def pesan_galat(fn, *args) -> str:
    """Jalankan fn, kembalikan pesan galatnya. Tidak melempar = kegagalan uji."""
    try:
        fn(*args)
        return "TIDAK MELEMPAR"
    except iso.IsochroneError as exc:
        return str(exc).split(":", 1)[1].strip()


def uji_osm_id() -> None:
    print("\n_osm_id - prefiks n/w/r harus dibuang supaya cocok dengan stations.osm_id")
    cek("osm_id berupa angka", iso._osm_id({"osm_id": 4981870932}), "4981870932")
    cek("full_id node", iso._osm_id({"full_id": "n4981870932"}), "4981870932")
    cek("full_id way", iso._osm_id({"full_id": "w123"}), "123")
    cek("full_id relation", iso._osm_id({"full_id": "r456"}), "456")
    cek("osm_id didahulukan", iso._osm_id({"osm_id": 99, "full_id": "n11"}), "99")
    cek("tidak ada keduanya", iso._osm_id({}), None)


def uji_geometri() -> None:
    print("\n_to_multipolygon - Polygon dan MultiPolygon harus jadi satu bentuk")
    kotak = [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]]
    harapan = "MULTIPOLYGON(((0.0 0.0, 1.0 0.0, 1.0 1.0, 0.0 1.0, 0.0 0.0)))"
    cek("Polygon dibungkus", iso._to_multipolygon({"type": "Polygon", "coordinates": kotak}), harapan)
    cek(
        "MultiPolygon tetap",
        iso._to_multipolygon({"type": "MultiPolygon", "coordinates": [kotak]}),
        harapan,
    )
    cek("Point ditolak", iso._to_multipolygon({"type": "Point", "coordinates": [1, 2]}), None)
    cek("koordinat kosong ditolak", iso._to_multipolygon({"type": "Polygon", "coordinates": []}), None)

    # Cincin kedua adalah lubang. Harus ikut terbawa, bukan dibuang diam-diam:
    # isochrone bisa berlubang di sekitar blok yang tidak bisa dilewati pejalan.
    berlubang = kotak + [[[0.2, 0.2], [0.4, 0.2], [0.4, 0.4], [0.2, 0.2]]]
    hasil = iso._to_multipolygon({"type": "Polygon", "coordinates": berlubang})
    cek("lubang ikut terbawa", hasil.count("), ("), 1)


def uji_validasi() -> None:
    print("\nvalidate_layer - layer yang salah harus BERBUNYI, bukan lolos diam-diam")
    baik = [{"properties": {"isochrone_profile": "foot", "time_limit": 300, "osm_id": 1}}]
    cek("layer benar lolos", iso.validate_layer(baik, 5, "uji"), None)
    cek("layer kosong ditolak", pesan_galat(iso.validate_layer, [], 5, "uji"), "layernya kosong, nol fitur")

    profil_mobil = [{"properties": {"isochrone_profile": "car", "time_limit": 300, "osm_id": 1}}]
    cek("profil mobil ditolak", pesan_galat(iso.validate_layer, profil_mobil, 5, "uji")[:9], "profilnya")

    limit_keliru = [{"properties": {"isochrone_profile": "foot", "time_limit": 600, "osm_id": 1}}]
    cek("time_limit keliru ditolak", pesan_galat(iso.validate_layer, limit_keliru, 5, "uji")[:10], "time_limit")

    tanpa_id = [{"properties": {"isochrone_profile": "foot", "time_limit": 300}}]
    cek("poligon tanpa osm_id ditolak", pesan_galat(iso.validate_layer, tanpa_id, 5, "uji")[:6], "1 dari")

    # Kasus paling berbahaya: sebagian benar. Kalau pemeriksaannya cuma melihat
    # fitur pertama, layer campuran akan lolos dan separuh isinya keliru.
    campuran = baik + profil_mobil
    cek("campuran foot+car ditolak", pesan_galat(iso.validate_layer, campuran, 5, "uji")[:9], "profilnya")


def uji_lingkaran() -> None:
    print("\nlingkaran_setara_m2 - penyebut Permeability Index")
    cek(
        "5 menit @ 5 km/jam",
        round(iso.lingkaran_setara_m2(5), 0),
        round(math.pi * (5000 / 3600 * 300) ** 2, 0),
    )
    # Luas berbanding kuadrat waktu: durasi dua kali lipat memberi luas empat kali.
    cek(
        "durasi 2x -> luas 4x",
        round(iso.lingkaran_setara_m2(10) / iso.lingkaran_setara_m2(5), 6),
        4.0,
    )


def uji_nama_dan_jarak() -> None:
    print("\nname_key dan meters_between")
    cek(
        "tanda kurung tidak membedakan",
        poi.name_key("INDOMARET PETOGOGAN (TB49)"),
        poi.name_key("Indomaret Petogogan TB49"),
    )
    cek("pemisah pipa dibuang", poi.name_key("A | B"), "AB")
    cek("nama non-latin tidak jadi kosong", poi.name_key("東京"), "東京")
    cek("kosong tetap kosong", poi.name_key(""), "")
    cek(
        "satu meter ke utara",
        round(poi.meters_between((106.8, -6.2), (106.8, -6.2 + 1 / 110540)), 2),
        1.0,
    )


def uji_dedupe() -> None:
    print("\ndedupe - jebakan Starbucks Cideng")

    def titik(nama, lon, lat):
        return {"name": nama, "_key": (poi.name_key(nama), (lon, lat))}

    # Dua salinan terpaut ~1,1 cm. Pembulatan koordinat ke kisi gagal menyatukan
    # keduanya kalau jatuh di sisi garis kisi yang berbeda; jaraknya tidak gagal.
    kembar = [titik("Starbucks Cideng", 106.8149999, -6.17),
              titik("Starbucks Cideng", 106.8150001, -6.17)]
    cek("dua salinan 1,1 cm jadi satu", len(poi.dedupe(kembar)), 1)

    # Nama sama tapi 330 m terpisah: dua gerai berbeda, jangan digabung.
    berjauhan = [titik("Alfamart", 106.8000, -6.17), titik("Alfamart", 106.8030, -6.17)]
    cek("nama sama beda 330 m tetap dua", len(poi.dedupe(berjauhan)), 2)

    setempat = [titik("A", 106.8, -6.17), titik("B", 106.8, -6.17)]
    cek("nama beda posisi sama tetap dua", len(poi.dedupe(setempat)), 2)
    cek("_key tidak bocor ke hasil", "_key" in poi.dedupe([kembar[0]])[0], False)


def main() -> int:
    for uji in (uji_osm_id, uji_geometri, uji_validasi, uji_lingkaran,
                uji_nama_dan_jarak, uji_dedupe):
        uji()

    print(f"\n{_lulus} lulus, {_gagal} gagal")
    return 1 if _gagal else 0


if __name__ == "__main__":
    sys.exit(main())
