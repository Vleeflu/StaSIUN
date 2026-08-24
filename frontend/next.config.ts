import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained .next/standalone bundle for a slim Docker runtime.
  output: "standalone",
};

export default nextConfig;
