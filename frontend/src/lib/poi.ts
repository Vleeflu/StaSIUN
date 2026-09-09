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
export const SUPPLY_VARIABLE = "C";
