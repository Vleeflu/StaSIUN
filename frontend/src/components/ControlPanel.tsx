"use client";

import type { ReactNode } from "react";

import StationSearch from "@/components/StationSearch";
import { KRL_LINES, lineColor, shortLabel } from "@/lib/lines";
import type { StationFeature } from "@/types/station";

type Props = {
  stations: StationFeature[];
  loading: boolean;
  error: string | null;
  onSelect: (station: StationFeature) => void;
  activeLines: Set<string>;
  onToggleLine: (code: string) => void;
  showLabels: boolean;
  onToggleLabels: (next: boolean) => void;
};

export default function ControlPanel({
  stations,
  loading,
  error,
  onSelect,
  activeLines,
  onToggleLine,
  showLabels,
  onToggleLabels,
}: Props) {
  return (
    <div className="panel-float w-[264px] border border-ink bg-panel">
      <Section title="Cari stasiun">
        <StationSearch
          stations={stations}
          loading={loading}
          error={error}
          onSelect={onSelect}
        />
      </Section>

      <Section title="Filter lin">
        <div className="flex flex-wrap gap-1.5">
          {KRL_LINES.map((code) => {
            const active = activeLines.has(code);
            return (
              <button
                key={code}
                type="button"
                aria-pressed={active}
                onClick={() => onToggleLine(code)}
                className={`flex items-center gap-1.5 border px-2 py-1 text-xs ${
                  active
                    ? "border-ink bg-panel text-ink"
                    : "border-hair bg-canvas text-muted"
                }`}
              >
                <span
                  aria-hidden="true"
                  className="h-2.5 w-2.5 shrink-0"
                  style={{
                    backgroundColor: lineColor(code),
                    opacity: active ? 1 : 0.3,
                  }}
                />
                <span className="data-num">{code}</span> · {shortLabel(code)}
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Layer">
        <div className="flex flex-col gap-2">
          <Toggle
            label="Label nama stasiun"
            checked={showLabels}
            onChange={onToggleLabels}
          />
          {/* Dua layer berikut butuh mesin skoring dan pgRouting yang belum
              dibangun. Sengaja dimatikan, bukan disembunyikan, supaya kerangka
              produknya tetap terbaca. */}
          <Toggle label="Heatmap SEPI per stasiun" disabled />
          <Toggle label="Isochrone stasiun terpilih" disabled />
        </div>
      </Section>

      <Section title="Legenda">
        <ul className="flex flex-col gap-2 text-xs text-ink-soft">
          <LegendRow color="#c90025">Stasiun satu lin</LegendRow>
          <LegendRow pie>Interchange (multi-lin)</LegendRow>
          <LegendRow color="#c90025" faded>
            Dilintasi tanpa berhenti
          </LegendRow>
        </ul>
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-hair p-3 last:border-b-0">
      <h2 className="label-caps mb-2 text-ink-soft">{title}</h2>
      {children}
    </section>
  );
}

function Toggle({
  label,
  checked = false,
  disabled = false,
  onChange,
}: {
  label: string;
  checked?: boolean;
  disabled?: boolean;
  onChange?: (next: boolean) => void;
}) {
  return (
    <label
      className={`flex items-start gap-2 text-xs ${
        disabled ? "cursor-not-allowed text-muted" : "cursor-pointer text-ink"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.checked)}
        className="mt-px h-3.5 w-3.5 shrink-0 accent-[#ec3013]"
      />
      <span>
        {label}
        {disabled && (
          <span className="block text-[10px] text-muted">belum tersedia</span>
        )}
      </span>
    </label>
  );
}

function LegendRow({
  color,
  pie = false,
  faded = false,
  children,
}: {
  color?: string;
  pie?: boolean;
  faded?: boolean;
  children: ReactNode;
}) {
  return (
    <li className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="h-3 w-3 shrink-0 rounded-full border-2 border-white"
        style={{
          // Interchange digambar sebagai lingkaran dua warna, sama seperti
          // ikon aslinya di peta.
          background: pie
            ? "conic-gradient(#c90025 0 50%, #00a4e4 50% 100%)"
            : color,
          opacity: faded ? 0.4 : 1,
          boxShadow: "0 0 0 1px #dedbd9",
        }}
      />
      {children}
    </li>
  );
}
