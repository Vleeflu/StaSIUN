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
