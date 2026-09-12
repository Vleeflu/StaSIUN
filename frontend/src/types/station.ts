import type { Feature, FeatureCollection, Point } from "geojson";

export type StationProps = {
  name: string;
  code: string | null;
  types: string[];
  network: string | null;
  lines: string[];
  primary_line: string | null;
  is_interchange: boolean;
  served: boolean;
  line_key: string;
  kecamatan: string | null;
  address: string | null;
  sepi: number | null;
  sepi_rank: number | null;
};

export type StationScore = {
  station_id: number;
  minutes: number;

  /**
   * Jumlah berbobot 0–100, dihitung per stasiun tanpa melihat stasiun lain.
   * Hanya angka ini yang boleh diklasifikasikan ke tiga kelas PRD.
   */
  sepi: number;
  kelas: string;
  /** Kalimat keputusan bisnis dari PRD. Inti gunanya skor, bukan pelengkap. */
  keputusan: string;

  /** Peringkat menurut `sepi`, bukan menurut `topsis`. */
  rank: number;
  /** Jumlah stasiun yang terskor pada pita waktu yang sama. */
  rank_total: number;

  /**
   * Kekokohan peringkat terhadap pilihan pembobotan (ADJUSTMENT 9.30). `null`
   * kalau skor disimpan sebelum analisis sensitivitas ada.
   */
  sensitivity: Sensitivitas | null;

  /**
   * Kedekatan TOPSIS 0–100, dikirim TERPISAH. Nilainya ditentukan oleh himpunan
   * stasiun yang ikut dinilai, jadi ia hanya sah sebagai pembanding relatif dan
   * TIDAK boleh dipakai untuk klasifikasi.
   */
  topsis: number;
  topsis_catatan: string;

  /**
   * Berapa dari lima variabel yang benar-benar terukur, dan keyakinan yang
   * mengikutinya. Skor 3 variabel TIDAK sebanding dengan skor 5 variabel, jadi
   * keduanya wajib ikut ditampilkan.
   */
  confidence: number;
  variabel_terpakai: number;
  variabel_total: number;

  /**
   * Nilai tiap variabel, sudah ternormalisasi 0–1 — BUKAN satuan aslinya.
   * `null` berarti variabelnya belum diukur sama sekali (E dan C menunggu
   * survey Activity), dan itu harus tampil berbeda dari nilai rendah.
   */
  components: {
    T: number | null;
    E: number | null;
    A: number | null;
    U: number | null;
    C: number | null;
  };
  detail: {
    line_count: number;
    halte_count: number;
    other_mode_count: number;
    area_km2: number;
  };

  /**
   * Volume penumpang harian. KONTEKS, bukan komponen skor — cakupannya baru 10
   * dari 46 stasiun, di bawah ambang 70% untuk dipakai sebagai indikator T.
   * `null` untuk stasiun yang datanya belum ada.
   */
  passenger_volume: {
    per_day: number;
    period: string;
    source: string;
    catatan: string;
  } | null;
};

export type Sensitivitas = {
  peringkat_resmi: number;
  peringkat_per_skema: Record<string, number>;
  kelas_per_skema: Record<string, string>;
  peringkat_min: number;
  peringkat_maks: number;
  kelas_sama_di: number;
  jumlah_skema: number;
  mc_p05: number;
  mc_median: number;
  mc_p95: number;
  /** Peluang masuk `n_besar` saat bobot diacak (Monte Carlo). */
  peluang_n_besar: number;
  n_besar: number;
  /** Masuk `n_besar` di SEMUA skema deterministik. */
  kokoh_n_besar: boolean;
  jumlah_undian: number;
};

/** Median keramaian satu rentang waktu, dinormalisasi 0–1 (PRD hal. 10). */
export type ProfilJendela = {
  normal: number;
  /** Padanan skala 1–5, hanya untuk dibaca. */
  setara_1_5: number;
  jumlah_penilaian: number;
} | null;

export type ProfilKeramaian = {
  pagi: ProfilJendela;
  siang: ProfilJendela;
  sore: ProfilJendela;
};

