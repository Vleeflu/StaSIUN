"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import type { FeatureCollection } from "geojson";

/**
 * Garis rute tiap line KRL, sekali ambil untuk seumur halaman.
 *
 * Bentuknya tidak pernah berubah oleh pilihan pengguna - yang berubah hanya
 * line mana yang ditampilkan, dan itu disaring di peta. Jadi tidak ada alasan
 * mengambilnya ulang saat filter digeser.
 */
export function useLineRoutes(): FeatureCollection | null {
  const [data, setData] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    let batal = false;
    apiGet<FeatureCollection>("/lines")
      .then((d) => !batal && setData(d))
      .catch(() => {
        /* Peta tetap berguna tanpa garis rute. */
      });
    return () => {
      batal = true;
    };
  }, []);

  return data;
}
