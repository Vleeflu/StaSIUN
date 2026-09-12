"use client";

import { useCallback, useState } from "react";

import { apiPost } from "@/lib/api";

export type BobotSepi = { T: number; E: number; A: number; U: number; C: number };

export type BarisSimulasi = {
  peringkat: number;
  stasiun: string;
  sepi: number;
  kelas: string;
  confidence: number;
};

export type HasilSimulasi = {
  cincin_menit: number;
  asal_bobot: string;
  bobot_dipakai: BobotSepi;
  variabel_terukur: number;
  variabel_total: number;
  catatan: string;
  peringkat: BarisSimulasi[];
  stasiun_dipilih: BarisSimulasi | null;
};

/**
 * Hitung ulang peringkat SEPI dengan bobot dan cincin pilihan pengguna.
 *
 * Sengaja TIDAK dijalankan otomatis saat slider bergeser. Tiap panggilan
 * membangun ulang matriks keputusan untuk 45 stasiun, jadi menjalankannya di
 * setiap piksel gerakan slider akan membanjiri backend dengan pekerjaan yang
 * langsung dibuang. Pengguna menekan tombol saat komposisinya sudah pas.
 *
 * Pemisahan itu juga jujur secara makna: menggeser slider adalah menyusun
 * pertanyaan, menekan tombol adalah mengajukannya.
 */
export function useSepiSimulation() {
  const [hasil, setHasil] = useState<HasilSimulasi | null>(null);
  const [memuat, setMemuat] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const jalankan = useCallback(
    async (bobot: BobotSepi, menit: number, stationId: number | null) => {
      setMemuat(true);
      setError(null);
      try {
        const data = await apiPost<HasilSimulasi>("/sepi/simulasi", {
          bobot,
          menit,
          batas: 46,
          station_id: stationId,
        });
        setHasil(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Simulasi gagal");
      } finally {
        setMemuat(false);
      }
    },
    []
  );

  const bersihkan = useCallback(() => {
    setHasil(null);
    setError(null);
  }, []);

  return { hasil, memuat, error, jalankan, bersihkan };
}
