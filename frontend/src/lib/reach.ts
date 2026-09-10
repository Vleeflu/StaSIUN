/** Pita jangkauan jalan kaki: pilihannya, warnanya, dan turunannya. */

/** Satu pita, atau ketiganya sekaligus. */
export type ReachBand = 5 | 10 | 15 | "all";

export const REACH_BANDS = [
  { minutes: 5 as const, opacity: 0.18 },
  { minutes: 10 as const, opacity: 0.12 },
  { minutes: 15 as const, opacity: 0.07 },
];

export const REACH_CHOICES: ReachBand[] = [5, 10, 15, "all"];

/** Menit yang poligonnya digambar. */
export function bandMinutes(band: ReachBand): number[] {
  return band === "all" ? REACH_BANDS.map((b) => b.minutes) : [band];
}

/**
 * Pita yang titik minatnya diambil — selalu yang terluar dari yang digambar.
 *
 * Kalau "Semua" dipilih, poligonnya tampil bertiga; titik yang berhenti di 10
 * menit bikin cincin terluar kelihatan kosong seolah datanya hilang. Untuk
 * pilihan pita tunggal, titiknya persis sepita dengan poligonnya, jadi
 * jumlahnya cocok dengan angka di panel stasiun.
 */
export function reachPoiMinutes(band: ReachBand): number {
  return band === "all" ? 15 : band;
}

export function bandLabel(band: ReachBand): string {
  return band === "all" ? "Semua" : `${band}′`;
}

/** Opasitas isian buat contoh warna di legenda. */
export function bandOpacity(band: ReachBand): number {
  return REACH_BANDS.find((b) => b.minutes === band)?.opacity ?? 0.12;
}
