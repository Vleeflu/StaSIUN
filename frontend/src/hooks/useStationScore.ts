"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { StationScore } from "@/types/station";

type Result = {
  score: StationScore | null;
  loading: boolean;
  error: string | null;
};

type Fetched = {
  key: string;
  score: StationScore | null;
  error: string | null;
};

const EMPTY: Fetched = { key: "", score: null, error: null };

export function useStationScore(stationId: number | null, minutes = 10): Result {
  const [fetched, setFetched] = useState<Fetched>(EMPTY);

  const key = stationId === null ? "" : `${stationId}:${minutes}`;

  useEffect(() => {
    if (stationId === null) return;

    let cancelled = false;
    const current = `${stationId}:${minutes}`;

    apiGet<StationScore>(`/stations/${stationId}/score?minutes=${minutes}`)
      .then((res) => {
        if (!cancelled) setFetched({ key: current, score: res, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : "Gagal memuat skor";
        setFetched({
          key: current,
          score: null,
          error: message.includes("belum dihitung") ? null : message,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [stationId, minutes]);

  const settled = fetched.key === key;

  return {
    score: settled ? fetched.score : null,
    loading: stationId !== null && !settled,
    error: settled ? fetched.error : null,
  };
}
