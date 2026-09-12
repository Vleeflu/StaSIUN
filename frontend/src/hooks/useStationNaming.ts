"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { StatusNaming } from "@/types/station";

type Fetched = { id: number | null; data: StatusNaming | null; error: string | null };

/**
 * Status hak penamaan satu stasiun beserta kelompok pembandingnya.
 *
 * Nilai kontrak dalam rupiah sengaja tidak ada di sini - ia butuh pembanding
 * transaksi nyata yang belum tersedia, dan endpoint-nya mengirim alasannya
 * apa adanya supaya panel bisa menjelaskan, bukan sekadar mengosongkan.
 */
export function useStationNaming(stationId: number | null) {
  const [fetched, setFetched] = useState<Fetched>({ id: null, data: null, error: null });

  useEffect(() => {
    if (stationId === null) return;
    let batal = false;
    apiGet<StatusNaming>(`/stations/${stationId}/naming`)
      .then((data) => {
        if (!batal) setFetched({ id: stationId, data, error: null });
      })
      .catch((err: unknown) => {
        if (!batal)
          setFetched({
            id: stationId,
            data: null,
            error: err instanceof Error ? err.message : "Gagal memuat status naming",
          });
      });
    return () => {
      batal = true;
    };
  }, [stationId]);

  const siap = fetched.id === stationId;
  return {
    naming: siap ? fetched.data : null,
    loading: stationId !== null && !siap,
    error: siap ? fetched.error : null,
  };
}
