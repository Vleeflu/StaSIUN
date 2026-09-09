"""Logika bersama untuk mengubah fitur GeoJSON stasiun jadi baris database.

Dipakai dua jalur pengisian: seed dari berkas lokal dan ingest dari API MAPID.
Keduanya lewat sini supaya hasilnya sama apa pun sumbernya.
"""

import re
from typing import Any

from geoalchemy2 import WKTElement

from app.core.database import SessionLocal
from app.models.station import Station

# Jaringan yang memakai penomoran lin KRL. Dipakai buat menentukan apakah
# roster lin boleh ditempelkan, bukan lagi buat menyaring stasiun.
KAI_NETWORKS = {"KAI COMMUTER", "KAI", "COMMUTER", "KERETA API"}

# Emplasemen barang, tidak melayani penumpang.
EXCLUDED = {"JAKARTAGUDANG"}

# Dilewati KRL tanpa berhenti.
UNSERVED = {"GAMBIR"}

# Roster resmi tiap lin, mengikuti peta rute KAI Commuter Jabodetabek & Merak.
LINE_ROSTER = {
    "B": """Jakarta Kota;Jayakarta;Mangga Besar;Sawah Besar;Juanda;Gambir;Gondangdia;Cikini;
        Manggarai;Tebet;Cawang;Duren Kalibata;Pasar Minggu Baru;Pasar Minggu;Tanjung Barat;
        Lenteng Agung;Universitas Pancasila;Universitas Indonesia;Pondok Cina;Depok Baru;Depok;
        Citayam;Bojong Gede;Cilebut;Sukaresmi;Bogor""",
    "C": """Pondok Jati;Kramat;Gang Sentiong;Pasar Senen;Kemayoran;Rajawali;Kampung Bandan;Angke;
        Duri;Tanah Abang;Karet;Sudirman;Manggarai;Matraman;Jatinegara;Klender;Buaran;Klender Baru;
        Cakung;Kranji;Bekasi;Bekasi Timur;Tambun;Cibitung;Metland Telaga Murni;Cikarang""",
    "R": """Tanah Abang;Palmerah;Kebayoran;Pondok Ranji;Jurang Mangu;Sudimara;Rawa Buntu;Serpong;
        Cisauk;Cicayur;Jatake;Parung Panjang;Parayasa;Cilejit;Daru;Tenjo;Tigaraksa;Cikoya;Maja;
        Citeras;Rangkasbitung""",
    "T": """Duri;Grogol;Pesing;Taman Kota;Bojong Indah;Rawa Buaya;Kali Deres;Poris;Batu Ceper;
        Tanah Tinggi;Tangerang""",
    "TP": "Jakarta Kota;Kampung Bandan;Ancol;JIS;Tanjung Priok",
    "A": "Manggarai;BNI City;Duri;Batu Ceper;Bandara Soekarno-Hatta",
}


def normalize(name: str) -> str:
    """Samakan ejaan supaya nama dari sumber berbeda bisa dicocokkan."""
    text = (name or "").upper()
    text = text.replace("JAKARTA INTERNATIONAL STADIUM", "JIS")
    text = text.replace("PRIUK", "PRIOK")
    text = text.replace("UNIV.", "UNIVERSITAS")
    text = text.replace("STASIUN", "")
    return re.sub(r"[^A-Z0-9]", "", text)


def _build_line_lookup() -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for code, blob in LINE_ROSTER.items():
        for raw in blob.split(";"):
            key = normalize(raw)
            if key and code not in lookup.setdefault(key, []):
                lookup[key].append(code)
    return lookup


LINE_LOOKUP = _build_line_lookup()


def feature_to_station(feature: dict[str, Any]) -> dict | None:
    """Ubah satu fitur GeoJSON jadi dict siap-simpan, atau None kalau dilewati.

    Menerima dua bentuk properti sekaligus: gaya OpenStreetMap (`name`,
    `network`) dan gaya layer MAPID (`NAMA`/`STASIUN`, `TIPE_3`).
    """
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        return None

    props = feature.get("properties") or {}
    name = (props.get("name") or props.get("NAMA") or props.get("STASIUN") or "").strip()
    if not name:
        return None

    # Kunci sambungan ke poligon isochrone. Nama tidak bisa dipakai: Halim dan
    # Cawang masing-masing dipakai dua stasiun dari moda yang berbeda.
    osm_id = props.get("osm_id") or props.get("full_id")
    osm_id = str(osm_id).lstrip("nwr") if osm_id else None

    key = normalize(name)
    if key in EXCLUDED:
        return None

    # Semua moda diterima: KRL, MRT, LRT, sampai kereta cepat. Jaringannya
    # disimpan apa adanya di kolom types supaya bisa dibedakan saat analisis.
    network = props.get("network") or props.get("TIPE_3") or "Lainnya"

    # Roster lin cuma berlaku buat jaringan KAI. Tanpa penjagaan ini, stasiun
    # senama dari moda lain ikut kebagian lin KRL — Cawang LRT sempat kena,
    # padahal letaknya 1,4 km dari Cawang KRL.
    is_kai = network.upper() in KAI_NETWORKS

    lon, lat = geometry["coordinates"][:2]

    return {
        "osm_id": osm_id,
        "name": name,
        "code": props.get("railway:ref"),
        "types": [network],
        "lines": LINE_LOOKUP.get(key, []) if is_kai else [],
        "served": key not in UNSERVED,
        "address": props.get("addr:full") or props.get("ALAMAT") or None,
        "kecamatan": props.get("addr:subdistrict") or props.get("KECAMATAN") or None,
        "kabkot": props.get("addr:district") or props.get("KABKOT") or None,
        "location": WKTElement(f"POINT({lon} {lat})", srid=4326),
    }


def save_stations(rows: list[dict]) -> None:
    """Ganti seluruh isi tabel stations. Dipanggil hanya kalau rows tidak kosong."""
    session = SessionLocal()
    try:
        session.query(Station).delete()
        for row in rows:
            session.add(Station(**row))
        session.commit()
    finally:
        session.close()


def report(rows: list[dict]) -> None:
    served = sum(1 for r in rows if r["served"])
    without_line = [r["name"] for r in rows if not r["lines"]]
    print(f"{len(rows)} stations stored ({served} served, {len(rows) - served} not served)")
    if without_line:
        print(f"  tanpa lin: {', '.join(sorted(without_line))}")
