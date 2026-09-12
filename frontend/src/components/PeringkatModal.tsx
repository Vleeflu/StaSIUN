"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";

type Baris = {
  peringkat: number;
  stasiun: string;
  nilai: number;
  confidence?: number;
  kelas?: string;
  pesaing?: number;
  /** Skor sesudah dipotong ketidakpastian; inilah dasar urutannya. */
  nilai_bawah?: number;
};

type Daftar = {
  minutes: number;
  sepi: Baris[];
  paparan: Baris[];
  tenant: Record<string, Baris[]>;
  catatan: string;
};

/**
 * Seluruh peringkat dalam satu halaman, dengan stasiun yang sedang dibuka
 * disorot di tiap daftar.
 *
 * Selama ini pembaca hanya melihat satu peringkat pada satu waktu - "#23 dari
 * 45" di panel SEPI - tanpa cara tahu bahwa stasiun yang sama menempati
 * peringkat 2 untuk paparan iklan. Padahal perbedaan itu bukan kebingungan
 * yang harus disembunyikan; ia justru inti pesan produknya: pertanyaan yang
 * berbeda menuntut ukuran yang berbeda.
 */
export default function PeringkatModal({
  stasiunSorot,
  daftarAwal = "sepi",
  onClose,
}: {
  stasiunSorot: string | null;
  daftarAwal?: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<Daftar | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [pilih, setPilih] = useState(daftarAwal);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let batal = false;
    apiGet<Daftar>("/peringkat?minutes=10")
      .then((d) => !batal && setData(d))
      .catch((e: unknown) =>
        !batal && setGalat(e instanceof Error ? e.message : "Gagal memuat peringkat")
      );
    return () => {
      batal = true;
    };
  }, []);

  const segmen = [
    { id: "sepi", label: "Potensi kawasan" },
    { id: "paparan", label: "Paparan iklan" },
    ...Object.keys(data?.tenant ?? {}).map((k) => ({ id: `tenant:${k}`, label: k })),
  ];

  const baris: Baris[] = !data
    ? []
    : pilih === "sepi"
      ? data.sepi
      : pilih === "paparan"
        ? data.paparan
        : (data.tenant[pilih.replace("tenant:", "")] ?? []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Peringkat stasiun"
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-3xl flex-col border border-ink bg-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hair p-4">
          <div className="min-w-0">
            <p className="label-caps text-accent">Peringkat stasiun</p>
            <h2 className="mt-1 text-xl font-bold leading-tight tracking-[-0.01em]">
              Jangkauan jalan kaki 10 menit
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup peringkat"
            className="shrink-0 border border-hair px-2 py-1 text-sm leading-none text-ink-soft hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </header>

        <div className="shrink-0 border-b border-hair px-4 py-2">
          <div className="flex flex-wrap gap-1">
            {segmen.map((sg) => (
              <button
                key={sg.id}
                type="button"
                onClick={() => setPilih(sg.id)}
                aria-current={pilih === sg.id ? "page" : undefined}
                className={`border px-2 py-0.5 text-[11px] ${
                  pilih === sg.id
                    ? "border-accent text-accent"
                    : "border-hair text-muted hover:border-ink hover:text-ink"
                }`}
              >
                {sg.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {galat && <p className="text-xs text-muted">{galat}</p>}
          {!data && !galat && <p className="text-xs text-muted">Memuat…</p>}

          {data && (
            <>
              <p className="mb-3 text-[11px] leading-relaxed text-muted">
                {data.catatan}
              </p>
              <p className="mb-3 border-l-2 border-hair pl-2 text-[10px] leading-relaxed text-muted">
                Urutannya memakai skor SESUDAH dipotong ketidakpastian, bukan
                skor mentahnya. Stasiun yang sebagian bahannya masih taksiran
                dipotong lebih dalam, sehingga tidak bisa unggul hanya karena
                datanya belum lengkap — dan peringkatnya naik sendiri begitu
                data barunya masuk.
              </p>
              <ol className="flex flex-col">
                {baris.map((b) => {
                  const sorot = b.stasiun === stasiunSorot;
                  return (
                    <li
                      key={`${pilih}-${b.stasiun}`}
                      className={`flex items-baseline gap-3 border-b border-canvas py-1.5 text-xs last:border-b-0 ${
                        sorot ? "bg-canvas px-2 font-semibold text-ink" : "text-ink-soft"
                      }`}
                    >
                      <span className="data-num w-8 shrink-0 text-right text-muted">
                        #{b.peringkat}
                      </span>
                      <span className="min-w-0 flex-1">{b.stasiun}</span>
                      {b.pesaing !== undefined && (
                        <span className="shrink-0 text-[10px] text-muted">
                          {b.pesaing} pesaing
                        </span>
                      )}
                      {b.confidence !== undefined && (
                        <span
                          className={`data-num shrink-0 text-[10px] ${
                            b.confidence < 0.8 ? "text-accent" : "text-muted"
                          }`}
                          title={
                            b.confidence < 0.8
                              ? "Sebagian bahannya masih taksiran, jadi skornya dipotong sebelum diurutkan"
                              : "Seluruh bahannya terukur"
                          }
                        >
                          yakin {b.confidence.toFixed(2)}
                        </span>
                      )}
                      {/*
                        Dua angka, bukan satu. Yang tipis di kiri adalah skor
                        mentah, yang tebal di kanan skor sesudah dipotong
                        ketidakpastian - dan yang kedua itulah dasar urutannya.
                        Menampilkan skor mentah saja membuat daftarnya tampak
                        tidak urut.
                      */}
                      {b.nilai_bawah !== undefined && (
                        <span className="data-num w-10 shrink-0 text-right text-[10px] text-muted line-through decoration-hair">
                          {b.nilai.toFixed(1)}
                        </span>
                      )}
                      <span className="data-num w-12 shrink-0 text-right">
                        {(b.nilai_bawah ?? b.nilai).toFixed(1)}
                      </span>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
