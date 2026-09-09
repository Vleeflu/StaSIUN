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
  /** Skor SEPI 0-100 dan peringkatnya. Null selama belum dihitung. */
  sepi: number | null;
  sepi_rank: number | null;
};

/** Rincian skor satu stasiun, dari /stations/{id}/score. */
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

export type StationFeature = Feature<Point, StationProps>;

export type StationCollection = FeatureCollection<Point, StationProps>;

/**
 * `lines` datangnya array kalau feature-nya dari state React, tapi string JSON
 * kalau dibaca dari event klik MapLibre — worker-nya menyerialisasi properti
 * non-primitif. Fungsi ini merapikan keduanya jadi array.
 */
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
