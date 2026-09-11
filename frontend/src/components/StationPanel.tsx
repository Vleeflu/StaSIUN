"use client";

import { type ReactNode } from "react";

import SimulasiSepi from "@/components/SimulasiSepi";
import { useStationAreas } from "@/hooks/useStationAreas";
import { useStationScore } from "@/hooks/useStationScore";
import { useStationTenants } from "@/hooks/useStationTenants";
import { badgeLabel, lineColor, lineLabel, lineTextColor } from "@/lib/lines";
import {
  SEPI_COMPONENTS,
  componentShares,
  confidenceLabel,
  formatKomponen,
  sepiColor,
} from "@/lib/sepi";
import { parseLines } from "@/types/station";
import type {
  AreaStasiun,
  LaporanArea,
  ProfilKeramaian,
  Sensitivitas,
  StationFeature,
} from "@/types/station";

const TABS = ["Ikhtisar", "Ad-Space", "Tenant", "Naming"] as const;
export type Tab = (typeof TABS)[number];

const SCORE_MINUTES = 10;

// Alasan tiap modul belum dibangun ditulis apa adanya. Menyebut kebutuhan
// datanya lebih berguna daripada "segera hadir" — pembacanya jadi tahu apa
// yang harus dicari, dan tidak menyangka angkanya sengaja disembunyikan.
const PENDING_REASON: Record<string, string> = {
  Naming:
    "Peringkat kandidat sponsor butuh deteksi merek (NER) dari narasi Activity, yang belum dibangun. Nilai kontraknya butuh pembanding transaksi naming rights yang juga belum ada. Keduanya tidak ditampilkan daripada ditebak.",
};

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
  /** Tab dikendalikan dari luar supaya tombol asisten bisa membuka tab tertentu. */
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  /** Bobot kiriman asisten; `nonce` baru membuka simulasi dan menjalankannya. */
  simulasiPreset: { bobot: Record<string, number>; nonce: number } | null;
  onClose: () => void;
};

export default function StationPanel({
  station,
  tab,
  onTabChange,
  simulasiPreset,
  onClose,
}: Props) {
  const setTab = onTabChange;
  const props = station.properties;
  const stationId = typeof station.id === "number" ? station.id : null;
  const areas = useStationAreas(stationId);
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
        {tab === "Ikhtisar" && (
          <Overview
            station={station}
            laporan={areas.laporan}
            simulasiPreset={simulasiPreset}
            onTabChange={setTab}
          />
        )}
        {tab === "Ad-Space" && (
          <AdSpaceTab laporan={areas.laporan} loading={areas.loading} error={areas.error} />
        )}
        {tab === "Tenant" && <TenantTab station={station} laporan={areas.laporan} />}
        {tab === "Naming" && <EmptyTab name={tab} reason={PENDING_REASON[tab]} />}
      </div>
    </aside>
  );
}