/** Satu area pengamatan: kelompok titik Activity yang berdekatan. */
export type AreaStasiun = {
  id: string;
  nama: string;
  judul_lain: string[];
  jumlah_titik: number;
  dari_survey_tim: number;
  jarak_m: number;
  di_stasiun: boolean;
  lon: number;
  lat: number;
  foto: string[];
  iklan: {
    total: number;
    kosong: number;
    per_jenis: Array<{ jenis: string; terpakai: number; kosong: number }>;
    kutipan: string[];
  };
  tenant: Array<{ nama: string; kategori: string; status: string }>;
  keramaian: ProfilKeramaian;
  /**
   * Watak waktu singgah DI AREA INI, bukan di stasiunnya.
   *
   * Satu stasiun bisa punya peron yang cuma dilewati dan concourse tempat orang
   * menunggu; rekomendasi format iklan baru berguna kalau dibedakan per titik.
   */
  waktu_singgah: {
    label: string;
    alasan: string;
    sinyal_lama: number;
    sinyal_sebentar: number;
  };
  narasumber: string[];
  fasilitas: Array<{ jenis: string; ringkasan: string; sentimen: number | null }>;
};

export type LaporanArea = {
  station_id: number;
  batas_area_stasiun_m: number;
  ringkasan: {
    titik_activity: number;
    titik_berisi: number;
    keramaian: ProfilKeramaian;
    jumlah_penilaian_keramaian: number;
    media_iklan: number | null;
    media_iklan_kosong: number | null;
    tenant_tercatat: number;
    fasilitas_positif: number;
    fasilitas_negatif: number;
    arketipe: string | null;
  };
  areas: AreaStasiun[];
};

/** Satu keluhan fasilitas yang layak jadi peluang CSR (F6-2). */
export type PeluangSponsorship = {
  id: number;
  station_id: number;
  stasiun: string;
  jenis: string;
  keluhan: string;
  sentimen: number | null;
  lokasi: {
    lon: number | null;
    lat: number | null;
    jarak_m: number | null;
    nama_titik: string | null;
  };
  /**
   * Hasil uji klaim ke data spasial. `tervalidasi` = diuji dan cocok;
   * `pengamatan langsung` = tidak ada data yang bisa mengujinya. Yang dibantah
   * data tidak pernah sampai ke sini — backend sudah membuangnya.
   */
  validasi: {
    status: string;
    uji: string | null;
    temuan: string | null;
    catatan: string;
  };
  /**
   * Selalu terisi: keluhan yang tidak punya bentuk sponsorship masuk akal
   * sudah disaring backend, bukan ditampilkan dengan usulan kosong.
   */
  usulan: {
    bentuk: string;
    dasar: string;
    /** "aset stasiun" atau "di luar lahan stasiun" — menentukan siapa yang berwenang. */
    kewenangan: string;
    catatan_kewenangan: string;
  };
  /** Berapa laporan berdekatan yang dilebur jadi satu peluang ini. */
  jumlah_laporan: number;
};

export type LaporanSponsorship = {
  minutes: number;
  station_id: number | null;
  jumlah: number;
  dibantah_validasi_spasial: number;
  bukan_keluhan_fasilitas: number;
  di_luar_lingkup_krl: number;
  tanpa_bentuk_sponsorship: number;
  laporan_digabung: number;
  terlalu_jauh_dari_stasiun: number;
  catatan: string;
  peluang: PeluangSponsorship[];
};

/** Tombol yang menyertai jawaban asisten, disusun backend dari alat yang dipanggil. */
export type AksiAsisten = {
  jenis: "buka_stasiun" | "bandingkan" | "simulasi";
  label: string;
  station_id?: number | null;
  station_ids?: number[] | null;
  tab?: string | null;
  bobot?: Record<string, number> | null;
};

/** Satu kategori usaha beserta Tenant Survival Index-nya di satu stasiun. */
export type TenantCategory = {
  category: string;
  label: string;
  tsi: number;
  rank: number;
  /** Titik ekonomi dan urban di dalam isochrone: calon pelanggan. */
  demand: number;
  /** Pengali arus lewat, 1,0 sampai 2,0, dari komponen T. */
  connectivity: number;
  /** Pesaing sejenis yang sudah ada. */
  supply: number;
  /** Calon pelanggan per pesaing, pesaingnya sudah ditambah satu. */
  headroom: number;
};

