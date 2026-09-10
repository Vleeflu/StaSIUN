/** Nama kategori titik minat yang enak dibaca, dan pengelompokannya. */

export const POI_LABEL: Record<string, string> = {
  makanan_minuman: "Makanan & minuman",
  coffee_shop: "Kedai kopi merek",
  alfamart: "Alfamart",
  indomaret: "Indomaret",
  atm_bank: "ATM & bank",
  kantor: "Kantor",
  kantor_swasta: "Kantor swasta",
  apartemen: "Apartemen",
  apotek: "Apotek",
  museum: "Museum",
  wisata_alam: "Wisata alam",
  wisata_budaya: "Wisata budaya",
  hiburan: "Hiburan & kesenian",
  ibadah: "Tempat ibadah",
  halte: "Halte bus",
};

export function poiLabel(category: string): string {
  return POI_LABEL[category] ?? category;
}

/**
 * Titik dibagi dua kelompok, mengikuti cara TSI membaca sekitar stasiun: gerai
 * komersial adalah pesaing, sisanya calon pelanggan.
 *
 * Bedanya ditandai lewat isian bulatan, bukan rona baru. Peta sudah memikul
 * tiga peran warna — merah skor, kuning pilihan, magenta jangkauan — plus enam
 * warna lin KRL; empat rona tambahan akan membuat semuanya tidak terbaca.
 */
/**
 * Kategori yang dihitung sebagai PASOKAN (pesaing), bukan calon pelanggan.
 * Daftarnya harus sama dengan TENANT_CATEGORIES di backend
 * (app/services/scoring/tenant.py) supaya yang terlihat di peta sama dengan
 * yang dipakai TSI.
 *
 * Sebelumnya penandanya `variable === "C"`. Kolom itu sudah tidak ada: menurut
 * PRD Tabel 6 variabel C bersumber dari survey di DALAM stasiun, bukan dari
 * titik minat di luarnya (ADJUSTMENT 8.2).
 */
export const SUPPLY_CATEGORIES = [
  "makanan_minuman",
  "coffee_shop",
  "alfamart",
  "indomaret",
  "apotek",
] as const;
