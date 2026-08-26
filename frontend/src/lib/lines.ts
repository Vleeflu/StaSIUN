// Warna dan nama tiap lin, mengikuti peta rute resmi KAI Commuter.
export const LINE_COLOR: Record<string, string> = {
  B: "#c90025",
  C: "#00a4e4",
  R: "#8dc63f",
  T: "#f68b1f",
  TP: "#fd6bc3",
  A: "#1b3d8f",
  // Moda non-KRL diwarnai per jaringan karena tidak memakai penomoran lin.
  "MRT Jakarta": "#7b3fa0",
  "LRT Jabodebek": "#00897b",
  "LRT Jakarta": "#546e7a",
  Whoosh: "#37474f",
};

export const LINE_NAME: Record<string, string> = {
  B: "Bogor",
  C: "Lingkar Cikarang",
  R: "Rangkasbitung",
  T: "Tangerang",
  TP: "Tanjung Priok",
  A: "Bandara",
  "MRT Jakarta": "MRT Jakarta",
  "LRT Jabodebek": "LRT Jabodebek",
  "LRT Jakarta": "LRT Jakarta",
  Whoosh: "Whoosh",
};

/** Urutan lin di panel filter, mengikuti urutan peta rute resmi. */
export const KRL_LINES = ["B", "C", "R", "T", "TP", "A"] as const;

// Versi pendek buat chip filter, supaya tidak melebar di panel yang sempit.
const LINE_SHORT: Record<string, string> = {
  B: "Bogor",
  C: "Cikarang",
  R: "Rangkasbitung",
  T: "Tangerang",
  TP: "Tanjung Priok",
  A: "KA Bandara",
};

export const FALLBACK_COLOR = "#64748b";

export function lineColor(code: string): string {
  return LINE_COLOR[code] ?? FALLBACK_COLOR;
}

/** Terang relatif sebuah warna hex, rumus WCAG. */
function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "");
  const channels = [0, 2, 4].map(
    (i) => parseInt(clean.slice(i, i + 2), 16) / 255
  );

  const linear = (c: number) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;

  const [r, g, b] = channels.map(linear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Warna teks di atas badge lin. Hijau Rangkasbitung, oranye Tangerang, dan
 * merah muda Tanjung Priok terlalu terang buat teks putih — kontrasnya cuma
 * sekitar 2,5:1. Dihitung, bukan ditebak satu-satu.
 */
export function lineTextColor(code: string): string {
  return relativeLuminance(lineColor(code)) > 0.35 ? "#201e1d" : "#ffffff";
}

/** Nama pendek buat chip filter, misalnya "Cikarang". */
export function shortLabel(code: string): string {
  return LINE_SHORT[code] ?? LINE_NAME[code] ?? code;
}

/** Teks badge di panel stasiun, misalnya "Lin Bogor" atau "KA Bandara". */
export function badgeLabel(code: string): string {
  if (code === "A") return "KA Bandara";
  const short = LINE_SHORT[code];
  return short ? `Lin ${short}` : (LINE_NAME[code] ?? code);
}

/** Ubah daftar kode lin jadi teks yang enak dibaca, misalnya "Bogor, Bandara". */
export function lineLabel(codes: string[]): string {
  return codes.map((code) => LINE_NAME[code] ?? code).join(", ");
}
