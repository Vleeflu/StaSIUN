"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { TenantReport } from "@/types/station";

type Result = {
  report: TenantReport | null;
  loading: boolean;
  error: string | null;
};

type Fetched = {
  /** Permintaan mana yang menghasilkan isi di bawah, buat menandai basi. */
  key: string;
  report: TenantReport | null;
  error: string | null;
};

const EMPTY: Fetched = { key: "", report: null, error: null };

/**
 * Ambil Tenant Survival Index tiap kategori usaha untuk satu stasiun.
 *
 * Polanya sama dengan hook skor: state cuma disentuh dari callback async, dan
 * status memuat diturunkan saat render dengan membandingkan permintaan yang
 * diminta dan yang sudah terjawab.
 */
export function useStationTenants(stationId: number | null, minutes = 10): Result {
  const [fetched, setFetched] = useState<Fetched>(EMPTY);

  const key = stationId === null ? "" : `${stationId}:${minutes}`;

  useEffect(() => {
    if (stationId === null) return;

    let cancelled = false;
    const current = `${stationId}:${minutes}`;

    apiGet<TenantReport>(`/stations/${stationId}/tenants?minutes=${minutes}`)
      .then((res) => {
        if (!cancelled) setFetched({ key: current, report: res, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setFetched({
          key: current,
          report: null,
          error: err instanceof Error ? err.message : "Gagal memuat skor tenant",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [stationId, minutes]);

  const settled = fetched.key === key;

  return {
    report: settled ? fetched.report : null,
    loading: stationId !== null && !settled,
    error: settled ? fetched.error : null,
  };
}
