"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { FeatureCollection } from "geojson";

type Fetched = {
  /** Permintaan mana yang menghasilkan isi di bawah, buat menandai basi. */
  key: string;
  data: FeatureCollection | null;
};

const EMPTY: Fetched = { key: "", data: null };

/**
 * Ambil titik minat yang jatuh di dalam isochrone satu stasiun.
 *
 * Mengembalikan null kalau layernya dimatikan atau belum ada stasiun terpilih —
 * peta memakai null itu sebagai penanda untuk menyembunyikan layernya, jadi
 * tidak perlu bendera terpisah.
 */
export function useStationPois(
  stationId: number | null,
  minutes: number,
  enabled: boolean
): FeatureCollection | null {
  const [fetched, setFetched] = useState<Fetched>(EMPTY);

  const key = !enabled || stationId === null ? "" : `${stationId}:${minutes}`;

  useEffect(() => {
    if (!enabled || stationId === null) return;

    let cancelled = false;
    const current = `${stationId}:${minutes}`;

    apiGet<FeatureCollection>(`/stations/${stationId}/pois?minutes=${minutes}`)
      .then((res) => {
        if (!cancelled) setFetched({ key: current, data: res });
      })
      .catch(() => {
        // Gagal memuat titik bukan hal yang perlu disela ke pengguna: petanya
        // tetap jalan, layernya saja yang tidak muncul.
        if (!cancelled) setFetched({ key: current, data: null });
      });

    return () => {
      cancelled = true;
    };
  }, [stationId, minutes, enabled]);

  return fetched.key === key ? fetched.data : null;
}
