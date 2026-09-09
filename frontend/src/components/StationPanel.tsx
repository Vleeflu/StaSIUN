"use client";

import { useState, type ReactNode } from "react";

import { useStationScore } from "@/hooks/useStationScore";
import { useStationTenants } from "@/hooks/useStationTenants";
import { badgeLabel, lineColor, lineLabel, lineTextColor } from "@/lib/lines";
import { SEPI_COMPONENTS, componentShares, sepiColor } from "@/lib/sepi";
import { parseLines } from "@/types/station";
import type { StationFeature } from "@/types/station";

const TABS = ["Ikhtisar", "Ad-Space", "Tenant", "Naming"] as const;
type Tab = (typeof TABS)[number];

const SCORE_MINUTES = 10;

// Alasan tiap modul belum dibangun ditulis apa adanya. Menyebut kebutuhan
// datanya lebih berguna daripada "segera hadir" — pembacanya jadi tahu apa
// yang harus dicari, dan tidak menyangka angkanya sengaja disembunyikan.
const PENDING_REASON: Record<string, string> = {
  "Ad-Space":
    "Peringkat kategori merek sudah bisa dihitung dari kepadatan titik, tapi perkiraan nilai sewanya belum. Belum ada satu pun data pembanding harga sewa ruang stasiun di database, dan angka tanpa pembanding cuma tebakan berbaju hitungan.",
  Naming:
    "Butuh data merek dan pembanding nilai kontrak penamaan yang belum kita punya sama sekali.",
};

const PLANNED_SOURCES = [
  "StrukGo · OCR struk",
  "MenuGo · harga & densitas",
  "PropertiGo · benchmark",
  "Activity · korpus NLP",
  "OSM · jaringan pejalan",
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
        {tab === "Ikhtisar" && <Overview station={station} />}
        {tab === "Tenant" && <TenantTab station={station} />}
        {(tab === "Ad-Space" || tab === "Naming") && (
          <EmptyTab name={tab} reason={PENDING_REASON[tab]} />
        )}
      </div>
    </aside>
  );
}