export type TenantReport = {
  station_id: number;
  minutes: number;
  station_count: number;
  categories: TenantCategory[];
};

/** Satu ukuran komposisi kawasan: luas tanah ATAU luas lantai terbangun. */
export type UkuranKawasan = {
  label: string;
  porsi: Record<string, number> | null;
  luas_m2: Record<string, number> | null;
  kelas_terbesar: string | null;
  dominasi: number | null;
  /** Apa yang dinyatakan angka ini - dan apa yang tidak. */
  arti?: string | null;
  /** Bias yang sudah diketahui dan sengaja tidak disembunyikan. */
  bias_diketahui?: string | null;
  cakupan_tag_lantai?: number | null;
  sumber: string;
  sumber_url: string | null;
  diakses: string | null;
};

/**
 * Komposisi kawasan menurut KEDUA ukuran sekaligus.
 *
 * Tidak ada satu angka yang dinyatakan sebagai kebenaran: luas tanah
 * mengecilkan menara, luas lantai mengecilkan permukiman padat, dan keduanya
 * disajikan sebagai kurung. `sepakat` false bukan kegagalan - ia berarti
 * tanahnya didominasi satu fungsi sementara ruang terbangunnya fungsi lain.
 */
export type KawasanPaparan = {
  per_ukuran: Record<string, UkuranKawasan>;
  sepakat: boolean | null;
  catatan: string;
  peringatan: string;
};

export type ProfilPaparan = {
  station_id: number;
  stasiun: string;
  kawasan: KawasanPaparan | null;
  /**
   * Keramaian per rentang waktu. `skala_min`/`skala_maks` ikut dikirim karena
   * tidak semua penilaian memakai 1-5: angka 3 pada skala 1-3 berarti paling
   * ramai, sedangkan pada skala 1-5 cuma sedang. `arti` sudah diterjemahkan di
   * backend supaya tampilan tidak perlu menebak sendiri.
   */
  keramaian: Record<
    string,
    {
      nilai: number;
      skala_min: number;
      skala_maks: number;
      arti: string;
      jumlah_penilaian: number;
    }
  >;
  /**
   * Kelompok pengunjung, DISIMPULKAN dari peruntukan lahan sekitar yang
   * disilangkan dengan pola keramaian — bukan dari penilaian terhadap orang
   * yang melintas. `dasar` menyimpan alasan penarikannya.
   */
  audiens: { kelompok: string; dasar: string; porsi_kawasan: number }[];
  waktu_singgah: {
    label: string;
    alasan: string;
    porsi_singgah_lama?: number;
    sinyal_lama: number;
    sinyal_sebentar: number;
    kalimat_penyangkal?: number;
  };
  format_iklan_disarankan: { bentuk: string | null; alasan: string; catatan?: string | null };
  dasar: {
    jumlah_narasi: number;
    jumlah_penilaian_keramaian: number;
    puncak_keramaian: string | null;
    metode: string;
    catatan_privasi: string;
  };
};

export type StatusNaming = {
  station_id: number;
  stasiun: string;
  /** Hak penamaan hanya diperjualbelikan di MRT dan LRT, tidak di KAI Commuter. */
  dalam_lingkup: boolean;
  status: {
    bersponsor: boolean;
    sponsor: string | null;
    nama_dasar: string;
    jaringan: string;
  } | null;
  pembanding: { total: number; bersponsor: number; belum: number; sponsor: string[] };
  catatan: string;
  /** Selalu null sampai ada pembanding transaksi nyata - lihat alasannya. */
  nilai_kontrak: number | null;
  alasan_nilai_kosong: string;
  selisih_daftar: string[];
};

export type StationFeature = Feature<Point, StationProps>;

export type StationCollection = FeatureCollection<Point, StationProps>;

export function parseLines(value: unknown): string[] {
  if (Array.isArray(value)) return value as string[];
  if (typeof value === "string") {
    try {
      const parsed: unknown = JSON.parse(value);
      return Array.isArray(parsed) ? (parsed as string[]) : [];
    } catch {
      return [];
    }
  }
  return [];
}
