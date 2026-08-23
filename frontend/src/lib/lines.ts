// Warna dan nama tiap lin, mengikuti peta rute resmi KAI Commuter.
export const LINE_COLOR: Record<string, string> = {
  B: "#c90025",
  C: "#00a4e4",
  R: "#8dc63f",
  T: "#f68b1f",
  TP: "#fd6bc3",
  A: "#1b3d8f",
};

export const LINE_NAME: Record<string, string> = {
  B: "Bogor",
  C: "Lingkar Cikarang",
  R: "Rangkasbitung",
  T: "Tangerang",
  TP: "Tanjung Priok",
  A: "Bandara",
};

export const FALLBACK_COLOR = "#64748b";

/** Ubah daftar kode lin jadi teks yang enak dibaca, misalnya "Bogor, Bandara". */
export function lineLabel(codes: string[]): string {
  return codes.map((code) => LINE_NAME[code] ?? code).join(", ");
}
