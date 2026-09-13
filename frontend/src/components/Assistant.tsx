"use client";

import { useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import type { AksiAsisten, StationFeature } from "@/types/station";

type Props = {
  station: StationFeature | null;
  onAction: (aksi: AksiAsisten) => void;
};

/**
 * Asisten sebagai panel yang menyatu, bukan tombol mengambang di pojok.
 *
 * Versi sebelumnya berupa tombol kecil di sudut kanan bawah peta. Penempatan
 * itu membuatnya terbaca sebagai pelengkap yang bisa diabaikan, padahal ia satu
 * satunya tempat pengguna bisa bertanya bebas, dan sekarang juga satu-satunya
 * yang bisa menghitung ulang atas permintaan.
 *
 * Sekarang ia menempel di tepi kanan peta setinggi penuh, sejajar dengan panel
 * stasiun, dengan pemicu yang menyebut namanya alih-alih hanya ikon.
 *
 * Panelnya tetap terpasang walau tertutup, cuma disembunyikan, supaya
 * percakapan tidak hilang tiap kali dibuka tutup.
 */
export default function Assistant({ station, onAction }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/*
        Pemicunya dibesarkan dan dipindah ke sudut kanan BAWAH.
        Di kanan atas ia berdesakan dengan panel stasiun dan terbaca sebagai
        label peta - dan ukurannya yang setinggi label membuatnya lolos dari
        pandangan sama sekali. Sudut kanan bawah adalah tempat yang sudah
        dikenal orang untuk pemicu asisten, jauh dari lapisan analisis, dan
        tidak pernah tertutup panel.

        Warna aksen dipakai, bukan tinta hitam: di halaman ini aksen menandai
        "yang bisa ditindaklanjuti", dan inilah satu-satunya tempat pengguna
        bisa meminta hitungan baru.
      */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Buka asisten analisis"
        className={`panel-float absolute bottom-4 right-4 z-10 items-center gap-2.5 border-2 border-ink bg-accent py-3 pl-3.5 pr-4 text-white shadow-lg transition-transform hover:scale-[1.03] ${
          open ? "hidden" : "flex"
        }`}
      >
        <AnalysisMark size={22} />
        <span className="flex flex-col items-start leading-tight">
          <span className="text-sm font-bold tracking-tight">Tanya AI</span>
          <span className="text-[10px] font-medium opacity-90">
            hitung ulang &amp; bandingkan
          </span>
        </span>
      </button>

      <div
        className={`panel-float absolute bottom-3 right-3 top-3 z-10 w-[380px] max-w-[calc(100%-1.5rem)] flex-col border border-ink bg-panel ${
          open ? "flex" : "hidden"
        }`}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-hair px-3 py-2">
          <p className="label-caps flex items-center gap-2 text-ink-soft">
            <AnalysisMark />
            Asisten analisis
          </p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Tutup asisten"
            className="border border-hair px-1.5 text-xs leading-5 text-muted hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </div>

        <ChatPanel station={station} onAction={onAction} />
      </div>
    </>
  );
}

/**
 * Ikon: batang peringkat menaik dengan penanda lokasi.
 *
 * Balon chat sebelumnya menjanjikan hal yang keliru, asisten ini bukan teman
 * ngobrol, ia menghitung peringkat di atas data spasial. Ikonnya sekarang
 * menyebut dua hal itu sekaligus.
 */
function AnalysisMark({ size = 16 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 20V13M9.5 20V9" />
      <path d="M15 20v-4" />
      <circle cx="18.5" cy="6.5" r="2.5" />
      <path d="M18.5 11.5c1.8-2.2 3-3.6 3-5a3 3 0 1 0-6 0c0 1.4 1.2 2.8 3 5z" />
    </svg>
  );
}
