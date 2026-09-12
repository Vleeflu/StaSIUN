"use client";

import { useEffect, useState } from "react";

import type { AreaStasiun, TenantCategory } from "@/types/station";

/**
 * Katalog usaha yang sudah beroperasi, dikelompokkan per titik survei.
 *
 * Terpisah dari `KatalogModal` (ruang iklan dan sponsorship fasilitas) karena
 * pembacanya berbeda: yang membuka ini calon penyewa yang ingin tahu siapa
 * saja yang sudah berjualan di sana, bukan pengiklan yang mencari ruang.
 * Menggabungkan keduanya dalam satu halaman timbul akan memaksa keduanya
 * melewati daftar yang bukan urusannya.
 *
 * Dikelompokkan per titik, bukan satu daftar panjang - "tiga kedai di koridor
 * peron 1" adalah informasi yang berbeda dari "tiga kedai di stasiun ini".
 */
export default function TenantModal({
  stasiun,
  areas,
  kategori,
  onClose,
}: {
  stasiun: string;
  areas: AreaStasiun[];
  kategori: TenantCategory[];
  onClose: () => void;
}) {
  const [saring, setSaring] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const berisi = areas.filter((a) => a.tenant.length > 0);
  const semuaKategori = Array.from(
    new Set(berisi.flatMap((a) => a.tenant.map((t) => t.kategori)))
  ).sort();

  const tampil = saring
    ? berisi
        .map((a) => ({ ...a, tenant: a.tenant.filter((t) => t.kategori === saring) }))
        .filter((a) => a.tenant.length > 0)
    : berisi;

  const jumlah = tampil.reduce((n, a) => n + a.tenant.length, 0);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Usaha di ${stasiun}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-3xl flex-col border border-ink bg-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hair p-4">
          <div className="min-w-0">
            <p className="label-caps text-accent">Usaha yang sudah beroperasi</p>
            <h2 className="mt-1 text-xl font-bold leading-tight tracking-[-0.01em]">
              {stasiun}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup katalog usaha"
            className="shrink-0 border border-hair px-2 py-1 text-sm leading-none text-ink-soft hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </header>

        <div className="shrink-0 border-b border-hair px-4 py-2">
          <div className="flex flex-wrap gap-1">
            <button
              type="button"
              onClick={() => setSaring(null)}
              className={`border px-2 py-0.5 text-[11px] ${
                saring === null
                  ? "border-accent text-accent"
                  : "border-hair text-muted hover:border-ink hover:text-ink"
              }`}
            >
              Semua
            </button>
            {semuaKategori.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setSaring(k)}
                className={`border px-2 py-0.5 text-[11px] ${
                  saring === k
                    ? "border-accent text-accent"
                    : "border-hair text-muted hover:border-ink hover:text-ink"
                }`}
              >
                {k}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <p className="mb-3 text-xs leading-relaxed text-ink-soft">
            {jumlah} usaha tercatat di {tampil.length} titik survei
            {saring && ` untuk kategori ${saring}`}. Daftar ini hasil pengamatan
            langsung surveyor di lapangan, dan{" "}
            <strong className="text-ink">tidak</strong> ikut dihitung sebagai
            pesaing pada Indeks Kelayakan Usaha — indeks itu memakai lajur data
            pemetaan yang kategorinya seragam untuk seluruh 45 stasiun,
            sedangkan kategori di daftar ini ditulis bebas oleh surveyor.
          </p>

          {tampil.length === 0 ? (
            <p className="text-xs text-muted">
              Tidak ada usaha tercatat untuk saringan ini.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {tampil.map((a) => (
                <li key={a.id} className="border border-hair p-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <h3 className="min-w-0 text-sm font-semibold leading-snug text-ink">
                      {a.nama}
                    </h3>
                    <span className="label-caps shrink-0 text-[9px] text-muted">
                      {a.di_stasiun ? "di dalam stasiun" : `${a.jarak_m} m dari stasiun`}
                    </span>
                  </div>
                  <ul className="mt-2 flex flex-col gap-1">
                    {a.tenant.map((t, i) => (
                      <li
                        key={`${a.id}-${i}`}
                        className="flex items-baseline justify-between gap-2 text-[11px]"
                      >
                        <span className="min-w-0 text-ink-soft">{t.nama}</span>
                        <span className="shrink-0 text-muted">{t.kategori}</span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}

          {kategori.length > 0 && (
            <p className="mt-4 border-t border-canvas pt-3 text-[10px] leading-relaxed text-muted">
              Sektor yang diskor kelayakannya:{" "}
              {kategori.map((k) => k.label).join(", ")}. Usaha di luar sektor
              tersebut tetap tercatat di daftar ini dan tetap dihitung sebagai
              pesaing, hanya saja belum punya indeks kelayakannya sendiri.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
