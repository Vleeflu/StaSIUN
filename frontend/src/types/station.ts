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
  narasumber: string[];
  fasilitas: Array<{ jenis: string; ringkasan: string; sentimen: number | null }>;
};

export type LaporanArea = {
  station_id: number;
  eps_meter: number;
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
