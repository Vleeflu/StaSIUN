"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { FeatureCollection } from "geojson";

type Fetched = {
  key: string;
  data: FeatureCollection | null;
};

const EMPTY: Fetched = { key: "", data: null };

export function useStationIsochrones(
  stationId: number | null,
  enabled: boolean
): FeatureCollection | null {
  const [fetched, setFetched] = useState<Fetched>(EMPTY);

  const key = !enabled || stationId === null ? "" : String(stationId);

  useEffect(() => {
    if (!enabled || stationId === null) return;

    let cancelled = false;
    const current = String(stationId);

    apiGet<FeatureCollection>(`/stations/${stationId}/isochrones`)
      .then((res) => {
        if (!cancelled) setFetched({ key: current, data: res });
      })
      .catch(() => {
        if (!cancelled) setFetched({ key: current, data: null });
      });

    return () => {
      cancelled = true;
    };
  }, [stationId, enabled]);

  return fetched.key === key ? fetched.data : null;
}
