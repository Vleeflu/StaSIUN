import type { Feature, FeatureCollection, Point } from "geojson";

export type StationProps = {
  name: string;
  code: string | null;
  types: string;
  lines: string[];
  primary_line: string | null;
  is_interchange: boolean;
  served: boolean;
  line_key: string;
  kecamatan: string | null;
  address: string | null;
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
