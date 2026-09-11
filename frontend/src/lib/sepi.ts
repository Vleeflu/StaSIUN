import type { StationScore } from "@/types/station";

const RAMP: Array<{ stop: number; color: string }> = [
  { stop: 0, color: "#e8e4e2" },
  { stop: 25, color: "#f6c3b6" },
  { stop: 50, color: "#f2846b" },
  { stop: 75, color: "#ec3013" },
  { stop: 100, color: "#a41c07" },
];

export const SEPI_RAMP_EXPRESSION = RAMP.flatMap((s) => [s.stop, s.color]);

export function sepiColor(score: number | null): string {
  if (score === null) return "#c9c4c1";

  const clamped = Math.min(100, Math.max(0, score));
  let lower = RAMP[0];
  let upper = RAMP[RAMP.length - 1];

  for (let i = 0; i < RAMP.length - 1; i += 1) {
    if (clamped >= RAMP[i].stop && clamped <= RAMP[i + 1].stop) {
      lower = RAMP[i];
      upper = RAMP[i + 1];
      break;
    }
  }

  const span = upper.stop - lower.stop;
  const ratio = span === 0 ? 0 : (clamped - lower.stop) / span;

  return mix(lower.color, upper.color, ratio);
}

function mix(from: string, to: string, ratio: number): string {
  const parse = (hex: string) =>
    [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

  const [r1, g1, b1] = parse(from);
  const [r2, g2, b2] = parse(to);
  const blend = (a: number, b: number) => Math.round(a + (b - a) * ratio);

  return `#${[blend(r1, r2), blend(g1, g2), blend(b1, b2)]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

type Component = {
  key: keyof StationScore["components"];
  label: string;
  /** Apa yang sebenarnya diukur, untuk ditampilkan saat nilainya kosong. */
  sumber: string;
};

/**
 * Kelima nilai komponen sudah TERNORMALISASI 0–1, bukan satuan aslinya.
 *
 * Versi sebelumnya memformat A sebagai `km²` dan U sebagai `titik`. Itu keliru
 * sejak variabelnya jadi gabungan beberapa indikator: A = luas + Permeability
 * Index, U = cacah + keberagaman + pembangkit perjalanan. Akibatnya nilai 0,87
 * tampil sebagai "0.87 km²" dan 0,92 tampil sebagai "1 titik" — angka benar,
 * satuan mengarang. Angka mentahnya tetap bisa dilihat di bagian "Isi jangkauan
 * jalan kaki"; di sini yang ditampilkan proporsinya.
 */
export const SEPI_COMPONENTS: Component[] = [
  { key: "T", label: "Transportasi", sumber: "volume, moda, line, keramaian" },
  { key: "E", label: "Ekonomi", sumber: "survey Activity" },
  { key: "A", label: "Aksesibilitas", sumber: "luas isochrone, permeability" },
  { key: "U", label: "Urban", sumber: "titik minat, keberagaman" },
  { key: "C", label: "Komersial", sumber: "survey Activity" },
];

/** Tampilkan nilai komponen apa adanya: 0–1 dua desimal, atau tanda belum diukur. */
export function formatKomponen(value: number | null | undefined): string {
  if (value === null || value === undefined) return "belum diukur";
  return value.toFixed(2);
}

/**
 * Panjang bar tiap komponen, relatif terhadap komponen tertinggi yang TERUKUR.
 *
 * Variabel yang belum diukur dikembalikan `null`, bukan 0. Bedanya menentukan:
 * bar sepanjang nol berarti "nilainya rendah", sedangkan yang kita maksud
 * adalah "belum ada datanya" — dua hal yang tidak boleh terlihat sama.
 *
 * Versi sebelumnya memanggil `Math.max` atas nilai yang kini bisa `null`,
 * menghasilkan `NaN` dan membuat seluruh diagram lenyap tanpa pesan apa pun.
 */
export function componentShares(
  components: StationScore["components"]
): Record<string, number | null> {
  const entries = Object.entries(components) as Array<
    [string, number | null]
  >;

  const terukur = entries
    .map(([, v]) => v)
    .filter((v): v is number => v !== null && Number.isFinite(v));

  const tertinggi = terukur.length ? Math.max(...terukur) : 0;

  return Object.fromEntries(
    entries.map(([key, value]) => {
      if (value === null || !Number.isFinite(value)) return [key, null];
      return [key, tertinggi > 0 ? value / tertinggi : 0];
    })
  );
}

/** Label dan nada untuk metadata keyakinan (F5-4). */
export function confidenceLabel(
  terpakai: number,
  total: number
): { teks: string; nada: "rendah" | "sedang" | "penuh" } {
  if (terpakai >= total) return { teks: "Lengkap", nada: "penuh" };
  if (terpakai >= total - 1) return { teks: "Hampir lengkap", nada: "sedang" };
  return { teks: "Terbatas", nada: "rendah" };
}
