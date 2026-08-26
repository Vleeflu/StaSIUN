"use client";

import { useState } from "react";

import ChatPanel from "@/components/ChatPanel";
import type { StationFeature } from "@/types/station";

type Props = {
  station: StationFeature | null;
};

/**
 * Asisten mengambang di pojok kanan bawah peta.
 *
 * Panelnya tetap terpasang walau sedang tertutup — cuma disembunyikan — supaya
 * percakapan tidak hilang tiap kali dibuka tutup.
 */
export default function Assistant({ station }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Buka asisten"
        className={`panel-float absolute bottom-3 right-3 z-10 h-11 w-11 items-center justify-center border border-ink bg-ink text-white hover:bg-ink-soft ${
          open ? "hidden" : "flex"
        }`}
      >
        <ChatMark />
      </button>

      <div
        className={`panel-float absolute bottom-3 right-3 z-10 h-[460px] max-h-[calc(100%-1.5rem)] w-[360px] max-w-[calc(100%-1.5rem)] flex-col border border-ink bg-panel ${
          open ? "flex" : "hidden"
        }`}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-hair px-3 py-2">
          <p className="label-caps text-ink-soft">Asisten StaSIUN</p>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Tutup asisten"
            className="border border-hair px-1.5 text-xs leading-5 text-muted hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </div>

        <ChatPanel station={station} />
      </div>
    </>
  );
}

function ChatMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 4h16v12H9l-5 4V4z" />
      <path d="M8 9h8M8 12h5" />
    </svg>
  );
}
