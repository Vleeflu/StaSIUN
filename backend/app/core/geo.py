"""Konvensi proyeksi ganda, sesuai PRD bagian Integrasi data.

Geometri disimpan dan dirender dalam EPSG:4326 karena itu yang dimengerti
MapLibre dan GeoJSON. Tapi 4326 satuannya derajat, jadi ST_Area, ST_Distance,
dan ST_Buffer di atasnya menghasilkan angka yang tidak berarti secara fisik.
Setiap perhitungan metrik karena itu wajib lewat EPSG:32748 (UTM 48S), zona
yang menaungi Jakarta.

Perhitungan yang akan memakai ini: Permeability Index (luas isochrone dibagi
luas lingkaran setara), radius pembanding harga sewa pada variabel R di TSI,
dan kepadatan titik minat per satuan luas.

Kolom UTM tersimpan (generated column ST_Transform) sengaja belum dipasang:
belum bisa diuji terhadap PostGIS yang hidup, dan kalau ekspresinya ditolak
saat pembuatan tabel, seluruh stack gagal start. Sampai itu diuji, transformasi
dilakukan di query lewat metric() di bawah.
"""

from sqlalchemy import func

# Penyimpanan dan rendering.
SRID_RENDER = 4326

# Perhitungan dalam meter. UTM 48S menaungi DKI Jakarta.
SRID_METRIC = 32748


def metric(column):
    """Proyeksikan geometri ke UTM 48S supaya hasilnya dalam meter.

    Pakai ini di setiap ST_Area / ST_Distance / ST_Buffer / ST_DWithin, jangan
    memanggil ST_Transform lepasan — supaya SRID metrik hanya ditulis di satu
    tempat kalau suatu saat cakupannya keluar dari zona 48S.
    """
    return func.ST_Transform(column, SRID_METRIC)
