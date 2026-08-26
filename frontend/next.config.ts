import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained .next/standalone bundle for a slim Docker runtime.
  output: "standalone",

  // Lencana Next.js hanya muncul saat dev, dan tempat bawaannya kiri bawah —
  // persis menimpa tombol zoom peta. Ganti false jadi { position: "top-right" }
  // kalau suatu saat mau dimunculkan lagi.
  devIndicators: false,
};

export default nextConfig;
