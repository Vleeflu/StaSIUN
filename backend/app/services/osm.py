"""Penarikan titik minat dari OpenStreetMap lewat Overpass API.

Mengisi tabel `poi`, yang menyuplai dua hal di PRD: variabel U pada SEPI
(kepadatan titik minat, keberagaman fungsi lahan, pembangkit perjalanan besar)
dan komponen supply pada GapScore (kategori usaha yang sudah tersedia di luar
stasiun).

Tiga catatan yang menentukan bentuk modul ini:

1. Overpass menolak permintaan dengan User-Agent bawaan pustaka HTTP — jawaban
   yang keluar 406 Not Acceptable, bukan pesan yang menjelaskan. Karena itu
   USER_AGENT di bawah wajib dikirim.
2. Yang diambil `nwr` (node, way, relation), bukan `node` saja. Pengamatan di
   tiga stasiun contoh: 916 dari 1.487 elemen bertipe `way` — mal, rumah sakit,
   dan sekolah di OSM digambar sebagai poligon bangunan, bukan titik. Mengambil
   node saja membuang justru pembangkit perjalanan terbesar.
3. Dua kategori TIDAK mewakili fungsi lahan dan karena itu dikecualikan dari
   perhitungan keberagaman di app/services/indicators.py: "fasilitas_jalan"
   (perabot jalan) dan "lainnya" (yang tidak tergolongkan). Keduanya tetap
   disimpan karena berguna untuk hal lain.
4. Tag mentah tetap disimpan apa adanya di kolom `osm_tags`. Kalau aturan
   penggolongan di bawah berubah, kategorinya bisa dihitung ulang dari data yang
   sudah tersimpan tanpa menarik ulang dari Overpass. Di sanalah nanti
   "pembangkit perjalanan berskala besar" dikenali (shop=mall, amenity=hospital,
   amenity=university), jadi tidak perlu kolom tambahan di tabel.
"""

import logging
import time
from typing import Any

import httpx

# Modul layanan tidak mencetak langsung ke layar — dia melapor lewat logging,
# dan skrip pemanggilnya yang memutuskan apakah laporan itu ditampilkan.
log = logging.getLogger(__name__)

# Overpass memblokir User-Agent bawaan pustaka HTTP. Identitas aplikasi wajib.
USER_AGENT = "StaSIUN/0.1 (MAPID WebGIS Competition 2026; research use)"

# Cermin resmi lebih dulu, cadangan menyusul kalau yang pertama sibuk.
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Kunci OSM yang menandai sebuah objek sebagai titik minat. Dipakai sebagai
# regex kunci supaya area yang sama cukup dipindai sekali, bukan enam kali.
POI_KEYS = ("amenity", "shop", "office", "tourism", "leisure", "healthcare")

# 15 menit x 4,8 km/jam = 1,2 km, batas teoretis terjauh jalan kaki. Isochrone
# sungguhan pasti lebih sempit, jadi mengambil sedikit lebih lebar sekarang
# berarti tidak perlu menarik ulang saat poligonnya datang.
DEFAULT_RADIUS_M = 1200


class OverpassError(RuntimeError):
    """Overpass tidak bisa dihubungi atau menolak kueri."""


# --- Penggolongan kategori --------------------------------------------------
#
# Disusun dari sebaran tag yang benar-benar muncul di sekitar stasiun DKI,
# bukan dari daftar teoretis. Urutan pemeriksaannya penting dan sengaja
# ditulis eksplisit di kategori(): satu objek bisa membawa beberapa kunci
# sekaligus (misal amenity=pharmacy + healthcare=pharmacy), jadi harus ada
# aturan yang menentukan mana yang menang — kalau tidak, hasilnya berubah-ubah
# mengikuti urutan tag yang kebetulan dikirim server.