function Overview({ station }: { station: StationFeature }) {
  const props = station.properties;
  const codes = parseLines(props.lines);
  const [lon, lat] = station.geometry.coordinates;

  const stationId = typeof station.id === "number" ? station.id : null;
  const { score, loading } = useStationScore(stationId, SCORE_MINUTES);

  const shares = score ? componentShares(score.components) : null;

  return (
    <div className="flex flex-col">
      <Section title="Indeks SEPI" pending={!score}>
        <div className="flex items-end justify-between">
          <div className="min-w-0 pr-4">
            {score ? (
              <>
                <p className="text-xs leading-relaxed text-ink-soft">
                  Peringkat{" "}
                  <span className="data-num font-semibold text-ink">
                    #{score.rank}
                  </span>{" "}
                  dari 46 stasiun KRL.
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted">
                  TOPSIS di atas bobot Entropy + AHP, dihitung dalam jangkauan
                  jalan kaki {score.minutes} menit.
                </p>
              </>
            ) : (
              <p className="text-xs leading-relaxed text-muted">
                {loading
                  ? "Memuat skor…"
                  : "Belum dihitung untuk stasiun ini. Jalankan compute_sepi di backend."}
              </p>
            )}
          </div>

          <p
            className="data-num shrink-0 text-4xl font-semibold leading-none"
            style={{ color: score ? sepiColor(score.sepi) : undefined }}
          >
            {score ? score.sepi.toFixed(1) : "—"}
            <span className="text-base font-medium text-muted">/100</span>
          </p>
        </div>
      </Section>

      <Section
        title="Komponen SEPI — w₁T + w₂E + w₃A + w₄U + w₅C"
        pending={!score}
      >
        <ul className="flex flex-col gap-2.5">
          {SEPI_COMPONENTS.map((c) => {
            const value = score?.components[c.key];
            const share = shares?.[c.key] ?? 0;

            return (
              <li key={c.key} className="flex items-center gap-3">
                <span className="data-num w-3 shrink-0 text-xs font-semibold text-ink-soft">
                  {c.key}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs text-ink-soft">{c.label}</span>
                  <span className="mt-1 block h-1.5 w-full bg-canvas">
                    <span
                      className="block h-full bg-accent"
                      style={{ width: `${Math.round(share * 100)}%` }}
                    />
                  </span>
                </span>
                <span className="data-num w-16 shrink-0 text-right text-xs text-ink-soft">
                  {value === undefined ? "—" : c.format(value)}
                </span>
              </li>
            );
          })}
        </ul>
      </Section>

      {score && (
        <Section title="Isi jangkauan jalan kaki">
          <dl className="flex flex-col gap-2">
            <Row
              label="Luas terjangkau"
              value={`${score.detail.area_km2.toFixed(2)} km²`}
              mono
            />
            <Row
              label="Lin KRL berhenti"
              value={String(score.detail.line_count)}
              mono
            />
            <Row
              label="Halte bus"
              value={String(score.detail.halte_count)}
              mono
            />
            <Row
              label="Stasiun moda lain"
              value={String(score.detail.other_mode_count)}
              mono
            />
          </dl>
        </Section>
      )}

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

function TenantTab({ station }: { station: StationFeature }) {
  const stationId = typeof station.id === "number" ? station.id : null;
  const { report, loading, error } = useStationTenants(stationId, SCORE_MINUTES);

  if (loading) {
    return <p className="p-4 text-xs text-muted">Memuat skor tenant…</p>;
  }

  if (error || !report || report.categories.length === 0) {
    return (
      <div className="p-4">
        <div className="border border-dashed border-hair p-6 text-center">
          <p className="text-sm font-semibold text-ink-soft">Tenant</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            {error ??
              "Skor tenant belum dihitung untuk stasiun ini. Jalankan compute_tsi di backend."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <Section title="Tenant Survival Index">
        <p className="text-xs leading-relaxed text-ink-soft">
          Perbandingan calon pelanggan yang bisa berjalan kaki ke sini dengan
          pesaing sejenis yang sudah ada, dalam jangkauan {report.minutes}{" "}
          menit. Skor tinggi berarti masih lapang.
        </p>
        <p className="mt-2 text-[11px] leading-relaxed text-muted">
          Peringkatnya dihitung per kategori, jadi bacanya &ldquo;stasiun ini
          urutan ke berapa untuk usaha jenis itu&rdquo; — bukan perbandingan
          antar kategori.
        </p>
      </Section>

      <Section title={`Peluang per kategori — ${report.station_count} stasiun KRL`}>
        <ul className="flex flex-col gap-4">
          {report.categories.map((c) => (
            <li key={c.category}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-xs font-semibold text-ink">{c.label}</span>
                <span className="data-num shrink-0 text-sm font-semibold text-ink">
                  {c.tsi.toFixed(0)}
                  <span className="text-[10px] font-medium text-muted">/100</span>
                </span>
              </div>

              <span className="mt-1.5 block h-1.5 w-full bg-canvas">
                <span
                  className="block h-full bg-accent"
                  style={{ width: `${Math.round(c.tsi)}%` }}
                />
              </span>

              <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-muted">
                <span className="label-caps border border-hair px-1.5 py-0.5 text-[9px] text-ink-soft">
                  #{c.rank} dari {report.station_count}
                </span>
                <span>
                  <span className="data-num text-ink-soft">{c.demand}</span> calon
                  pelanggan
                </span>
                <span>
                  <span className="data-num text-ink-soft">{c.supply}</span> pesaing
                </span>
                <span>
                  rasio{" "}
                  <span className="data-num text-ink-soft">
                    {c.headroom.toFixed(0)}
                  </span>
                </span>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Cara membacanya">
        <ul className="flex flex-col gap-2 text-[11px] leading-relaxed text-muted">
          <li>
            <span className="text-ink-soft">Calon pelanggan</span> — titik ekonomi
            dan urban di dalam isochrone: kantor, bank, hunian, tempat ibadah,
            faskes. Gerai komersial sengaja tidak dihitung di sini supaya
            daerah yang sudah padat warung tidak tercatat butuh lebih banyak
            warung.
          </li>
          <li>
            <span className="text-ink-soft">Pengali arus lewat</span> ×
            {" "}
            <span className="data-num">
              {report.categories[0]?.connectivity.toFixed(2)}
            </span>{" "}
            — dari komponen T. Stasiun yang terhubung banyak moda melewatkan
            orang yang tidak tinggal maupun bekerja di sekitarnya.
          </li>
          <li>
            <span className="text-ink-soft">Batasnya</span> — skor ini mengukur
            kelapangan pasar, bukan kecocokan merek atau daya beli. Angkanya
            juga terbatas pada lima kategori yang datanya kita punya.
          </li>
        </ul>
      </Section>
    </div>
  );
}

function EmptyTab({ name, reason }: { name: string; reason: string }) {
  return (
    <div className="p-4">
      <div className="border border-dashed border-hair p-6">
        <p className="text-center text-sm font-semibold text-ink-soft">{name}</p>
        <p className="mt-2 text-xs leading-relaxed text-muted">{reason}</p>
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
