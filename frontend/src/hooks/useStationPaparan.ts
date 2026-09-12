"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { ProfilPaparan } from "@/types/station";

type Fetched = { id: number | null; data: ProfilPaparan | null; error: string | null };

/**
 * Profil paparan satu stasiun - dasar tab Ad-Space (PRD bagian h).
 *
 * Menjawab "siapa yang MELINTAS di sini", bukan "siapa yang berbelanja".
 * Isinya komposisi kawasan menurut dua ukuran, pola keramaian per rentang
 * waktu, kelompok pengunjung yang disebut narasumber, dan watak waktu singgah.
 */
export function useStationPaparan(stationId: number | null) {
  const [fetched, setFetched] = useState<Fetched>({ id: null, data: null, error: null });

  useEffect(() => {
    if (stationId === null) return;
    let batal = false;
    apiGet<ProfilPaparan>(`/stations/${stationId}/paparan`)
      .then((data) => {
        if (!batal) setFetched({ id: stationId, data, error: null });
      })
      .catch((err: unknown) => {
        if (!batal)
          setFetched({
            id: stationId,
            data: null,
            error: err instanceof Error ? err.message : "Gagal memuat profil paparan",
          });
      });
    return () => {
      batal = true;
    };
  }, [stationId]);

  const siap = fetched.id === stationId;
  return {
    paparan: siap ? fetched.data : null,
    loading: stationId !== null && !siap,
    error: siap ? fetched.error : null,
  };
}
