"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState("menghubungi backend...");

  useEffect(() => {
    apiGet<{ status: string; database: string }>("/health")
      .then((d) => setStatus(`backend: ${d.status} · database: ${d.database}`))
      .catch((e: Error) => setStatus(`error: ${e.message}`));
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center font-mono">
      {status}
    </main>
  );
}