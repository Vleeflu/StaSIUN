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
  showSepi: boolean;
  onToggleSepi: (next: boolean) => void;
  showIsochrone: boolean;
  onToggleIsochrone: (next: boolean) => void;
  hasSelection: boolean;
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
  showSepi,
  onToggleSepi,
  showIsochrone,
  onToggleIsochrone,
  hasSelection,
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
          <Toggle
            label="Skor SEPI per stasiun"
            checked={showSepi}
            onChange={onToggleSepi}
          />
          <Toggle
            label="Isochrone stasiun terpilih"
            checked={showIsochrone}
            onChange={onToggleIsochrone}
            disabled={!hasSelection}
            hint={hasSelection ? undefined : "pilih stasiun dulu"}
          />
        </div>
      </Section>

      <Section title="Legenda">
        {showSepi ? (
          <div>
            <div
              aria-hidden="true"
              className="h-2 w-full"
              style={{
                background:
                  "linear-gradient(to right, #e8e4e2, #f6c3b6, #f2846b, #ec3013, #a41c07)",
              }}
            />
            <div className="mt-1 flex justify-between">
              <span className="data-num text-[10px] text-muted">0</span>
              <span className="label-caps text-[9px] text-muted">Skor SEPI</span>
              <span className="data-num text-[10px] text-muted">100</span>
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-muted">
              Cincin latar di belakang penanda stasiun. Abu-abu berarti skornya
              belum dihitung.
            </p>
            <ul className="mt-2.5 flex flex-col gap-2 border-t border-hair pt-2.5 text-xs text-ink-soft">
              <LegendRow color="#c90025">Stasiun satu lin</LegendRow>
              <LegendRow pie>Interchange (multi-lin)</LegendRow>
              <LegendRow ring>Stasiun terpilih</LegendRow>
            </ul>
          </div>
        ) : (
          <ul className="flex flex-col gap-2 text-xs text-ink-soft">
            <LegendRow color="#c90025">Stasiun satu lin</LegendRow>
            <LegendRow pie>Interchange (multi-lin)</LegendRow>
            <LegendRow color="#c90025" faded>
              Dilintasi tanpa berhenti
            </LegendRow>
            <LegendRow ring>Stasiun terpilih</LegendRow>
          </ul>
        )}

        {showIsochrone && hasSelection && (
          <div className="mt-3 border-t border-hair pt-2.5">
            <p className="label-caps mb-1.5 text-[9px] text-muted">
              Jangkauan jalan kaki
            </p>
            <div className="flex gap-3">
              {[
                { minutes: 5, opacity: 0.18 },
                { minutes: 10, opacity: 0.12 },
                { minutes: 15, opacity: 0.07 },
              ].map((band) => (
                <span
                  key={band.minutes}
                  className="flex items-center gap-1.5 text-xs text-ink-soft"
                >
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 shrink-0 border border-reach"
                    style={{ backgroundColor: `rgb(164 36 158 / ${band.opacity})` }}
                  />
                  <span className="data-num">{band.minutes}′</span>
                </span>
              ))}
            </div>
          </div>
        )}
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
  hint = "belum tersedia",
  onChange,
}: {
  label: string;
  checked?: boolean;
  disabled?: boolean;
  hint?: string;
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
        {disabled && <span className="block text-[10px] text-muted">{hint}</span>}
      </span>
    </label>
  );
}

function LegendRow({
  color,
  pie = false,
  ring = false,
  faded = false,
  children,
}: {
  color?: string;
  pie?: boolean;
  ring?: boolean;
  faded?: boolean;
  children: ReactNode;
}) {
  if (ring) {
    return (
      <li className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="h-3 w-3 shrink-0 rounded-full border-2 border-select"
          style={{ backgroundColor: "rgb(242 193 1 / 0.16)" }}
        />
        {children}
      </li>
    );
  }

  return (
    <li className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="h-3 w-3 shrink-0 rounded-full border-2 border-white"
        style={{
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
