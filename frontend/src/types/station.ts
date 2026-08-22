import type { Feature, FeatureCollection, Point } from "geojson";

export type StationProps = {
  name: string;
  types: string;
  primary_type: string;
  kecamatan: string | null;
  address: string | null;
};

export type StationFeature = Feature<Point, StationProps>;

export type StationCollection = FeatureCollection<Point, StationProps>;