AMENITY_KATEGORI = {
    "restaurant": "makanan_minuman",
    "cafe": "makanan_minuman",
    "fast_food": "makanan_minuman",
    "food_court": "makanan_minuman",
    "bar": "makanan_minuman",
    "pub": "makanan_minuman",
    "ice_cream": "makanan_minuman",
    "bank": "keuangan",
    "atm": "keuangan",
    "bureau_de_change": "keuangan",
    "hospital": "kesehatan",
    "clinic": "kesehatan",
    "doctors": "kesehatan",
    "dentist": "kesehatan",
    "pharmacy": "kesehatan",
    "veterinary": "kesehatan",
    "school": "pendidikan",
    "university": "pendidikan",
    "college": "pendidikan",
    "kindergarten": "pendidikan",
    "language_school": "pendidikan",
    "driving_school": "pendidikan",
    "place_of_worship": "ibadah",
    "parking": "transportasi",
    "fuel": "transportasi",
    "bus_station": "transportasi",
    "taxi": "transportasi",
    "car_rental": "transportasi",
    "bicycle_parking": "transportasi",
    "charging_station": "transportasi",
    "post_office": "layanan_publik",
    "police": "layanan_publik",
    "townhall": "layanan_publik",
    "library": "layanan_publik",
    "community_centre": "layanan_publik",
    "courthouse": "layanan_publik",
    "fire_station": "layanan_publik",
    "social_facility": "layanan_publik",
    "grave_yard": "layanan_publik",
    "crematorium": "layanan_publik",
    "prison": "layanan_publik",
    "marketplace": "ritel",
    "vending_machine": "ritel",
    # Ditambahkan 7 Sep setelah memeriksa isi kategori "lainnya": nilai-nilai
    # berikut adalah fungsi lahan sungguhan yang sebelumnya jatuh ke keranjang
    # sisa hanya karena belum terdaftar di sini.
    "cinema": "hiburan_rekreasi",
    "theatre": "hiburan_rekreasi",
    "nightclub": "hiburan_rekreasi",
    "arts_centre": "hiburan_rekreasi",
    "events_venue": "hiburan_rekreasi",
    "studio": "hiburan_rekreasi",
    "motorcycle_parking": "transportasi",
    "bicycle_rental": "transportasi",
    "car_pooling": "transportasi",
    "car_wash": "jasa",
    "internet_cafe": "jasa",
    "photo_booth": "jasa",
    "parcel_locker": "jasa",
    "prep_school": "pendidikan",
}

# Perabot jalan: ADA di lapangan, tetapi BUKAN fungsi lahan. Bangku, tempat
# sampah, dan pintu masuk parkir tidak menarik siapa pun datang ke sebuah
# kawasan, jadi memasukkannya ke perhitungan keberagaman fungsi lahan itu
# keliru — dan keliru yang tidak merata, karena banyaknya bangku yang
# terpetakan lebih mencerminkan kerajinan pemeta OpenStreetMap di daerah itu
# daripada keadaan kawasannya.
#
# Tetap disimpan di tabel, tidak dibuang: toilet, bangku, dan tempat sampah
# justru bahan langsung untuk fitur Facility Sponsorship, yang berangkat dari
# keluhan kondisi fasilitas.
FASILITAS_JALAN = {
    "parking_entrance",
    "parking_space",
    "bench",
    "chair",
    "toilets",
    "shower",
    "waste_basket",
    "waste_disposal",
    "fountain",
    "drinking_water",
    "water_point",
    "shelter",
    "clock",
    "telephone",
    "post_box",
    "ticket_validator",
    "bbq",
}

SHOP_KATEGORI = {
    "bakery": "makanan_minuman",
    "coffee": "makanan_minuman",
    "pastry": "makanan_minuman",
    "confectionery": "makanan_minuman",
    "deli": "makanan_minuman",
    "laundry": "jasa",
    "dry_cleaning": "jasa",
    "hairdresser": "jasa",
    "beauty": "jasa",
    "copyshop": "jasa",
    "travel_agency": "jasa",
    "tailor": "jasa",
    "car_repair": "jasa",
    "motorcycle_repair": "jasa",
    "optician": "kesehatan",
    "chemist": "kesehatan",
    "medical_supply": "kesehatan",
}


