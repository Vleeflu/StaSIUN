"use client";

import { type ReactNode, useState } from "react";

import KatalogModal from "@/components/KatalogModal";
import SimulasiSepi from "@/components/SimulasiSepi";
import { useSponsorship } from "@/hooks/useSponsorship";
import { useStationAreas } from "@/hooks/useStationAreas";
import { useStationNaming } from "@/hooks/useStationNaming";
import { useStationPaparan } from "@/hooks/useStationPaparan";
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
  LaporanSponsorship,
  ProfilKeramaian,
  Sensitivitas,
  StationFeature,
} from "@/types/station";

const TABS = ["Ikhtisar", "Ad-Space", "Tenant", "Naming"] as const;
export type Tab = (typeof TABS)[number];

const SCORE_MINUTES = 10;

// PENDING_REASON dihapus: tab Naming tidak lagi kosong. Alasan nilai kontrak
// masih kosong kini datang dari backend (`alasan_nilai_kosong`), supaya satu
// keputusan tidak ditulis dua kali di dua tempat yang bisa berbeda isi.

// Sumber data, LENGKAP DENGAN TAUTANNYA.
//
// Sebelumnya bagian ini hanya berisi nama sumber tanpa alamat - pembaca yang
// ingin memeriksa harus menebak sendiri harus ke mana. Padahal justru pembaca
// semacam itu yang paling perlu dilayani: regulator dan calon mitra menilai
// sebuah angka dari asal-usulnya, bukan dari tampilannya.
//
// Dataset Mission (StrukGo, MenuGo, PropertiGo) sengaja tidak ada di sini:
// cakupannya di wilayah studi belum memadai, jadi tidak ada satu variabel pun
// yang boleh bergantung padanya.
const SUMBER_DATA: { nama: string; untuk: string; url: string }[] = [
  {
    nama: "MAPID Activity Community Maps",
    untuk: "catatan survei lapangan, keterangan pedagang dan petugas",
    url: "https://geo.mapid.io/",
  },
  {
    nama: "Isochrone GeoMAPID",
    untuk: "batas wilayah yang terjangkau jalan kaki",
    url: "https://geo.mapid.io/",
  },
  {
    nama: "OpenStreetMap",
    untuk: "jaringan jalan pejalan kaki, titik minat, guna lahan",
    url: "https://www.openstreetmap.org/",
  },
  {
    nama: "Statistik Transportasi DKI Jakarta — BPS",
    untuk: "volume penumpang stasiun",
    url: "https://jakarta.bps.go.id/",
  },
  {
    nama: "Colliers Indonesia — laporan pasar ritel",
    untuk: "pembanding harga sewa ruang komersial",
    url: "https://www.colliers.com/id-id/research",
  },
  {
    nama: "Lestari Ads — benchmark tarif iklan luar ruang",
    untuk: "acuan tarif per seribu paparan",
    url: "https://www.lestariads.com/en/blog/marketing/expected-cpm-cpc-and-roi-benchmarks-for-ooh-advertising-in-indonesia-2025-data.html",
  },
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
          <AdSpaceTab
            stationId={stationId}
            stationName={props.name}
            laporan={areas.laporan}
            loading={areas.loading}
            error={areas.error}
          />
        )}
        {tab === "Tenant" && <TenantTab station={station} laporan={areas.laporan} />}
        {tab === "Naming" && <NamingTab stationId={stationId} />}
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

      {/*
        Judulnya dulu berbunyi "Komponen SEPI — w₁T + w₂E + w₃A + w₄U + w₅C".
        Rumus itu benar, tetapi ia menyapa pembaca dengan notasi sebelum sempat
        memberi tahu apa yang sedang dilihat. Rumusnya tetap ada, satu klik di
        bawah, buat yang memang mencarinya.
      */}
      <Section title="Yang membentuk skor ini" pending={!score}>
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

        <details className="mt-3 border-t border-canvas pt-3">
          <summary className="cursor-pointer text-[11px] text-muted hover:text-ink">
            Apa arti kelima variabel ini?
          </summary>
          <dl className="mt-2 flex flex-col gap-2">
            {SEPI_COMPONENTS.map((c) => (
              <div key={c.key}>
                <dt className="text-[11px] font-semibold text-ink-soft">
                  {c.key} · {c.label}
                </dt>
                <dd className="text-[10px] leading-relaxed text-muted">{c.arti}</dd>
              </div>
            ))}
            <p className="mt-1 text-[10px] leading-relaxed text-muted">
              Kelimanya dijumlahkan dengan bobot berbeda — variabel yang lebih
              menentukan diberi porsi lebih besar. Nilainya 0 sampai 1: makin
              tinggi, makin kuat sisi itu di stasiun ini.
            </p>
          </dl>
        </details>
      </Section>

      {score && (
        <Section title={`Di sekitar stasiun — jalan kaki ${score.minutes} menit`}>
          <p className="mb-2 text-xs leading-relaxed text-ink-soft">
            Yang bisa dijangkau calon pembeli dan pengunjung tanpa naik kendaraan
            lagi. Angka-angka ini ikut membentuk skor di atas.
          </p>
          <dl className="flex flex-col gap-2">
            <Row
              label="Luas wilayah yang terjangkau"
              value={`${score.detail.area_km2.toFixed(2)} km²`}
              mono
            />
            <Row
              label="Jalur KRL yang berhenti di sini"
              value={String(score.detail.line_count)}
              mono
            />
            <Row
              label="Halte bus di sekitarnya"
              value={String(score.detail.halte_count)}
              mono
            />
            <Row
              label="Stasiun moda lain (MRT, LRT)"
              value={String(score.detail.other_mode_count)}
              mono
            />
          </dl>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Luasnya dihitung mengikuti jalan yang benar-benar bisa dilewati
            pejalan kaki, bukan lingkaran di peta — jadi kawasan yang terpotong
            rel atau jalan besar tidak ikut terhitung.
          </p>
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
      <Section title="Hasil pengamatan lapangan" pending={!laporan}>
        {laporan ? (
          <>
            <p className="mb-2 text-xs leading-relaxed text-ink-soft">
              Dicatat langsung di lokasi oleh tim survei, termasuk keterangan dari
              pedagang dan petugas yang sehari-hari ada di sana.
            </p>
            <dl className="flex flex-col gap-2">
              {/*
                "Titik Activity" sengaja tidak ditampilkan lagi sebagai baris
                sendiri. Bagi pembaca di luar tim, jumlah titik pengamatan tidak
                menjawab pertanyaan apa pun yang ia bawa ke halaman ini - ia
                angka proses, bukan temuan. Jumlahnya tetap terbaca di catatan
                kaki bagian ini sebagai ukuran seberapa tebal dasarnya.
              */}
              <Row
                label="Media iklan terpasang"
                value={
                  laporan.ringkasan.media_iklan === null
                    ? "belum tercatat"
                    : `${laporan.ringkasan.media_iklan} (${laporan.ringkasan.media_iklan_kosong} kosong)`
                }
                mono
              />
              <Row
                label="Usaha yang berjualan di sini"
                value={
                  laporan.ringkasan.tenant_tercatat
                    ? String(laporan.ringkasan.tenant_tercatat)
                    : "belum tercatat"
                }
                mono
              />
              <Row
                label="Kondisi fasilitas"
                value={
                  laporan.ringkasan.fasilitas_positif + laporan.ringkasan.fasilitas_negatif
                    ? `${laporan.ringkasan.fasilitas_positif} baik · ${laporan.ringkasan.fasilitas_negatif} perlu dibenahi`
                    : "belum tercatat"
                }
              />
            </dl>
            <p className="mb-1.5 mt-3 text-[11px] text-muted">
              Seberapa ramai menurut orang yang bekerja di sana
            </p>
            <ProfilBar profil={laporan.ringkasan.keramaian} />
            {laporan.areas.length > 0 && (
              <button
                type="button"
                onClick={() => onTabChange("Ad-Space")}
                className="mt-3 w-full border border-hair px-3 py-2 text-left text-xs text-ink-soft hover:border-ink hover:text-ink"
              >
                Lihat {laporan.areas.length} titik pengamatan di tab Ad-Space →
              </button>
            )}
            <p className="mt-2 text-[10px] leading-relaxed text-muted">
              Dasarnya {laporan.ringkasan.titik_activity} catatan lapangan dan{" "}
              {laporan.ringkasan.jumlah_penilaian_keramaian} penilaian keramaian
              di kawasan ini.
            </p>
          </>
        ) : (
          <p className="text-xs text-muted">Memuat…</p>
        )}
      </Section>

      <Section title="Dari mana datanya">
        <p className="mb-2 text-xs leading-relaxed text-ink-soft">
          Setiap angka di halaman ini bisa ditelusuri ke sumbernya. Tautan di
          bawah menuju sumber aslinya, bukan salinan kami.
        </p>
        <ul className="flex flex-col gap-1.5">
          {SUMBER_DATA.map((s) => (
            <li key={s.nama} className="text-[11px] leading-relaxed">
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-ink-soft underline decoration-hair underline-offset-2 hover:text-ink hover:decoration-ink"
              >
                {s.nama} ↗
              </a>
              <span className="text-muted"> — {s.untuk}</span>
            </li>
          ))}
        </ul>
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

/**
 * Tab Naming - status hak penamaan, bukan valuasi.
 *
 * Yang ditampilkan hanya yang benar-benar diketahui: apakah hak penamaan
 * stasiun ini sudah terjual dan kepada siapa, ditambah kelompok pembandingnya.
 * Nilai kontrak dalam rupiah dibiarkan kosong BESERTA alasannya - ia butuh
 * pembanding transaksi nyata yang belum ada, dan angka tebakan pada fitur
 * semacam ini justru yang paling mudah dikutip orang lepas dari konteksnya.
 */
function NamingTab({ stationId }: { stationId: number | null }) {
  const { naming, loading, error } = useStationNaming(stationId);

  if (loading) return <p className="p-4 text-xs text-muted">Memuat status naming…</p>;
  if (error || !naming) {
    return <EmptyTab name="Naming" reason={error ?? "Status naming belum bisa dimuat."} />;
  }

  const { status, pembanding } = naming;

  return (
    <div className="flex flex-col">
      <Section title="Status hak penamaan">
        {status ? (
          <p className="text-xs leading-relaxed text-ink-soft">
            {status.bersponsor ? (
              <>
                Sudah terjual ke <strong>{status.sponsor}</strong>. Nama dasarnya{" "}
                {status.nama_dasar}, jaringan {status.jaringan}.
              </>
            ) : (
              <>
                Belum terjual. Stasiun {status.jaringan} ini masih memakai nama
                dasarnya, {status.nama_dasar}.
              </>
            )}
          </p>
        ) : (
          <p className="text-xs leading-relaxed text-ink-soft">
            Di luar lingkup penilaian.
          </p>
        )}
        <p className="mt-2 text-[10px] leading-relaxed text-muted">{naming.catatan}</p>
      </Section>

      <Section title="Kelompok pembanding">
        <p className="text-xs leading-relaxed text-ink-soft">
          Dari {pembanding.total} stasiun MRT dan LRT,{" "}
          <span className="data-num font-semibold text-ink">{pembanding.bersponsor}</span>{" "}
          hak penamaannya sudah terjual dan {pembanding.belum} belum.
        </p>
        <div className="mt-2 flex h-2 w-full overflow-hidden bg-canvas">
          <span
            className="block h-full bg-accent"
            style={{ width: `${(pembanding.bersponsor / pembanding.total) * 100}%` }}
          />
        </div>
        <ul className="mt-2 flex flex-wrap gap-1">
          {pembanding.sponsor.map((s) => (
            <li key={s} className="border border-hair px-2 py-0.5 text-[11px]">
              {s}
            </li>
          ))}
        </ul>
        <p className="mt-2 text-[10px] leading-relaxed text-muted">
          Stasiun KAI Commuter sengaja tidak ikut dihitung: ia tidak pernah
          memperjualbelikan hak penamaan dengan cara yang sama, sehingga
          memasukkannya sebagai &quot;belum terjual&quot; akan mencampur dua sebab yang
          berbeda.
        </p>
      </Section>

      <Section title="Nilai kontrak">
        <p className="text-xs leading-relaxed text-ink-soft">Belum ditampilkan.</p>
        <p className="mt-1 text-[10px] leading-relaxed text-muted">
          {naming.alasan_nilai_kosong}
        </p>
      </Section>

      {naming.selisih_daftar.length > 0 && (
        <Section title="Perlu diperiksa">
          <ul className="flex flex-col gap-1 text-[11px] leading-relaxed text-ink-soft">
            {naming.selisih_daftar.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

/**
 * Nama fungsi ruang dalam kalimat, bukan istilah tabel.
 *
 * "kantor" dan "hunian" enak dibaca sebagai label pendek di grafik, tetapi
 * janggal begitu masuk ke tengah kalimat - "wilayahnya lebih banyak hunian"
 * terdengar seperti potongan basis data. Di dalam kalimat dipakai bentuk yang
 * biasa diucapkan orang.
 */
function labelKelas(kelas: string | null | undefined): string {
  const peta: Record<string, string> = {
    hunian: "permukiman",
    kantor: "perkantoran",
    niaga: "pertokoan",
    wisata: "tempat wisata",
    industri: "kawasan industri",
  };
  return kelas ? peta[kelas] ?? kelas : "—";
}

/** Warna per fungsi ruang. Sengaja tetap, supaya satu warna berarti satu hal. */
const WARNA_KELAS: Record<string, string> = {
  hunian: "bg-sky-500",
  kantor: "bg-amber-500",
  niaga: "bg-emerald-500",
  wisata: "bg-fuchsia-500",
  industri: "bg-zinc-500",
};

/** Satu baris komposisi: batang berwarna per fungsi, ditulis porsinya. */
function BatangKomposisi({ porsi }: { porsi: Record<string, number> | null }) {
  if (!porsi) return null;
  const isi = Object.entries(porsi)
    .filter(([, v]) => v > 0.005)
    .sort((a, b) => b[1] - a[1]);
  if (isi.length === 0) return null;
  return (
    <>
      <div className="mt-1 flex h-2 w-full overflow-hidden bg-canvas">
        {isi.map(([kelas, v]) => (
          <span
            key={kelas}
            className={`block h-full ${WARNA_KELAS[kelas] ?? "bg-zinc-400"}`}
            style={{ width: `${v * 100}%` }}
          />
        ))}
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-muted">
        {isi.map(([kelas, v]) => `${kelas} ${Math.round(v * 100)}%`).join(" · ")}
      </p>
    </>
  );
}

/**
 * Profil paparan - siapa yang MELINTAS, bukan siapa yang berbelanja.
 *
 * Komposisi kawasan ditampilkan menurut DUA ukuran sekaligus, bukan dipilih
 * salah satu: luas tanah mengecilkan menara, luas lantai mengecilkan
 * permukiman padat. Kalau keduanya tidak sepakat, ketidaksepakatan itu yang
 * ditampilkan - ia gambaran paling jujur tentang kawasannya, bukan gangguan.
 */
function PaparanSection({ stationId }: { stationId: number | null }) {
  const { paparan, loading, error } = useStationPaparan(stationId);

  if (loading) return <p className="p-4 text-xs text-muted">Memuat…</p>;
  if (error || !paparan) return null;

  const { kawasan, keramaian, audiens, waktu_singgah, format_iklan_disarankan, dasar } = paparan;
  const waktu = Object.entries(keramaian);

  // SATU batang utama, bukan dua berdampingan.
  //
  // Versi sebelumnya menampilkan komposisi menurut luas tanah DAN luas lantai
  // sekaligus, dan Villyan membacanya sebagai sistem yang ragu pada dirinya
  // sendiri - dua grafik yang seolah saling membantah. Padahal keduanya bukan
  // saling membantah, melainkan menjawab pertanyaan berbeda.
  //
  // Maka yang tampil satu: pembagian wilayahnya. Ukuran kedua tetap ada, tetapi
  // sebagai pemeriksa silang di balik toggle, dan saat keduanya berbeda itu
  // disampaikan sebagai TEMUAN dalam satu kalimat - bukan sebagai dua grafik
  // yang membuat pembaca harus menengahi sendiri.
  const tanah = kawasan?.per_ukuran?.luas_tanah;
  const lantai = kawasan?.per_ukuran?.luas_lantai;

  return (
    <Section title="Profil paparan">
      <p className="text-xs leading-relaxed text-ink-soft">
        Profil orang yang melintas di kawasan stasiun ini, sebagai dasar
        penentuan format iklan yang tepat.
      </p>

      {tanah && (
        <div className="mt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Komposisi kawasan sekitar
          </p>
          <BatangKomposisi porsi={tanah.porsi} />
          {kawasan?.sepakat === false && lantai && (
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-soft">
              Perlu dicatat: secara luas wilayah kawasan ini didominasi{" "}
              {labelKelas(tanah.kelas_terbesar)}, namun bangunan bertingkatnya
              didominasi <strong>{labelKelas(lantai.kelas_terbesar)}</strong>.
              Keduanya sama-sama memengaruhi siapa yang melintas di sini.
            </p>
          )}
          {lantai && (
            <details className="mt-1.5">
              <summary className="cursor-pointer text-[10px] text-muted hover:text-ink">
                Tinjau berdasarkan luas bangunan
              </summary>
              <div className="mt-1.5">
                <BatangKomposisi porsi={lantai.porsi} />
                <p className="mt-1 text-[10px] leading-relaxed text-muted">
                  Perhitungan di atas berdasarkan luas wilayah, sedangkan yang
                  ini berdasarkan luas lantai bangunan — sehingga gedung
                  bertingkat memperoleh bobot lebih besar. Permukiman padat yang
                  tidak terpetakan per bangunan cenderung terhitung lebih kecil.
                </p>
              </div>
            </details>
          )}
        </div>
      )}

      {waktu.length > 0 && (
        <div className="mt-3 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Tingkat keramaian sepanjang hari
          </p>
          <ul className="mt-1.5 flex flex-col gap-2">
            {waktu.map(([rentang, v]) => (
              <li key={rentang}>
                <div className="flex items-center gap-2 text-xs">
                  <span className="w-12 shrink-0 capitalize text-ink-soft">{rentang}</span>
                  <span className="flex h-2 flex-1 overflow-hidden bg-canvas">
                    <span
                      className="block h-full bg-accent"
                      style={{
                        width: `${
                          ((v.nilai - v.skala_min) / (v.skala_maks - v.skala_min)) * 100
                        }%`,
                      }}
                    />
                  </span>
                  <span className="data-num shrink-0 text-xs text-ink-soft">
                    {v.nilai}/{v.skala_maks}
                  </span>
                </div>
                <p className="ml-14 text-[10px] leading-relaxed text-muted">{v.arti}</p>
              </li>
            ))}
          </ul>
          {dasar.puncak_keramaian && (
            <p className="mt-1.5 text-[11px] leading-relaxed text-ink-soft">
              Puncak keramaian terjadi pada {dasar.puncak_keramaian}.
            </p>
          )}
        </div>
      )}

      {audiens.length > 0 && (
        <div className="mt-3 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Profil pengunjung
          </p>
          <ul className="mt-1.5 flex flex-wrap gap-1">
            {audiens.map((a) => (
              <li
                key={a.kelompok}
                title={a.dasar}
                className="border border-hair px-2 py-0.5 text-[11px]"
              >
                {a.kelompok}
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
            Disimpulkan dari peruntukan lahan di sekitar stasiun yang disilangkan
            dengan pola keramaian per rentang waktu — bukan dari penilaian
            terhadap pengunjung yang melintas.
          </p>
        </div>
      )}

      <div className="mt-3 border-t border-canvas pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Format iklan yang disarankan
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
          Waktu singgah di stasiun ini <strong>{waktu_singgah.label}</strong> —{" "}
          {waktu_singgah.alasan}.
        </p>
        {format_iklan_disarankan.bentuk && (
          <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
            Format yang paling sesuai adalah{" "}
            <strong>{format_iklan_disarankan.bentuk}</strong>, karena{" "}
            {format_iklan_disarankan.alasan}.
          </p>
        )}
        {format_iklan_disarankan.catatan && (
          <p className="mt-1.5 border-l-2 border-accent pl-2 text-[11px] leading-relaxed text-ink-soft">
            {format_iklan_disarankan.catatan}
          </p>
        )}
      </div>

      <details className="mt-3 border-t border-canvas pt-3">
        <summary className="cursor-pointer text-[11px] text-muted hover:text-ink">
          Dasar penyusunan profil ini
        </summary>
        <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
          Disusun dari {dasar.jumlah_narasi} pengamatan lapangan dan{" "}
          {dasar.jumlah_penilaian_keramaian} penilaian keramaian di kawasan ini.{" "}
          {dasar.catatan_privasi}
        </p>
      </details>
    </Section>
  );
}

function AdSpaceTab({
  stationId,
  stationName,
  laporan,
  loading,
  error,
}: {
  stationId: number | null;
  stationName: string;
  laporan: LaporanArea | null;
  loading: boolean;
  error: string | null;
}) {
  const { laporan: sponsorship } = useSponsorship(stationId);
  const [katalog, setKatalog] = useState<"iklan" | "fasilitas" | null>(null);

  if (loading) return <p className="p-4 text-xs text-muted">Memuat…</p>;
  if (error || !laporan) {
    return <EmptyTab name="Ad-Space" reason={error ?? "Data belum bisa dimuat."} />;
  }

  const areaIklan = laporan.areas.filter((a) => a.iklan.total > 0);
  // Total media saja. Terisi atau kosong TIDAK ditampilkan: yang menyewa ruang
  // iklan berurusan dengan pengelola, dan status keterisian pada hari survei
  // sudah usang begitu halaman ini dibuka.
  const totalMedia = areaIklan.reduce((n, a) => n + a.iklan.total, 0);
  const peluang = sponsorship?.peluang ?? [];

  // Cuplikan: dua teratas saja. Yang di stasiun didahulukan, lalu yang paling
  // banyak ruang kosongnya - urutan yang sama dengan urutan minat pembacanya.
  const cuplikanIklan = [...areaIklan]
    .sort((a, b) => Number(b.di_stasiun) - Number(a.di_stasiun) || b.iklan.total - a.iklan.total)
    .slice(0, 2);

  return (
    <div className="flex flex-col">
      <PaparanSection stationId={stationId} />

      <Section title="Inventaris ruang iklan">
        {areaIklan.length === 0 ? (
          <p className="text-xs leading-relaxed text-muted">
            Belum ada media iklan yang tercatat di stasiun ini. Daftar akan
            terisi otomatis seiring bertambahnya pengamatan lapangan.
          </p>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-ink-soft">
              Tercatat <strong>{totalMedia} media iklan</strong> yang tersebar di{" "}
              {areaIklan.length} titik di stasiun ini dan sekitarnya.
            </p>

            <ul className="mt-2 flex flex-col gap-2">
              {cuplikanIklan.map((a) => (
                <li key={a.id} className="border border-hair p-2.5">
                  <p className="text-xs font-semibold leading-snug text-ink">{a.nama}</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
                    {a.iklan.total > 0
                      ? `${a.iklan.total} media iklan`
                      : "Media iklan tercatat, jumlahnya tidak dicatat surveyor"}
                    {a.waktu_singgah?.label && a.waktu_singgah.label !== "tidak terbaca" && (
                      <> · waktu singgah {a.waktu_singgah.label}</>
                    )}
                  </p>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => setKatalog("iklan")}
              className="mt-2 w-full border border-hair px-3 py-2 text-xs text-ink-soft hover:border-ink hover:text-ink"
            >
              Buka katalog lengkap · {areaIklan.length} titik →
            </button>
          </>
        )}
      </Section>

      <Section title="Peluang sponsorship fasilitas">
        {peluang.length === 0 ? (
          <p className="text-xs leading-relaxed text-muted">
            Belum ada fasilitas yang dapat ditawarkan sebagai kemitraan di
            stasiun ini.
          </p>
        ) : (
          <>
            <p className="text-xs leading-relaxed text-ink-soft">
              {peluang.length} fasilitas teridentifikasi perlu pembenahan dan
              dapat ditawarkan sebagai kemitraan: sponsor menanggung biaya
              perbaikan, mereknya melekat pada fasilitas yang diperbaiki.
            </p>

            <ul className="mt-2 flex flex-col gap-2">
              {peluang.slice(0, 2).map((p) => (
                <li key={p.id} className="border border-hair p-2.5">
                  <p className="text-xs font-semibold leading-snug text-ink">
                    {p.usulan.bentuk}
                  </p>
                  <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
                    {p.jenis}
                    {p.jumlah_laporan > 1 && ` · dilaporkan ${p.jumlah_laporan} kali`}
                    {p.usulan.kewenangan !== "aset stasiun" && " · perlu izin pengelola jalan"}
                  </p>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => setKatalog("fasilitas")}
              className="mt-2 w-full border border-hair px-3 py-2 text-xs text-ink-soft hover:border-ink hover:text-ink"
            >
              Buka katalog lengkap · {peluang.length} fasilitas →
            </button>
          </>
        )}
      </Section>

      {katalog && (
        <KatalogModal
          stasiun={stationName}
          areas={laporan.areas}
          sponsorship={sponsorship}
          segmenAwal={katalog}
          onClose={() => setKatalog(null)}
        />
      )}
    </div>
  );
}

// SponsorshipSection, Penyaringan, dan judulPendek DIHAPUS dari sini.
// Katalog sponsorship kini hidup di KatalogModal, satu halaman bersama katalog
// ruang iklan — dua daftar yang tujuannya berbeda, dipisahkan segmen, alih-alih
// ditumpuk di panel samping selebar 400 px.

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

/**
 * Judul post Activity sering memuat nama stasiun dan keterangan panjang.
 * Dipotong di penghubung yang wajar supaya kartu tetap terbaca, bukan dipotong
 * di tengah kata.
 */
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
