"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { LaporanArea } from "@/types/station";

type Fetched = { id: number | null; data: LaporanArea | null; error: string | null };

/**
 * Area pengamatan Activity di satu stasiun: iklan, tenant, keramaian, fasilitas.
 *
 * Dipakai tiga tempat sekaligus (ringkasan survey di Ikhtisar, katalog
 * Ad-Space, dan tenant per area), jadi datanya diambil sekali per stasiun.
 */
export function useStationAreas(stationId: number | null) {
  const [fetched, setFetched] = useState<Fetched>({ id: null, data: null, error: null });

  useEffect(() => {
    if (stationId === null) return;
    let batal = false;
    apiGet<LaporanArea>(`/stations/${stationId}/areas`)
      .then((data) => {
        if (!batal) setFetched({ id: stationId, data, error: null });
      })
      .catch((err: unknown) => {
        if (!batal)
          setFetched({
            id: stationId,
            data: null,
            error: err instanceof Error ? err.message : "Gagal memuat area",
          });
      });
    return () => {
      batal = true;
    };
  }, [stationId]);

  const siap = fetched.id === stationId;
  return {
    laporan: siap ? fetched.data : null,
    loading: stationId !== null && !siap,
    error: siap ? fetched.error : null,
  };
}
