"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { FeatureCollection } from "geojson";
import type { LaporanSponsorship } from "@/types/station";

type Fetched = { kunci: string; data: LaporanSponsorship | null; error: string | null };

/**
 * Peluang Facility Sponsorship satu stasiun, untuk panel.
 *
 * Keluhan yang dibantah query spasial sudah disaring backend, jadi panel tidak
 * perlu tahu aturannya - tetapi jumlah yang tersaring ikut dikirim supaya bisa
 * ditampilkan, bukan disembunyikan.
 */
export function useSponsorship(stationId: number | null) {
  const [fetched, setFetched] = useState<Fetched>({ kunci: "", data: null, error: null });
  const kunci = stationId === null ? "" : String(stationId);

  useEffect(() => {
    if (stationId === null) return;
    let batal = false;
    apiGet<LaporanSponsorship>(`/sponsorship?station_id=${stationId}`)
      .then((data) => {
        if (!batal) setFetched({ kunci: String(stationId), data, error: null });
      })
      .catch((err: unknown) => {
        if (!batal)
          setFetched({
            kunci: String(stationId),
            data: null,
            error: err instanceof Error ? err.message : "Gagal memuat peluang sponsorship",
          });
      });
    return () => {
      batal = true;
    };
  }, [stationId]);

  const siap = fetched.kunci === kunci;
  return {
    laporan: siap ? fetched.data : null,
    loading: stationId !== null && !siap,
    error: siap ? fetched.error : null,
  };
}

/**
 * Penanda keluhan fasilitas untuk seluruh stasiun, sebagai GeoJSON peta.
 *
 * Hanya ditarik saat layernya dinyalakan. Titiknya sedikit (puluhan), jadi
 * tidak perlu per stasiun seperti titik minat.
 */
export function useSponsorshipMarkers(aktif: boolean) {
  const [data, setData] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    if (!aktif) return;
    let batal = false;
    apiGet<FeatureCollection>("/sponsorship?format=geojson")
      .then((res) => {
        if (!batal) setData(res);
      })
      .catch(() => {
        if (!batal) setData(null);
      });
    return () => {
      batal = true;
    };
  }, [aktif]);

  return aktif ? data : null;
}
