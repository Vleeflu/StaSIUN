"use client";

import { useState, type ReactNode } from "react";

import { badgeLabel, lineColor, lineLabel, lineTextColor } from "@/lib/lines";
import { parseLines } from "@/types/station";
import type { StationFeature } from "@/types/station";

// Empat sisi dari satu stasiun. Asisten tidak ikut di sini karena dia alat,
// bukan sisi dari stasiun — tempatnya tombol mengambang di pojok peta.
const TABS = ["Ikhtisar", "Ad-Space", "Tenant", "Naming"] as const;
type Tab = (typeof TABS)[number];

// Lima komponen SEPI persis seperti di proposal. Bobotnya belum ada angkanya
// karena masih menunggu perhitungan Entropy + AHP.
const SEPI_COMPONENTS = [
  { key: "T", label: "Transportasi" },
  { key: "E", label: "Ekonomi" },
  { key: "A", label: "Aksesibilitas" },
  { key: "U", label: "Urban" },
  { key: "C", label: "Komersial" },
];

// Sumber sesuai PRD. Dataset Mission (StrukGo, MenuGo, PropertiGo) sengaja
// tidak ada di sini: cakupannya di wilayah studi belum memadai, jadi tidak ada
// satu variabel pun yang boleh bergantung padanya.
const PLANNED_SOURCES = [
  "Activity · korpus + objek",
  "Isochrone · GeoMAPID",
  "OSM · pejalan & titik minat",
  "Volume penumpang",
  "Profil kawasan",
  "Riset harga terbuka",
];

type Props = {
  station: StationFeature;
  onClose: () => void;
};

export default function StationPanel({ station, onClose }: Props) {
  const [tab, setTab] = useState<Tab>("Ikhtisar");
  const props = station.properties;
  const codes = parseLines(props.lines);

  return (
    <aside className="flex w-[400px] shrink-0 flex-col overflow-hidden border-l border-ink bg-panel">
      <div className="shrink-0 border-b border-hair p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="label-caps text-accent">Stasiun</p>
            <h2 className="mt-1 text-[26px] font-bold leading-[1.1] tracking-[-0.02em]">
              {props.name}
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup panel stasiun"
            className="shrink-0 border border-hair px-2 py-1 text-sm leading-none text-ink-soft hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {codes.map((code) => (
            <span
              key={code}
              className="label-caps px-2 py-1"
              style={{
                backgroundColor: lineColor(code),
                color: lineTextColor(code),
              }}
            >
              {code} · {badgeLabel(code)}
            </span>
          ))}

          {codes.length === 0 && props.network && (
            <span className="label-caps border border-hair px-2 py-1 text-muted">
              {props.network}
            </span>
          )}
        </div>

        {(codes.length > 1 || !props.served) && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {codes.length > 1 && (
              <span className="label-caps border border-ink px-2 py-1 text-ink">
                Interchange
              </span>
            )}
            {!props.served && (
              <span className="label-caps border border-hair px-2 py-1 text-muted">
                Dilintasi tanpa berhenti
              </span>
            )}
          </div>
        )}
      </div>

      <nav
        className="flex shrink-0 border-b border-hair"
        aria-label="Bagian detail stasiun"
      >
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            aria-current={t === tab ? "page" : undefined}
            className={`label-caps flex-1 border-b-2 px-1 py-2.5 ${
              t === tab
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink-soft"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "Ikhtisar" ? (
          <Overview station={station} />
        ) : (
          <EmptyTab name={tab} />
        )}
      </div>
    </aside>
  );
}

function Overview({ station }: { station: StationFeature }) {
  const props = station.properties;
  const codes = parseLines(props.lines);
  const [lon, lat] = station.geometry.coordinates;

  return (
    <div className="flex flex-col">
      <Section title="Indeks SEPI" pending>
        <div className="flex items-end justify-between">
          <p className="text-xs leading-relaxed text-muted">
            Akan dihitung dengan TOPSIS di atas bobot gabungan Entropy + AHP
            (CR &lt; 0,10).
          </p>
          <p className="data-num shrink-0 pl-4 text-4xl font-semibold leading-none text-muted">
            —
            <span className="text-base font-medium">/100</span>
          </p>
        </div>
      </Section>

      <Section title="Komponen SEPI — w₁T + w₂E + w₃A + w₄U + w₅C" pending>
        <ul className="flex flex-col gap-2.5">
          {SEPI_COMPONENTS.map((c) => (
            <li key={c.key} className="flex items-center gap-3">
              <span className="data-num w-3 shrink-0 text-xs font-semibold text-ink-soft">
                {c.key}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-xs text-ink-soft">{c.label}</span>
                {/* Track kosong: kerangkanya sudah terlihat, isinya menunggu
                    angka asli dari mesin skoring. */}
                <span className="mt-1 block h-1.5 w-full bg-canvas" />
              </span>
              <span className="data-num w-6 shrink-0 text-right text-xs text-muted">
                —
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Profil stasiun">
        <dl className="flex flex-col gap-2">
          <Row label="Kode KAI" value={props.code} mono />
          <Row
            label="Lin dilayani"
            value={codes.length > 0 ? lineLabel(codes) : props.network}
          />
          <Row
            label="Status"
            value={props.served ? "Dilayani KRL" : "Dilintasi tanpa berhenti"}
          />
          <Row label="Kecamatan" value={props.kecamatan} />
          <Row label="Alamat" value={props.address} />
          <Row
            label="Koordinat"
            value={`${lat.toFixed(5)}, ${lon.toFixed(5)}`}
            mono
          />
        </dl>
      </Section>

      <Section title="Menunggu data" pending>
        <dl className="flex flex-col gap-2">
          <Row label="Footfall / hari kerja" value={null} />
          <Row label="Median dwell-time" value={null} />
          <Row label="Arketipe (LDA)" value={null} />
        </dl>
      </Section>

      <Section title="Sumber data — rencana" pending>
        <div className="flex flex-wrap gap-1.5">
          {PLANNED_SOURCES.map((s) => (
            <span
              key={s}
              className="border border-hair px-2 py-1 text-[10px] text-muted"
            >
              {s}
            </span>
          ))}
        </div>
      </Section>
    </div>
  );
}

function EmptyTab({ name }: { name: string }) {
  return (
    <div className="p-4">
      <div className="border border-dashed border-hair p-6 text-center">
        <p className="text-sm font-semibold text-ink-soft">{name}</p>
        <p className="mt-1 text-xs leading-relaxed text-muted">
          Modul ini belum dibangun. Butuh mesin skoring SEPI dan data mitra
          MAPID lebih dulu.
        </p>
      </div>
    </div>
  );
}

function Section({
  title,
  pending = false,
  children,
}: {
  title: string;
  pending?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-hair p-4 last:border-b-0">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="label-caps text-ink-soft">{title}</h3>
        {pending && (
          <span className="label-caps shrink-0 border border-hair px-1.5 py-0.5 text-[9px] text-muted">
            Belum terhitung
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value?: string | null;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="shrink-0 text-xs text-muted">{label}</dt>
      <dd
        className={`text-right text-xs ${mono ? "data-num" : ""} ${
          value ? "text-ink" : "text-muted"
        }`}
      >
        {value || "—"}
      </dd>
    </div>
  );
}
