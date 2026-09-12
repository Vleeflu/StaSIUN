"use client";

import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";
import { SEPI_COMPONENTS, sepiColor } from "@/lib/sepi";
import type { StationScore } from "@/types/station";

type Props = {
  stationIds: number[];
  names: Record<number, string>;
  onOpen: (stationId: number) => void;
  onClose: () => void;
};

/**
 * Perbandingan beberapa stasiun berdampingan, dibuka dari tombol asisten.
 *
 * Angkanya diambil ulang dari skor resmi, bukan disalin dari jawaban asisten.
 * Kalau asisten salah membaca angka, kartu ini yang membuktikannya.
 */
export default function CompareCard({ stationIds, names, onOpen, onClose }: Props) {
  const kunci = stationIds.join(",");
  const [hasil, setHasil] = useState<{ kunci: string; skor: StationScore[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let batal = false;
    Promise.all(
      stationIds.map((id) => apiGet<StationScore>(`/stations/${id}/score?minutes=10`))
    )
      .then((skor) => {
        if (!batal) {
          setHasil({ kunci, skor: [...skor].sort((a, b) => a.rank - b.rank) });
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!batal) setError(e instanceof Error ? e.message : "Gagal memuat skor");
      });
    return () => {
      batal = true;
    };
    // `kunci` mewakili isi `stationIds`; array baru dengan isi sama tidak memicu ulang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kunci]);

  const skor = hasil?.kunci === kunci ? hasil.skor : null;

  return (
    <div className="panel-float absolute bottom-3 left-3 z-20 w-[460px] max-w-[calc(100%-1.5rem)] border border-ink bg-panel">
      <div className="flex items-center justify-between border-b border-hair px-3 py-2">
        <p className="label-caps text-ink-soft">Perbandingan · skor resmi</p>
        <button
          type="button"
          onClick={onClose}
          aria-label="Tutup perbandingan"
          className="border border-hair px-1.5 text-xs leading-5 text-muted hover:border-ink hover:text-ink"
        >
          ✕
        </button>
      </div>

      {error && <p className="p-3 text-xs text-accent">{error}</p>}
      {!skor && !error && <p className="p-3 text-xs text-muted">Memuat…</p>}

      {skor && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-hair text-left text-[10px] text-muted">
                <th className="px-3 py-1.5 font-normal">Stasiun</th>
                <th className="px-1 py-1.5 text-right font-normal">SEPI</th>
                <th className="px-1 py-1.5 text-right font-normal" title="Rentang peringkat di 5 skema bobot">
                  Peringkat
                </th>
                {SEPI_COMPONENTS.map((c) => (
                  <th key={c.key} className="px-1 py-1.5 text-right font-normal" title={c.label}>
                    {c.key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {skor.map((s) => (
                <tr key={s.station_id} className="border-b border-canvas last:border-0">
                  <td className="px-3 py-1.5">
                    <button
                      type="button"
                      onClick={() => onOpen(s.station_id)}
                      className="text-left font-semibold text-ink underline decoration-hair underline-offset-2 hover:decoration-ink"
                    >
                      {names[s.station_id] ?? `#${s.station_id}`}
                    </button>
                    <span className="block text-[10px] text-muted">{s.kelas}</span>
                  </td>
                  <td className="data-num px-1 py-1.5 text-right font-semibold" style={{ color: sepiColor(s.sepi) }}>
                    {s.sepi.toFixed(1)}
                  </td>
                  <td className="data-num px-1 py-1.5 text-right">
                    #{s.rank}
                    {s.sensitivity && (
                      <span className="block text-[10px] text-muted">
                        {s.sensitivity.peringkat_min}–{s.sensitivity.peringkat_maks}
                      </span>
                    )}
                  </td>
                  {SEPI_COMPONENTS.map((c) => {
                    const v = s.components[c.key];
                    return (
                      <td key={c.key} className="data-num px-1 py-1.5 text-right text-ink-soft">
                        {v === null ? <span className="text-muted">—</span> : v.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="border-t border-hair px-3 py-2 text-[10px] leading-relaxed text-muted">
            Angka di bawah peringkat adalah rentangnya di lima skema bobot. Tanda — berarti
            variabel itu belum terukur di stasiun tersebut.
          </p>
        </div>
      )}
    </div>
  );
}