function Overview({
  station,
  laporan,
  simulasiPreset,
  onTabChange,
}: {
  station: StationFeature;
  laporan: LaporanArea | null;
  simulasiPreset: Props["simulasiPreset"];
  onTabChange: (tab: Tab) => void;
}) {
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
                <p className="text-xs font-semibold leading-relaxed text-ink">
                  {score.kelas}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                  Peringkat{" "}
                  <span className="data-num font-semibold text-ink">
                    #{score.rank}
                  </span>{" "}
                  dari {score.rank_total} stasiun KRL.
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted">
                  Dinilai dalam jangkauan jalan kaki {score.minutes} menit.
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

        {score && (
          <>
            <p className="mt-3 border-l-2 border-accent pl-3 text-xs leading-relaxed text-ink-soft">
              {score.keputusan}
            </p>

            {/*
              Metadata keyakinan (F5-4). WAJIB tampil, tidak boleh disembunyikan:
              skor dari 3 variabel tidak sebanding dengan skor 5 variabel, dan
              pembaca tidak punya cara lain untuk tahu bedanya.
            */}
            <ConfidenceBar
              terpakai={score.variabel_terpakai}
              total={score.variabel_total}
              confidence={score.confidence}
            />

            {score.sensitivity && (
              <Kekokohan sens={score.sensitivity} rank={score.rank} total={score.rank_total} />
            )}

            <SimulasiSepi
              stationId={stationId}
              stationName={props.name}
              sepiResmi={score.sepi}
              rankResmi={score.rank}
              preset={simulasiPreset}
            />

            {/*
              Metodologi disembunyikan, bukan dihapus. Pembaca B2B perlu yakin
              angkanya berdasar, tetapi tidak perlu membaca rumusnya untuk itu.
              Yang ingin menggali tetap bisa — dan yang tidak, tidak dipaksa
              melewati dinding istilah sebelum sampai ke angkanya.
            */}
            <details className="mt-3 border-t border-canvas pt-3">
              <summary className="cursor-pointer text-[11px] text-muted hover:text-ink">
                Bagaimana angka ini dihitung
              </summary>
              <div className="mt-2 flex flex-col gap-2 text-[10px] leading-relaxed text-muted">
                <p>
                  SEPI adalah jumlah berbobot lima variabel. Bobotnya gabungan
                  Entropy Weighting (dari sebaran data) dan AHP (dari riset
                  literatur, consistency ratio 0,0072).
                </p>
                <p>
                  Nilainya dihitung per stasiun tanpa melihat stasiun lain,
                  sehingga menambah stasiun ke lingkup tidak mengubah angka
                  stasiun yang sudah ada.
                </p>
                <p>
                  Kedekatan TOPSIS{" "}
                  <span className="data-num">{score.topsis.toFixed(1)}</span>{" "}
                  dihitung terpisah sebagai pembanding relatif dalam satu
                  himpunan. Ia sengaja tidak dipakai menentukan kelas karena
                  nilainya bergeser kalau daftar stasiunnya berubah.
                </p>
              </div>
            </details>
          </>
        )}
      </Section>

      <Section
        title="Komponen SEPI — w₁T + w₂E + w₃A + w₄U + w₅C"
        pending={!score}
      >
        <ul className="flex flex-col gap-2.5">
          {SEPI_COMPONENTS.map((c) => {
            const value = score?.components[c.key];
            const share = shares?.[c.key];
            // `null` berarti belum diukur; 0 berarti terukur dan rendah. Bar
            // bergaris putus-putus dipakai untuk yang pertama supaya keduanya
            // tidak pernah terlihat sama.
            const belumDiukur = score != null && share === null;

            return (
              <li key={c.key} className="flex items-center gap-3">
                <span className="data-num w-3 shrink-0 text-xs font-semibold text-ink-soft">
                  {c.key}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs text-ink-soft">
                    {c.label}
                    {belumDiukur && (
                      <span className="ml-1 text-[10px] text-muted">
                        · menunggu {c.sumber}
                      </span>
                    )}
                  </span>
                  <span
                    className={`mt-1 block h-1.5 w-full ${
                      belumDiukur
                        ? "border border-dashed border-muted/60"
                        : "bg-canvas"
                    }`}
                  >
                    {!belumDiukur && (
                      <span
                        className="block h-full bg-accent"
                        style={{ width: `${Math.round((share ?? 0) * 100)}%` }}
                      />
                    )}
                  </span>
                </span>
                <span className="data-num w-20 shrink-0 text-right text-xs text-ink-soft">
                  {score ? formatKomponen(value) : "—"}
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
              label="Line KRL berhenti"
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

      {/*
        Volume penumpang sengaja ditaruh di bagian TERPISAH, bukan digabung ke
        "Isi jangkauan jalan kaki". Angka di bagian itu semuanya ikut menghitung
        skor; angka ini tidak. Cakupannya baru 10 dari 46 stasiun, di bawah
        ambang 70%, jadi ia konteks yang jujur ditampilkan — bukan komponen.
      */}
      {score?.passenger_volume && (
        <Section title="Volume penumpang">
          <dl className="flex flex-col gap-2">
            <Row
              label="Penumpang per hari"
              value={score.passenger_volume.per_day.toLocaleString("id-ID")}
              mono
            />
            <Row label="Periode" value={score.passenger_volume.period} mono />
            <Row label="Sumber" value={score.passenger_volume.source} />
          </dl>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            {score.passenger_volume.catatan}
          </p>
        </Section>
      )}

      <Section title="Profil stasiun">
        <dl className="flex flex-col gap-2">
          <Row label="Kode KAI" value={props.code} mono />
          <Row
            label="Line dilayani"
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

      {/*
        Footfall dan dwell-time tidak ada di sini karena PRD mengeluarkannya dari
        lingkup; penggantinya skala keramaian narasumber (ADJUSTMENT 7.18).
        Bagian ini dulu bertuliskan "menunggu survey Activity". Datanya sekarang
        ada, jadi yang ditampilkan hasil ukurnya - termasuk kalau hasilnya kosong.
      */}
      <Section title="Dari survey Activity" pending={!laporan}>
        {laporan ? (
          <>
            <dl className="flex flex-col gap-2">
              <Row
                label="Titik Activity di jangkauan"
                value={`${laporan.ringkasan.titik_activity} titik`}
                mono
              />
              <Row
                label="Media iklan tercatat"
                value={
                  laporan.ringkasan.media_iklan === null
                    ? "belum tercatat"
                    : `${laporan.ringkasan.media_iklan} (${laporan.ringkasan.media_iklan_kosong} kosong)`
                }
                mono
              />
              <Row
                label="Tenant tercatat"
                value={
                  laporan.ringkasan.tenant_tercatat
                    ? String(laporan.ringkasan.tenant_tercatat)
                    : "belum tercatat"
                }
                mono
              />
              <Row
                label="Catatan fasilitas"
                value={
                  laporan.ringkasan.fasilitas_positif + laporan.ringkasan.fasilitas_negatif
                    ? `${laporan.ringkasan.fasilitas_positif} baik · ${laporan.ringkasan.fasilitas_negatif} keluhan`
                    : "belum tercatat"
                }
              />
            </dl>
            <p className="mb-1.5 mt-3 text-[11px] text-muted">
              Keramaian menurut petugas ({laporan.ringkasan.jumlah_penilaian_keramaian} penilaian)
            </p>
            <ProfilBar profil={laporan.ringkasan.keramaian} />
            {laporan.areas.length > 0 && (
              <button
                type="button"
                onClick={() => onTabChange("Ad-Space")}
                className="mt-3 w-full border border-hair px-3 py-2 text-left text-xs text-ink-soft hover:border-ink hover:text-ink"
              >
                Lihat {laporan.areas.length} area pengamatan →
              </button>
            )}
          </>
        ) : (
          <p className="text-xs text-muted">Memuat…</p>
        )}
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

function TenantTab({
  station,
  laporan,
}: {
  station: StationFeature;
  laporan: LaporanArea | null;
}) {
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

  const areaTenant = (laporan?.areas ?? []).filter((a) => a.tenant.length > 0);

  return (
    <div className="flex flex-col">
      {areaTenant.length > 0 && (
        <Section title={`Tenant tercatat per area — ${areaTenant.length} area`}>
          <ul className="flex flex-col gap-3">
            {areaTenant.map((a) => (
              <li key={a.id} className="border border-hair p-3">
                <AreaKepala area={a} />
                <ul className="mt-2 flex flex-col gap-1">
                  {a.tenant.map((t, i) => (
                    <li key={i} className="flex items-baseline justify-between gap-2 text-xs">
                      <span className="text-ink">{t.nama}</span>
                      <span className="shrink-0 text-[10px] text-muted">
                        {t.kategori} · {t.status}
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="mt-2">
                  <ProfilBar profil={a.keramaian} />
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Diambil dari narasi Activity dengan kutipan terverifikasi. Area yang sama bisa
            punya lebih banyak tenant daripada yang tercatat.
          </p>
        </Section>
      )}

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

function Kekokohan({ sens, rank, total }: { sens: Sensitivitas; rank: number; total: number }) {
  const lebar = sens.peringkat_maks - sens.peringkat_min;
  const kokoh = lebar <= 3;
  return (
    <div className="mt-3 border-t border-canvas pt-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Kekokohan peringkat
        </span>
        <span className={`label-caps text-[9px] ${kokoh ? "text-ink" : "text-accent"}`}>
          {kokoh ? "Stabil" : "Bergantung bobot"}
        </span>
      </div>

      {/* Garis 1..total dengan rentang peringkat lintas skema dan titik peringkat resmi. */}
      <div className="relative mt-2 h-3">
        <span className="absolute left-0 right-0 top-1/2 h-px bg-hair" />
        <span
          className="absolute top-1/2 h-1.5 -translate-y-1/2 bg-accent/30"
          style={{
            left: `${((sens.peringkat_min - 1) / Math.max(1, total - 1)) * 100}%`,
            width: `${Math.max(1.5, (lebar / Math.max(1, total - 1)) * 100)}%`,
          }}
        />
        <span
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 bg-ink"
          style={{ left: `${((rank - 1) / Math.max(1, total - 1)) * 100}%` }}
        />
      </div>

      <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
        Di {sens.jumlah_skema} cara pembobotan, peringkatnya antara{" "}
        <span className="data-num text-ink-soft">
          #{sens.peringkat_min}–#{sens.peringkat_maks}
        </span>
        . Peluang masuk {sens.n_besar} besar saat bobot diacak:{" "}
        <span className="data-num text-ink-soft">
          {Math.round(sens.peluang_n_besar * 100)}%
        </span>
        . Stabil terhadap bobot belum tentu benar kalau datanya bias.
      </p>
    </div>
  );
}

const JENDELA: Array<{ key: keyof ProfilKeramaian; label: string; jam: string }> = [
  { key: "pagi", label: "Pagi", jam: "06–09" },
  { key: "siang", label: "Siang", jam: "09–16" },
  { key: "sore", label: "Sore", jam: "16–19" },
];

/** Profil keramaian tiga rentang PRD; rentang tanpa penilaian tampil putus-putus. */
function ProfilBar({ profil }: { profil: ProfilKeramaian }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {JENDELA.map((j) => {
        const p = profil[j.key];
        return (
          <div key={j.key}>
            <div className="flex items-baseline justify-between text-[10px] text-muted">
              <span>
                {j.label} <span className="data-num">{j.jam}</span>
              </span>
              <span className="data-num text-ink-soft">{p ? p.setara_1_5.toFixed(0) : "—"}</span>
            </div>
            <span
              className={`mt-1 block h-1.5 w-full ${p ? "bg-canvas" : "border border-dashed border-muted/60"}`}
            >
              {p && (
                <span
                  className="block h-full bg-accent"
                  style={{ width: `${Math.max(4, p.normal * 100)}%` }}
                />
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function AreaKepala({ area }: { area: AreaStasiun }) {
  return (
    <div>
      <p className="text-xs font-semibold leading-snug text-ink">{area.nama}</p>
      <p className="mt-0.5 text-[10px] text-muted">
        <span className="data-num">±{area.jarak_m} m</span> dari titik stasiun ·{" "}
        {area.jumlah_titik} catatan
        {area.dari_survey_tim > 0 && ` · ${area.dari_survey_tim} survey tim`}
      </p>
    </div>
  );
}

function AdSpaceTab({
  laporan,
  loading,
  error,
}: {
  laporan: LaporanArea | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <p className="p-4 text-xs text-muted">Memuat area…</p>;
  if (error || !laporan) {
    return <EmptyTab name="Ad-Space" reason={error ?? "Area belum bisa dimuat."} />;
  }

  const relevan = laporan.areas.filter(
    (a) => a.iklan.total > 0 || Object.values(a.keramaian).some(Boolean)
  );
  const diStasiun = relevan.filter((a) => a.di_stasiun);
  const sekitar = relevan.filter((a) => !a.di_stasiun);

  if (relevan.length === 0) {
    return (
      <EmptyTab
        name="Ad-Space"
        reason="Belum ada catatan Activity yang menyebut media iklan atau keramaian di stasiun ini. Katalog terisi otomatis begitu ada."
      />
    );
  }

  const kosong = relevan.reduce((n, a) => n + a.iklan.kosong, 0);

  return (
    <div className="flex flex-col">
      <Section title="Katalog ruang iklan per area">
        <p className="text-xs leading-relaxed text-ink-soft">
          {relevan.length} area dari catatan lapangan.{" "}
          {kosong > 0
            ? `${kosong} slot media masih kosong — itu yang bisa ditawarkan.`
            : "Belum ada slot kosong yang tercatat."}
        </p>
        <p className="mt-1 text-[10px] leading-relaxed text-muted">
          Area dibentuk dari catatan Activity yang berjarak kurang dari {laporan.eps_meter} m.
          Perkiraan nilai sewa belum ditampilkan karena belum ada pembanding harga yang sah.
        </p>
      </Section>

      {[
        { judul: `Di stasiun (≤ ${laporan.batas_area_stasiun_m} m)`, isi: diStasiun },
        { judul: "Kawasan sekitar", isi: sekitar },
      ]
        .filter((g) => g.isi.length > 0)
        .map((g) => (
          <Section key={g.judul} title={g.judul}>
            <ul className="flex flex-col gap-3">
              {g.isi.map((a) => (
                <li key={a.id} className="border border-hair p-3">
                  <AreaKepala area={a} />

                  {a.iklan.total > 0 ? (
                    <ul className="mt-2 flex flex-col gap-1">
                      {a.iklan.per_jenis.map((j) => (
                        <li key={j.jenis} className="flex items-baseline justify-between gap-2 text-xs">
                          <span className="text-ink">{j.jenis}</span>
                          <span className="data-num shrink-0 text-[11px] text-ink-soft">
                            {j.terpakai} terpakai
                            {j.kosong > 0 && (
                              <span className="ml-1 font-semibold text-accent">· {j.kosong} kosong</span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-[11px] text-muted">Media iklan belum tercatat di area ini.</p>
                  )}

                  <div className="mt-2">
                    <ProfilBar profil={a.keramaian} />
                  </div>

                  {a.iklan.kutipan[0] && (
                    <p className="mt-2 border-l-2 border-hair pl-2 text-[10px] italic leading-relaxed text-muted">
                      “{a.iklan.kutipan[0]}”
                    </p>
                  )}

                  {a.fasilitas.some((f) => (f.sentimen ?? 0) < 0) && (
                    <p className="mt-2 text-[10px] leading-relaxed text-ink-soft">
                      <span className="label-caps mr-1 text-[9px] text-accent">Peluang CSR</span>
                      {a.fasilitas
                        .filter((f) => (f.sentimen ?? 0) < 0)
                        .map((f) => f.ringkasan)
                        .join("; ")}
                    </p>
                  )}

                  {a.foto.length > 0 && (
                    <div className="mt-2 flex gap-1.5 overflow-x-auto">
                      {a.foto.map((url) => (
                        <a key={url} href={url} target="_blank" rel="noreferrer" className="shrink-0">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={url}
                            alt={`Foto ${a.nama}`}
                            loading="lazy"
                            className="h-14 w-20 border border-hair object-cover"
                          />
                        </a>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        ))}
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

/**
 * Metadata keyakinan yang dipakai ulang di seluruh panel (F5-4).
 *
 * Menampilkan berapa dari lima variabel SEPI yang benar-benar terukur. Ini
 * bukan hiasan: skor yang disusun dari tiga variabel tidak sebanding dengan
 * skor lima variabel, dan pembaca tidak punya cara lain untuk mengetahuinya.
 * Karena itu ia selalu tampil, bukan hanya ketika datanya kurang — angka
 * "5 dari 5" sama informatifnya dengan "3 dari 5".
 */
function ConfidenceBar({
  terpakai,
  total,
  confidence,
}: {
  terpakai: number;
  total: number;
  confidence: number;
}) {
  const { teks, nada } = confidenceLabel(terpakai, total);

  const warna =
    nada === "penuh"
      ? "bg-accent"
      : nada === "sedang"
        ? "bg-amber-500"
        : "bg-muted";

  return (
    <div className="mt-3 border-t border-canvas pt-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Keyakinan data
        </span>
        <span className="data-num text-[11px] text-ink-soft">
          {terpakai}/{total} variabel · {confidence.toFixed(2)}
        </span>
      </div>

      <div className="mt-1.5 flex gap-1">
        {Array.from({ length: total }, (_, i) => (
          <span
            key={i}
            className={`h-1.5 flex-1 ${i < terpakai ? warna : "border border-dashed border-muted/60"}`}
          />
        ))}
      </div>

      <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
        {teks}.{" "}
        {terpakai < total
          ? `Skor disusun dari ${terpakai} variabel, jadi tidak sebanding dengan stasiun yang datanya lengkap.`
          : "Seluruh variabel terukur."}
      </p>
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
