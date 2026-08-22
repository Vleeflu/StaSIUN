"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { StationCollection, StationFeature } from "@/types/station";

type State = {
  data: StationCollection | null;
  loading: boolean;
  error: string | null;
};

type UseStationsResult = State & {
  stations: StationFeature[];
};

const STATE_AWAL: State = { data: null, loading: true, error: null };

/**
 * Mengambil data stasiun dari backend.
 * Beri `serviceType` untuk menyaring per jenis layanan (mis. "KERETA API"),
 * atau biarkan kosong untuk mengambil semua stasiun.
 *
 * State hanya diperbarui dari dalam callback async, tidak pernah sinkron di
 * badan effect, agar tidak memicu render berantai.
 */
export function useStations(serviceType?: string): UseStationsResult {
  const [state, setState] = useState<State>(STATE_AWAL);

  useEffect(() => {
    let cancelled = false;

    const path = serviceType
      ? `/stations?type=${encodeURIComponent(serviceType)}`
      : "/stations";

    apiGet<StationCollection>(path)
      .then((res) => {
        if (!cancelled) setState({ data: res, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          data: null,
          loading: false,
          error:
            err instanceof Error
              ? err.message
              : "Gagal memuat data stasiun dari server",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [serviceType]);

  return { ...state, stations: state.data?.features ?? [] };
}
