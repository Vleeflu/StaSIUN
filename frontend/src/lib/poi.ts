/** Nama kategori titik minat yang enak dibaca, dan pengelompokannya. */

export const POI_LABEL: Record<string, string> = {
  makanan_minuman: "Makanan & minuman",
  coffee_shop: "Kedai kopi",
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
 * warna line KRL; empat rona tambahan akan membuat semuanya tidak terbaca.
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


/**
 * Kelompok fungsional titik minat, beserta warnanya di peta.
 *
 * Sebelumnya seluruh titik digambar satu warna dan hanya dibedakan isian
 * bulatan (pesaing vs calon pelanggan). Itu keputusan yang masuk akal saat
 * peta sudah memikul tiga peran warna plus enam warna line KRL - tetapi
 * akibatnya pengguna tidak bisa melihat KOMPOSISI kawasan, padahal justru itu
 * yang menjelaskan kenapa sebuah stasiun berskor tinggi.
 *
 * Jalan tengahnya: enam kelompok, bukan enam belas kategori. Enam warna masih
 * bisa dibedakan mata, dan legendanya bisa diklik untuk menyorot satu kelompok
 * saja - sehingga beban warna yang tampak bersamaan tetap bisa dikendalikan
 * pengguna.
 */
export const KELOMPOK_POI: {
  id: string;
  label: string;
  warna: string;
  kategori: string[];
}[] = [
  {
    id: "makan",
    label: "Makan & minum",
    warna: "#e8590c",
    kategori: ["makanan_minuman", "coffee_shop"],
  },
  {
    id: "ritel",
    label: "Ritel & kebutuhan harian",
    warna: "#2f9e44",
    kategori: ["alfamart", "indomaret", "apotek"],
  },
  {
    id: "keuangan",
    label: "ATM & bank",
    warna: "#1971c2",
    kategori: ["atm_bank"],
  },
  {
    id: "kerja_tinggal",
    label: "Kantor & hunian",
    warna: "#7048e8",
    kategori: ["kantor", "kantor_swasta", "apartemen"],
  },
  {
    id: "wisata",
    label: "Wisata & hiburan",
    warna: "#c2255c",
    kategori: ["museum", "wisata_alam", "wisata_budaya", "hiburan"],
  },
  {
    id: "publik",
    label: "Fasilitas publik",
    warna: "#868e96",
    kategori: ["ibadah", "halte"],
  },
];

/** Ekspresi MapLibre: kategori -> warna kelompoknya. */
export function ekspresiWarnaPoi(): unknown[] {
  const pasangan: unknown[] = [];
  for (const k of KELOMPOK_POI) {
    for (const kat of k.kategori) {
      pasangan.push(kat, k.warna);
    }
  }
  // Kategori yang belum masuk kelompok mana pun tetap digambar, berwarna netral
  // - lebih baik terlihat sebagai titik abu daripada hilang dari peta.
  return ["match", ["get", "category"], ...pasangan, "#adb5bd"];
}

/** Kategori yang termasuk kelompok-kelompok yang sedang dinyalakan. */
export function kategoriAktif(idAktif: string[]): string[] {
  return KELOMPOK_POI.filter((k) => idAktif.includes(k.id)).flatMap((k) => k.kategori);
}

/** Kelompok tempat sebuah kategori bernaung, kalau ada. */
export function kelompokDariKategori(kategori: string) {
  return KELOMPOK_POI.find((k) => k.kategori.includes(kategori)) ?? null;
}

/**
 * Peran satu titik dalam perhitungan, dijelaskan dengan kalimat.
 *
 * Warna dan isian bulatan sudah membedakan pesaing dari calon pelanggan, tapi
 * itu cuma terbaca kalau pembacanya sudah hafal legendanya. Saat titiknya
 * diklik, alasannya harus tertulis - sebab pertanyaan yang sebenarnya bukan
 * "titik ini warna apa", melainkan "titik ini memengaruhi angka yang mana".
 */
const ALASAN_PESAING: Record<string, string> = {
  makanan_minuman:
    "Memperebutkan pembeli yang sama dengan warung makan baru. Kerapatannya menekan kelayakan sektor Makanan & minuman.",
  coffee_shop:
    "Pesaing langsung kedai kopi, dan sebagian juga menyerap pembeli yang sekadar mencari tempat duduk.",
  alfamart:
    "Pesaing minimarket. Alfamart dan Indomaret dihitung satu sektor - keduanya menjual barang yang sama ke orang yang sama.",
  indomaret:
    "Pesaing minimarket. Alfamart dan Indomaret dihitung satu sektor - keduanya menjual barang yang sama ke orang yang sama.",
  apotek:
    "Pesaing sektor apotek & obat. Pembelian obat jarang berulang dalam sehari, jadi satu apotek saja sudah cukup menutup kebutuhan sekitarnya.",
};

const ALASAN_PELANGGAN: Record<string, string> = {
  kantor:
    "Kantor memasok pembeli pada jam berangkat, istirahat siang, dan pulang - pola tiga puncak yang paling cocok untuk makanan siap santap.",
  kantor_swasta:
    "Kantor memasok pembeli pada jam berangkat, istirahat siang, dan pulang - pola tiga puncak yang paling cocok untuk makanan siap santap.",
  apartemen:
    "Hunian memasok pembeli yang berulang tiap hari, dan belanjanya condong ke kebutuhan harian ketimbang santap di tempat.",
  atm_bank:
    "Menarik orang yang datang dengan keperluan singkat, dan singgahnya sering berlanjut ke gerai sebelah.",
  museum:
    "Pengunjung wisata datang berombongan di akhir pekan - ramainya besar tapi tidak tiap hari.",
  wisata_alam:
    "Pengunjung wisata datang berombongan di akhir pekan - ramainya besar tapi tidak tiap hari.",
  wisata_budaya:
    "Pengunjung wisata datang berombongan di akhir pekan - ramainya besar tapi tidak tiap hari.",
  hiburan:
    "Ramainya menumpuk di malam hari dan akhir pekan, berlawanan jam dengan kerumunan pekerja.",
  ibadah:
    "Mengumpulkan orang pada jam-jam tertentu, dan di sekitar waktu itu lalu lalangnya melonjak tajam.",
  halte:
    "Titik perpindahan moda: orang berhenti sebentar di sini, dan jeda itulah kesempatan belanja singkat.",
};

/**
 * Peran satu titik dalam perhitungan, dijelaskan dengan kalimat.
 *
 * Warna dan isian bulatan sudah membedakan pesaing dari calon pelanggan, tapi
 * itu cuma terbaca kalau pembacanya sudah hafal legendanya. Saat titiknya
 * diklik, alasannya harus tertulis - sebab pertanyaan yang sebenarnya bukan
 * "titik ini warna apa", melainkan "titik ini memengaruhi angka yang mana".
 *
 * Alasannya ditulis per kategori, bukan per peran. Dua kalimat umum - satu
 * untuk pesaing, satu untuk calon pelanggan - memang lebih ringkas, tapi
 * akibatnya keterangan yang sama persis muncul di ratusan titik berbeda;
 * pembaca cepat belajar bahwa popupnya tidak mengandung informasi baru dan
 * berhenti membukanya. Kantor dan masjid sama-sama calon pelanggan, tetapi
 * yang menjelaskan keputusan penyewa adalah BEDANYA: jam ramainya tidak sama.
 */
export function peranPoi(kategori: string): { peran: string; alasan: string } {
  const pesaing = (SUPPLY_CATEGORIES as readonly string[]).includes(kategori);

  if (pesaing) {
    return {
      peran: "Pesaing",
      alasan:
        ALASAN_PESAING[kategori] ??
        "Gerai sejenis yang sudah berjualan di sekitar stasiun. Kerapatannya menekan kelayakan sektor ini.",
    };
  }

  return {
    peran: "Calon pelanggan",
    alasan:
      ALASAN_PELANGGAN[kategori] ??
      "Memasok orang ke kawasan stasiun, sehingga menaikkan sisi permintaan pada indeks kelayakan usaha.",
  };
}
