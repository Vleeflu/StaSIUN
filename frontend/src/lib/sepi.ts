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
  format: (value: number) => string;
};

export const SEPI_COMPONENTS: Component[] = [
  {
    key: "T",
    label: "Transportasi",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  { key: "E", label: "Ekonomi", format: (v) => `${Math.round(v)} titik` },
  { key: "A", label: "Aksesibilitas", format: (v) => `${v.toFixed(2)} km²` },
  { key: "U", label: "Urban", format: (v) => `${Math.round(v)} titik` },
  { key: "C", label: "Komersial", format: (v) => `${Math.round(v)} titik` },
];

export function componentShares(
  components: StationScore["components"]
): Record<string, number> {
  const scaled: Record<string, number> = {
    T: components.T,
    E: components.E,
    A: components.A,
    U: components.U,
    C: components.C,
  };

  const values = Object.values(scaled);
  const highest = Math.max(...values);

  if (highest <= 0) {
    return Object.fromEntries(Object.keys(scaled).map((k) => [k, 0]));
  }

  return Object.fromEntries(
    Object.entries(scaled).map(([key, value]) => [key, value / highest])
  );
}
