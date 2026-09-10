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
  sepi: number;
  rank: number;
  components: {
    T: number;
    E: number;
    A: number;
    U: number;
    C: number;
  };
  detail: {
    line_count: number;
    halte_count: number;
    other_mode_count: number;
    area_km2: number;
  };
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