def kategori(tags: dict[str, str]) -> str:
    """Seragamkan tag OSM jadi satu kategori milik kita.

    Urutan pemeriksaan menentukan hasil, jadi ditulis dari yang paling khusus
    ke yang paling umum. Nilai amenity yang tidak dikenali sengaja jatuh ke
    "lainnya", bukan dipaksa masuk kategori terdekat — kategori palsu lebih
    berbahaya daripada kategori "lainnya" yang jujur.
    """
    amenity = tags.get("amenity")
    if amenity in FASILITAS_JALAN:
        return "fasilitas_jalan"
    if amenity in AMENITY_KATEGORI:
        return AMENITY_KATEGORI[amenity]

    shop = tags.get("shop")
    if shop is not None:
        # Sebagian besar shop=* memang ritel; yang bukan didaftar di atas.
        return SHOP_KATEGORI.get(shop, "ritel")

    if tags.get("healthcare"):
        return "kesehatan"
    if tags.get("office"):
        return "perkantoran"
    if tags.get("leisure") or tags.get("tourism"):
        return "hiburan_rekreasi"

    return "lainnya"


# --- Pengambilan data -------------------------------------------------------


def build_query(
    centers: list[tuple[float, float]], radius_m: int = DEFAULT_RADIUS_M, timeout_s: int = 180
) -> str:
    """Susun satu kueri Overpass untuk beberapa titik pusat sekaligus.

    `out center tags` penting: untuk way dan relation, Overpass tidak
    mengirimkan koordinat kecuali diminta titik pusatnya.
    """
    keys = "|".join(POI_KEYS)
    bagian = "".join(
        f'nwr(around:{radius_m},{lat},{lon})[~"^({keys})$"~"."];' for lat, lon in centers
    )
    return f"[out:json][timeout:{timeout_s}];({bagian});out center tags;"


def fetch(
    query: str, timeout: float = 240.0, percobaan: int = 3
) -> list[dict[str, Any]]:
    """Jalankan kueri ke Overpass, dengan cermin cadangan dan percobaan ulang.

    Percobaan ulang bertingkat itu keharusan, bukan kemewahan: Overpass
    membatasi laju permintaan dan membalas 429 Too Many Requests begitu terlalu
    sering dihubungi. Jeda tetap tidak cukup karena batasnya dihitung dari
    beban server saat itu, jadi jeda harus melebar tiap kali gagal.
    """
    kesalahan: list[str] = []

    for putaran in range(percobaan):
        for url in ENDPOINTS:
            try:
                response = httpx.post(
                    url,
                    data={"data": query},
                    headers={"User-Agent": USER_AGENT},
                    timeout=timeout,
                )
                response.raise_for_status()

                # Berhasil, tetapi kalau sempat gagal sebelumnya, itu WAJIB
                # terdengar. Percobaan ulang yang diam-diam berhasil membuat
                # "Overpass sehat" dan "Overpass hampir tumbang" terlihat
                # sama persis dari luar — padahal keduanya menuntut tindakan
                # berbeda. Sebelum ini, satu-satunya petunjuk cuma waktu
                # penarikan yang janggal.
                if kesalahan:
                    log.warning(
                        "Overpass berhasil setelah %d kegagalan: %s",
                        len(kesalahan),
                        " | ".join(kesalahan),
                    )
                return response.json().get("elements", [])
            except httpx.HTTPError as exc:
                kesalahan.append(f"putaran {putaran + 1} {url}: {exc}")

        if putaran < percobaan - 1:
            # 5 detik, lalu 10, lalu menyerah. Melebar supaya server sempat
            # pulih, tetapi tidak sampai membuat penarikan berjam-jam.
            jeda = 5 * (2**putaran)
            log.warning(
                "Overpass gagal di putaran %d, menunggu %d detik lalu mengulang.",
                putaran + 1,
                jeda,
            )
            time.sleep(jeda)

    raise OverpassError("Overpass gagal setelah semua percobaan -> " + " | ".join(kesalahan))


def element_to_poi(element: dict[str, Any]) -> dict | None:
    """Ubah satu elemen Overpass jadi baris siap-simpan, atau None kalau dilewati.

    Node membawa lat/lon langsung; way dan relation membawa `center` hasil
    permintaan `out center`. Elemen tanpa keduanya dilewati — tanpa koordinat,
    sebuah titik minat tidak berguna untuk analisis spasial apa pun.
    """
    tags = element.get("tags") or {}
    if not tags:
        return None

    posisi = element.get("center") or element
    lat, lon = posisi.get("lat"), posisi.get("lon")
    if lat is None or lon is None:
        return None

    return {
        "osm_type": element["type"],
        "osm_id": element["id"],
        "name": tags.get("name"),
        "category": kategori(tags),
        "osm_tags": tags,
        "lat": lat,
        "lon": lon,
    }
