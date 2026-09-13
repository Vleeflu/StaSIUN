"use client";

import { type ReactNode, useState } from "react";

import KatalogModal from "@/components/KatalogModal";
import PeringkatModal from "@/components/PeringkatModal";
import SimulasiSepi from "@/components/SimulasiSepi";
import TenantModal from "@/components/TenantModal";
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
    nama: "Statistik Transportasi DKI Jakarta, BPS",
    untuk: "volume penumpang stasiun",
    url: "https://jakarta.bps.go.id/",
  },
  {
    nama: "Colliers Indonesia, laporan pasar ritel",
    untuk: "pembanding harga sewa ruang komersial",
    url: "https://www.colliers.com/id-id/research",
  },
  {
    nama: "Lestari Ads, benchmark tarif iklan luar ruang",
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
  /** Menyorot satu titik katalog di peta; null menghapus sorotannya. */
  onSorot: (titik: { lon: number; lat: number; nama: string } | null) => void;
  onClose: () => void;
};

export default function StationPanel({
  station,
  tab,
  onTabChange,
  simulasiPreset,
  onSorot,
  onClose,
}: Props) {
  const setTab = onTabChange;
  const props = station.properties;
  const stationId = typeof station.id === "number" ? station.id : null;
  const areas = useStationAreas(stationId);
  const codes = parseLines(props.lines);

  return (
    <aside className="fixed inset-x-0 bottom-0 top-[52px] z-30 flex w-full flex-col overflow-hidden border-ink bg-panel sm:static sm:inset-auto sm:z-auto sm:w-[400px] sm:shrink-0 sm:border-l">
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

        {(codes.length > 1 || !props.served || props.survei_tim) && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {codes.length > 1 && (
              <span className="label-caps border border-ink px-2 py-1 text-ink">
                Interchange
              </span>
            )}
            {/*
              Lencana survei lapangan. Sengaja TIDAK berbunyi "data lengkap"
              maupun "premium": dari sembilan stasiun yang didatangi tim, hanya
              satu yang variabel skornya benar-benar lengkap. Yang dijanjikan
              lencana ini persis yang dibawa pulang surveyor - catatan, foto,
              inventaris media iklan, dan penilaian keramaian dari narasumber.
            */}
            {props.survei_tim && (
              <span className="label-caps border border-accent bg-accent px-2 py-1 text-white">
                Disurvei langsung
                {props.survei_titik ? ` · ${props.survei_titik} titik` : ""}
              </span>
            )}
            {!props.served && (
              <span className="label-caps border border-hair px-2 py-1 text-muted">
                Dilintasi tanpa berhenti
              </span>
            )}
          </div>
        )}

        {/*
          Keterangan survei DILIPAT, bukan ditampilkan penuh.

          Kepala panel ini tidak ikut bergulir, jadi tiap barisnya langsung
          memotong ruang baca isi tab di bawahnya. Paragraf enam baris di sini
          menyisakan kurang dari separuh tinggi panel untuk skor, komponen, dan
          rekomendasi - padahal itu yang dicari pembaca, sedangkan keterangan
          survei cukup dibaca sekali.

          Angka terpentingnya tetap terlihat tanpa dibuka, menempel di lencana.
        */}
        {props.survei_tim && (
          <details className="mt-2">
            <summary className="cursor-pointer text-[11px] text-muted hover:text-ink">
              Apa artinya stasiun ini disurvei langsung?
            </summary>
            <p className="mt-1.5 border-l-2 border-accent pl-2 text-[11px] leading-relaxed text-muted">
              Tim mendatangi stasiun ini dan mencatat{" "}
              <strong className="text-ink">
                {props.survei_titik ?? 0} titik pengamatan
              </strong>
              {(props.survei_skala ?? 0) > 0 && (
                <>
                  {" "}
                  serta{" "}
                  <strong className="text-ink">
                    {props.survei_skala} penilaian keramaian
                  </strong>{" "}
                  dari petugas dan pelaku usaha di lokasi
                </>
              )}
              . Katalog media iklan, foto lapangan, dan pola keramaian pada
              halaman ini bersumber dari pengamatan tersebut. Kelengkapan variabel
              skornya disajikan terpisah melalui indikator keyakinan.
            </p>
          </details>
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
            onSorot={onSorot}
          />
        )}
        {tab === "Tenant" && (
          <TenantTab station={station} laporan={areas.laporan} onSorot={onSorot} />
        )}
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
  // Variabel yang nilainya identik di SELURUH stasiun. Ia tetap ditampilkan -
  // menyembunyikannya justru menyembunyikan keterbatasan datanya - tetapi
  // labelnya harus berbeda dari "estimasi" biasa. Estimasi yang berbeda-beda
  // per stasiun masih membedakan sesuatu; yang seragam tidak membedakan apa pun.
  const seragam: string[] = score?.seragam_di_semua_stasiun ?? [];
  // Daftar peringkat mana yang sedang dibuka. Null berarti tertutup.
  const [peringkat, setPeringkat] = useState<string | null>(null);

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
                  <button
                    type="button"
                    onClick={() => setPeringkat("sepi")}
                    className="data-num font-semibold text-ink underline decoration-hair underline-offset-2 hover:decoration-ink"
                  >
                    #{score.rank}
                  </button>{" "}
                  dari {score.rank_total} stasiun KRL, berada di atas{" "}
                  <span className="data-num">{score.persentil}%</span> stasiun
                  lainnya.
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
            {score ? score.sepi.toFixed(1) : "-"}
            <span className="text-base font-medium text-muted">/100</span>
          </p>
        </div>

        {score && (
          <>
            <p className="mt-3 border-l-2 border-accent pl-3 text-xs leading-relaxed text-ink-soft">
              {score.keputusan}
            </p>

            {/*
              TRIASE, inti gunanya klasifikasi SEPI, dan selama ini tidak
              pernah sampai ke layar. Pembaca melihat angka 67,5 tanpa tahu
              angka itu menyarankan fitur mana yang masuk akal dikejar.
            */}
            {score.triase && (
              <div className="mt-3 border border-hair p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Yang paling masuk akal dikejar di sini
                </p>
                <p className="mt-1.5 text-xs font-semibold leading-relaxed text-ink">
                  {score.triase.fokus}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
                  {score.triase.alasan}
                </p>
                <p className="mt-1 text-[10px] leading-relaxed text-muted">
                  Sebaiknya dihindari: {score.triase.hindari.toLowerCase()}.
                </p>
              </div>
            )}

            {/*
              CEI ditampilkan BERDAMPINGAN dengan SEPI, bukan menggantikannya.
              Keduanya menjawab pertanyaan berbeda: SEPI soal potensi ekonomi
              kawasan, CEI soal nilai paparan iklan. Menampilkan satu saja
              membuat pembaca memakai angka yang salah untuk keputusannya.
            */}
            {score.paparan?.cei !== null && score.paparan?.cei !== undefined && (
              <div className="mt-3 border-t border-canvas pt-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Nilai paparan iklan
                  </span>
                  <span className="data-num text-sm font-semibold text-ink">
                    {score.paparan.cei.toFixed(1)}
                    <span className="text-[10px] font-medium text-muted">/100</span>
                  </span>
                </div>
                <span className="mt-1.5 block h-1.5 w-full bg-canvas">
                  <span
                    className="block h-full bg-accent"
                    style={{ width: `${Math.round(score.paparan.cei)}%` }}
                  />
                </span>
                <button
                  type="button"
                  onClick={() => setPeringkat("paparan")}
                  className="mt-1 text-[10px] text-muted underline decoration-hair underline-offset-2 hover:text-ink hover:decoration-ink"
                >
                  Lihat peringkat paparan seluruh stasiun →
                </button>
                <p className="mt-1.5 text-[11px] leading-relaxed text-ink-soft">
                  {score.paparan.kelas}. Dihitung terpisah dari SEPI, dengan
                  keramaian dan jangkauan transportasi diberi bobot separuh, karena yang dibeli pengiklan adalah orang yang lewat.
                </p>
              </div>
            )}

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
              Yang ingin menggali tetap bisa, dan yang tidak, tidak dipaksa
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
        Judulnya dulu berbunyi "Komponen SEPI, w₁T + w₂E + w₃A + w₄U + w₅C".
        Rumus itu benar, tetapi ia menyapa pembaca dengan notasi sebelum sempat
        memberi tahu apa yang sedang dilihat. Rumusnya tetap ada, satu klik di
        bawah, buat yang memang mencarinya.
      */}
      <Section title="Yang membentuk skor ini" pending={!score}>
        <ul className="flex flex-col gap-2.5">
          {SEPI_COMPONENTS.map((c) => {
            const value = score?.components[c.key];
            const share = shares?.[c.key];
            // Nilainya SELALU ada - skor memang dihitung dari kelima variabel.
            // Yang membedakan: sebagian diukur langsung, sebagian diestimasi
            // dari stasiun berarketipe serupa. Bar bergaris putus-putus menandai
            // yang kedua, supaya estimasi tidak pernah terlihat sama dengan
            // pengukuran - tanpa menyembunyikan angkanya.
            const estimasi = score != null && score.terukur?.[c.key] === false;

            return (
              <li key={c.key} className="flex items-center gap-3">
                <span className="data-num w-3 shrink-0 text-xs font-semibold text-ink-soft">
                  {c.key}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-xs text-ink-soft">
                    {c.label}
                    {estimasi && (
                      <span className="ml-1 text-[10px] text-muted">
                        {seragam.includes(c.key)
                          ? "· sama di semua stasiun"
                          : "· estimasi"}
                      </span>
                    )}
                  </span>
                  <span
                    className={`mt-1 block h-1.5 w-full ${
                      estimasi ? "border border-dashed border-muted/60" : "bg-canvas"
                    }`}
                  >
                    <span
                      className={`block h-full ${estimasi ? "bg-muted/50" : "bg-accent"}`}
                      style={{ width: `${Math.round((share ?? 0) * 100)}%` }}
                    />
                  </span>
                </span>
                <span className="data-num w-20 shrink-0 text-right text-xs text-ink-soft">
                  {score ? formatKomponen(value) : "-"}
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
              Kelimanya dijumlahkan dengan bobot berbeda, variabel yang lebih
              menentukan diberi porsi lebih besar. Nilainya 0 sampai 1: makin
              tinggi, makin kuat sisi itu di stasiun ini.
            </p>
            {score?.catatan_estimasi && (
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                {score.catatan_estimasi}
              </p>
            )}
            {seragam.length > 0 && (
              <p className="mt-1 border-l-2 border-hair pl-2 text-[10px] leading-relaxed text-muted">
                Variabel <strong className="text-ink">{seragam.join(" dan ")}</strong>{" "}
                saat ini bernilai sama pada seluruh stasiun. Pengukuran
                langsungnya baru tersedia di satu stasiun, sehingga belum ada
                kelompok pembanding yang bervariasi untuk dijadikan acuan
                estimasi. Nilai yang seragam menggeser skor seluruh stasiun dalam
                besaran yang sama, sehingga urutan peringkat tidak terpengaruh.
                Yang belum tersedia adalah daya bedanya, bukan ketepatan
                peringkatnya.
              </p>
            )}
          </dl>
        </details>
      </Section>

      {score && (
        <Section title={`Di sekitar stasiun, jalan kaki ${score.minutes} menit`}>
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
          </dl>

          {/*
            Moda terhubung dipecah menurut JENIS, dengan sumbernya.
            Dua baris lama ("halte bus" dan "stasiun moda lain") hanya
            memperlihatkan jumlah titik, sehingga TransJakarta, bus reguler, dan
            terminal tercampur jadi satu angka, sementara taksi dan ojek daring
            tidak muncul sama sekali.
          */}
          {score.moda && (
            <div className="mt-3 border-t border-canvas pt-2.5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                Moda terhubung dalam {score.moda.radius_m} m
              </p>
              {score.moda.dihitung.length === 0 ? (
                <p className="mt-1 text-[11px] leading-relaxed text-muted">
                  Belum ada moda lain yang tercatat dalam radius ini.
                </p>
              ) : (
                <ul className="mt-1.5 flex flex-col gap-1.5">
                  {score.moda.dihitung.map((m) => (
                    <li key={m.jenis} className="flex items-baseline justify-between gap-2 text-xs">
                      <span className="min-w-0 text-ink-soft">
                        {m.jenis}
                        <span className="block text-[10px] text-muted">{m.sumber}</span>
                      </span>
                      {m.satuan && (
                        <span className="data-num shrink-0 text-ink">
                          {m.jumlah} {m.satuan}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              {score.moda.keterangan.length > 0 && (
                <div className="mt-2.5 border-l-2 border-hair pl-2">
                  <p className="text-[10px] font-semibold text-ink-soft">
                    Juga tercatat, tetapi tidak ikut skor
                  </p>
                  <ul className="mt-1 flex flex-col gap-0.5">
                    {score.moda.keterangan.map((m) => (
                      <li key={m.jenis} className="text-[11px] text-ink-soft">
                        {m.jenis}
                        <span className="text-muted">
                          {" "}
                          ({[
                            m.tercatat_peta > 0 ? `${m.tercatat_peta} di peta` : null,
                            m.disebut_survei > 0 ? `${m.disebut_survei} catatan survei` : null,
                          ]
                            .filter(Boolean)
                            .join(", ")})
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-[10px] leading-relaxed text-muted">
                    Pangkalan taksi dan ojek daring belum terpetakan merata untuk
                    seluruh stasiun, sehingga keduanya ditampilkan sebagai
                    keterangan. Menjadikannya skor akan merugikan stasiun yang
                    pangkalannya belum sempat dipetakan atau disurvei.
                  </p>
                </div>
              )}
            </div>
          )}
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Luasnya dihitung mengikuti jalan yang benar-benar bisa dilewati
            pejalan kaki, bukan lingkaran di peta, jadi kawasan yang terpotong
            rel atau jalan besar tidak ikut terhitung.
          </p>
        </Section>
      )}

      {/*
        Volume penumpang sengaja ditaruh di bagian TERPISAH, bukan digabung ke
        "Isi jangkauan jalan kaki". Angka di bagian itu semuanya ikut menghitung
        skor; angka ini tidak. Cakupannya baru 10 dari 46 stasiun, di bawah
        ambang 70%, jadi ia konteks yang jujur ditampilkan, bukan komponen.
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

      {peringkat && (
        <PeringkatModal
          stasiunSorot={props.name}
          daftarAwal={peringkat}
          onClose={() => setPeringkat(null)}
        />
      )}


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
              <span className="text-muted">, {s.untuk}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

/**
 * Tab Tenant - menjawab "usaha jenis apa yang layak dibuka di sini".
 *
 * Susunannya dibalik 12 Sep atas koreksi Villyan. Sebelumnya yang pertama
 * terlihat adalah DAFTAR tenant yang sudah ada, dan skor TSI baru muncul jauh
 * di bawahnya. Itu menjawab pertanyaan yang tidak sedang ditanyakan siapa pun:
 * PRD hal. 5 menempatkan fitur ini untuk pelaku UMKM yang "tidak memiliki
 * instrumen untuk mengetahui berapa besar permintaan laten, seberapa jenuh
 * kompetisi di sekitarnya", dan hal. 3 menyebutnya penyelamat "dari risiko
 * investasi buta".
 *
 * Maka rekomendasinya yang didahulukan. Daftar tenant yang sudah beroperasi
 * tetap ada - ia bukti bahwa angkanya berpijak pada lapangan - tetapi turun
 * jadi pelengkap, dikelompokkan per titik survei, dan tertutup secara bawaan.
 */
function TenantTab({
  station,
  laporan,
  onSorot,
}: {
  station: StationFeature;
  laporan: LaporanArea | null;
  onSorot: (titik: { lon: number; lat: number; nama: string } | null) => void;
}) {
  const stationId = typeof station.id === "number" ? station.id : null;
  const { report, loading, error } = useStationTenants(stationId, SCORE_MINUTES);
  const [katalogTenant, setKatalogTenant] = useState(false);
  const [peringkatTenant, setPeringkatTenant] = useState<string | null>(null);

  if (loading) return <p className="p-4 text-xs text-muted">Memuat…</p>;

  if (error || !report || report.categories.length === 0) {
    return (
      <EmptyTab
        name="Tenant"
        reason={
          error ??
          "Peringkat kategori usaha belum dihitung untuk stasiun ini."
        }
      />
    );
  }

  const terurut = [...report.categories].sort((x, y) => y.tsi - x.tsi);
  const teratas = terurut[0];
  const areaTenant = (laporan?.areas ?? []).filter((a) => a.tenant.length > 0);
  const jumlahTenant = areaTenant.reduce((n, a) => n + a.tenant.length, 0);

  return (
    <div className="flex flex-col">
      <Section title="Rekomendasi kategori usaha">
        <p className="text-xs leading-relaxed text-ink-soft">
          Untuk lapak kosong di stasiun ini, kategori dengan kelayakan tertinggi
          adalah <strong>{teratas.label}</strong> dengan indeks{" "}
          <span className="data-num font-semibold text-ink">
            {teratas.tsi.toFixed(0)}/100
          </span>
          .
        </p>
        <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
          Indeks Kelayakan Usaha membandingkan jumlah calon pelanggan yang
          dapat menjangkau stasiun ini dalam {report.minutes} menit berjalan kaki
          dengan jumlah pesaing sejenis yang telah beroperasi. Nilai yang lebih
          tinggi menunjukkan pasar yang lebih lapang.
        </p>
        {terurut[0] && (
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
            Basis pelanggan bernilai sama untuk seluruh kategori, yaitu{" "}
            <span className="data-num text-ink-soft">{terurut[0].demand}</span>{" "}
            titik aktivitas dalam jangkauan. Perbedaan antarkategori berasal dari
            jumlah pesaing sejenis yang telah beroperasi.
          </p>
        )}
      </Section>

      <Section title="Peringkat kelayakan per kategori">
        <ul className="flex flex-col gap-4">
          {terurut.map((c) => (
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

              {/*
                `demand` SENGAJA tidak diulang di tiap baris. Nilainya sama untuk
                semua kategori - ia jumlah titik aktivitas di sekitar stasiun,
                yaitu basis pelanggan yang dipakai bersama. Mengulangnya empat
                kali membuatnya terbaca seperti kekeliruan, padahal yang benar-
                benar membedakan kategori adalah jumlah pesaingnya.
              */}
              {/*
                Pesaing nol TIDAK boleh dibaca "tidak ada pesaing". Yang benar
                adalah "tidak ada dalam jangkauan yang dihitung" - kalimat yang
                salah di sini akan terbaca sebagai pasar kosong, padahal
                pesaingnya bisa saja berdiri sedikit lebih jauh.
              */}
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
                <span className="data-num text-ink-soft">{c.supply_luar}</span>{" "}
                pesaing terpetakan di sekitar stasiun
                {/*
                  Sisi dalam SELALU dibulatkan. Nilainya memang pecahan - ia
                  hasil shrinkage, bukan cacahan - tetapi "27,2 pesaing di dalam
                  stasiun" terbaca sebagai kesalahan hitung, bukan sebagai
                  taksiran. Kata "sekitar" yang menyampaikan ketidakpastiannya,
                  bukan angka di belakang koma. Pecahannya tetap dipakai utuh di
                  perhitungan; yang dibulatkan hanya tampilannya.
                */}
                {c.dalam_terukur ? (
                  <>, ditambah sekitar{" "}
                    <span className="data-num text-ink-soft">
                      {Math.round(c.supply_dalam)}
                    </span>{" "}
                    di dalam stasiun menurut survei lapangan
                  </>
                ) : (
                  <>
                    ; yang di dalam stasiun belum disurvei, ditaksir sekitar{" "}
                    <span className="data-num text-ink-soft">
                      {Math.round(c.supply_dalam)}
                    </span>{" "}
                    dari stasiun sejenis
                  </>
                )}
                . Sekitar{" "}
                <span className="data-num text-ink-soft">{c.headroom.toFixed(0)}</span>{" "}
                calon pelanggan per pesaing. Urutan{" "}
                <button
                  type="button"
                  onClick={() => setPeringkatTenant(c.label)}
                  className="font-semibold text-ink underline decoration-hair underline-offset-2 hover:decoration-ink"
                >
                  #{c.rank}
                </button>{" "}
                dari {report.station_count} stasiun untuk kategori ini
                {!c.dalam_terukur && (
                  <>, sesudah dipotong ketidakpastian taksiran (skor tanpa
                    potongan{" "}
                    <span className="data-num">{c.tsi.toFixed(0)}</span>, dipakai
                    mengurutkan{" "}
                    <span className="data-num">{c.tsi_bawah.toFixed(0)}</span>)
                  </>
                )}
                .
              </p>
            </li>
          ))}
        </ul>
        <p className="mt-3 border-t border-canvas pt-2 text-[10px] leading-relaxed text-muted">
          Peringkat disusun terpisah untuk setiap kategori, sehingga angkanya
          menyatakan posisi stasiun ini pada satu jenis usaha tertentu, bukan
          perbandingan antarkategori.
        </p>
        <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
          Urutan menggunakan skor yang telah dikurangi ketidakpastian data, bukan
          skor perhitungan langsung. Stasiun yang pesaing di dalam stasiunnya
          belum disurvei memperoleh pengurangan lebih besar, sehingga keunggulan
          peringkat tidak muncul semata-mata karena datanya belum lengkap.
          Pengurangan tersebut mengecil dengan sendirinya ketika data survei
          bertambah.
        </p>
        <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
          Lingkup penilaian adalah peluang usaha di{" "}
          <strong className="text-ink">kawasan</strong> stasiun, bukan lapak di
          dalam gedung stasiun. Calon pelanggan maupun pesaing sama-sama dihitung
          dari titik usaha yang terpetakan dalam jangkauan berjalan kaki, dan
          sebagian besar di antaranya berjarak lebih dari 300 meter dari peron.
        </p>
      </Section>

      {areaTenant.length > 0 && (
        <Section title="Usaha yang sudah beroperasi">
          <p className="text-xs leading-relaxed text-ink-soft">
            {jumlahTenant} usaha tercatat di {areaTenant.length} titik survei.
            Daftar ini menjadi komponen pesaing pada perhitungan di atas.
          </p>
          <button
            type="button"
            onClick={() => setKatalogTenant(true)}
            className="mt-2 w-full border border-hair px-3 py-2 text-xs text-ink-soft hover:border-ink hover:text-ink"
          >
            Buka katalog usaha · {jumlahTenant} usaha →
          </button>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Dihimpun dari catatan lapangan dengan kutipan terverifikasi. Satu
            titik bisa memiliki lebih banyak usaha daripada yang sempat tercatat.
          </p>
        </Section>
      )}

      {peringkatTenant && (
        <PeringkatModal
          stasiunSorot={station.properties.name}
          daftarAwal={`tenant:${peringkatTenant}`}
          onClose={() => setPeringkatTenant(null)}
        />
      )}

      {katalogTenant && (
        <TenantModal
          stasiun={station.properties.name}
          areas={laporan?.areas ?? []}
          kategori={report.categories}
          onSorot={onSorot}
          onClose={() => {
            setKatalogTenant(false);
            onSorot(null);
          }}
        />
      )}
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

      {/*
        Ditulis ulang sebagai satu pertanyaan dan satu jawaban. Versi lama
        menumpuk tiga gagasan asing dalam dua kalimat - "cara pembobotan",
        "bobot diacak", "stabil belum tentu benar" - dan pembaca yang bukan
        penyusun modelnya tidak punya pijakan untuk satu pun di antaranya.
      */}
      <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
        Skor stasiun bergantung pada besar bobot yang diberikan kepada setiap
        variabel, dan penetapan bobot itu sendiri merupakan pilihan metode. Untuk
        menguji apakah peringkat ini bertahan pada pilihan bobot yang lain,
        perhitungan diulang melalui dua cara: dengan{" "}
        <span className="data-num text-ink-soft">{sens.jumlah_skema}</span>{" "}
        susunan bobot yang disusun sengaja, dan dengan{" "}
        <span className="data-num text-ink-soft">
          {sens.jumlah_undian.toLocaleString("id-ID")}
        </span>{" "}
        pengacakan bobot dalam rentang yang wajar. Pada {sens.jumlah_skema}{" "}
        susunan bobot tersebut, peringkat stasiun ini berada antara{" "}
        <span className="data-num text-ink-soft">#{sens.peringkat_min}</span> dan{" "}
        <span className="data-num text-ink-soft">#{sens.peringkat_maks}</span>,
        yang berarti posisinya bergeser paling jauh{" "}
        <span className="data-num text-ink-soft">
          {sens.peringkat_maks - sens.peringkat_min}
        </span>{" "}
        tingkat mengikuti susunan bobot yang dipakai. Adapun dari seluruh
        pengacakan, stasiun ini menempati {sens.n_besar} besar sebanyak{" "}
        <span className="data-num text-ink-soft">
          {Math.round(sens.peluang_n_besar * 100)}%
        </span>
        {sens.peluang_n_besar === 0
          ? `, yang berarti tidak ada satu pun susunan bobot yang menempatkannya pada ${sens.n_besar} teratas.`
          : sens.peluang_n_besar === 1
            ? `, yang berarti seluruh susunan bobot menempatkannya pada ${sens.n_besar} teratas.`
            : `, yang berarti sebagian susunan bobot menempatkannya pada ${sens.n_besar} teratas dan sebagian lainnya tidak.`}{" "}
        {kokoh
          ? "Dengan demikian peringkat ini tidak bergantung pada satu pilihan bobot tertentu."
          : "Dengan demikian peringkat ini sebaiknya dibaca sebagai kisaran, bukan sebagai satu angka pasti."}
      </p>
    </div>
  );
}

const JENDELA: Array<{ key: keyof ProfilKeramaian; label: string; jam: string }> = [
  { key: "pagi", label: "Pagi", jam: "06-09" },
  { key: "siang", label: "Siang", jam: "09-16" },
  { key: "sore", label: "Sore", jam: "16-19" },
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
              <span className="data-num text-ink-soft">{p ? p.setara_1_5.toFixed(0) : "-"}</span>
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

function NamingTab({ stationId }: { stationId: number | null }) {
  const { naming, loading, error } = useStationNaming(stationId);

  if (loading) return <p className="p-4 text-xs text-muted">Memuat…</p>;
  if (error || !naming) {
    return <EmptyTab name="Naming" reason={error ?? "Data belum bisa dimuat."} />;
  }

  const { status, potensi, kandidat_sponsor, cara_hitung } = naming;

  return (
    <div className="flex flex-col">
      {/*
        Potensi ditampilkan lebih dulu daripada status. Hampir semua stasiun KRL
        berstatus sama - belum terjual - sehingga status tidak membedakan satu
        stasiun dari yang lain, sedangkan potensi membedakannya.
      */}
      {potensi?.cei != null ? (
        <Section title="Potensi hak penamaan">
          <div className="flex items-end justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold leading-relaxed text-ink">
                {potensi.kelas_paparan}
              </p>
              {potensi.peringkat_paparan != null && (
                <p className="mt-1 text-xs leading-relaxed text-ink-soft">
                  Peringkat paparan{" "}
                  <span className="data-num font-semibold text-ink">
                    #{potensi.peringkat_paparan}
                  </span>{" "}
                  dari {potensi.dari_stasiun_krl} stasiun KRL.
                </p>
              )}
            </div>
            <p className="data-num shrink-0 text-3xl font-semibold leading-none text-ink">
              {potensi.cei.toFixed(1)}
              <span className="text-sm font-medium text-muted">/100</span>
            </p>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted">{potensi.catatan}</p>

          <details className="mt-2.5 border-t border-canvas pt-2">
            <summary className="cursor-pointer text-[11px] font-semibold text-ink-soft hover:text-ink">
              Bagaimana angka ini dihitung?
            </summary>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              {cara_hitung.indeks}
            </p>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              {cara_hitung.kenapa_bobot}
            </p>
          </details>
        </Section>
      ) : (
        <Section title="Status hak penamaan">
          <p className="text-xs leading-relaxed text-ink-soft">
            {status
              ? status.bersponsor
                ? `Sudah terjual ke ${status.sponsor}.`
                : `Belum terjual. Masih memakai nama dasarnya, ${status.nama_dasar}.`
              : "Belum ada nilai paparan untuk stasiun ini."}
          </p>
        </Section>
      )}

      {kandidat_sponsor.length > 0 && (
        <Section title="Calon sponsor di sekitar stasiun">
          <p className="text-xs leading-relaxed text-ink-soft">
            Merek yang kantor atau gerainya berada dalam jangkauan jalan kaki
            dari stasiun ini. Titiknya disorot di peta.
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {kandidat_sponsor.map((k) => (
              <li
                key={`${k.nama}-${k.jarak_m}`}
                className="flex items-baseline justify-between gap-2 text-[11px]"
              >
                <span className="min-w-0 text-ink-soft">{k.nama}</span>
                <span className="flex shrink-0 items-baseline gap-1.5">
                  {!k.dalam_inti && (
                    <span className="label-caps text-[8px] text-muted">
                      di luar inti
                    </span>
                  )}
                  <span
                    className={`data-num ${k.dalam_inti ? "text-muted" : "text-muted/70"}`}
                  >
                    {k.jarak_m} m
                  </span>
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            {naming.catatan_kandidat}
          </p>

          <details className="mt-2 border-t border-canvas pt-2">
            <summary className="cursor-pointer text-[11px] font-semibold text-ink-soft hover:text-ink">
              Bagaimana nama-nama ini dipilih?
            </summary>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              {cara_hitung.kandidat}
            </p>
          </details>
          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Diurutkan dari yang terdekat, bersumber dari data titik minat
            OpenStreetMap dan survei MAPID. Mereka belum tentu tertarik menjadi
            sponsor, daftar ini titik awal untuk dihubungi, bukan daftar peminat.
          </p>
        </Section>
      )}

      <NilaiKontrak cei={potensi?.cei ?? null} alasan={naming.alasan_nilai_kosong} />
    </div>
  );
}

/**
 * Nilai kontrak: kalkulator proporsi, bukan angka yang kami karang.
 *
 * PRD mewajibkan valuasi diacu pada transaksi pembanding NYATA lalu diskalakan
 * dengan indeks paparan. Bagian pertamanya belum kami punya - tidak ada data
 * transaksi hak penamaan di Indonesia yang bisa dikutip - dan menebaknya berarti
 * mengarang angka yang akan dipakai orang untuk bernegosiasi.
 *
 * Tetapi bagian KEDUANYA sudah lengkap: indeks paparan tiap stasiun sudah
 * dihitung, jadi perbandingan antar stasiun bisa dilakukan sekarang juga. Maka
 * angkanya diminta dari pengguna. Ia yang memegang pembanding - pengelola aset
 * tahu tarif yang pernah ditawarkan, konsultan tahu nilai transaksi sejenis -
 * dan sistem mengerjakan bagian yang memang bisa dikerjakannya: menskalakan.
 *
 * Bedanya penting. Angka yang keluar tetap milik pengguna, dan halaman ini
 * tidak pernah berpura-pura tahu harga pasar yang belum pernah diukur siapa pun.
 */
function NilaiKontrak({ cei, alasan }: { cei: number | null; alasan: string }) {
  const [acuan, setAcuan] = useState("");

  const angka = Number(acuan.replace(/[^\d]/g, ""));
  const hasil = cei != null && angka > 0 ? (angka * cei) / 100 : null;

  return (
    <Section title="Nilai kontrak">
      <p className="text-xs leading-relaxed text-ink-soft">{alasan}</p>

      {cei == null ? (
        <p className="mt-2 text-[11px] leading-relaxed text-muted">
          Stasiun ini belum punya nilai paparan, sehingga perbandingannya pun
          belum bisa dihitung.
        </p>
      ) : (
        <>
          <p className="mt-2.5 text-[11px] leading-relaxed text-muted">
            Yang bisa dihitung sekarang adalah perbandingannya. Kalau Anda punya
            angka pembanding, tarif yang pernah ditawarkan, atau nilai kontrak
            stasiun sejenis, masukkan di bawah untuk stasiun berpaparan penuh
            (100), dan nilainya diskalakan ke paparan stasiun ini.
          </p>

          <label className="mt-2 block">
            <span className="label-caps mb-1 block text-[9px] text-muted">
              Nilai acuan untuk paparan 100, per tahun
            </span>
            {/*
              Angka diformat sambil diketik, dan "Rp" berdiri sebagai awalan
              tetap di luar kotak isian.

              Alasannya praktis: nilai kontrak hak penamaan berada di kisaran
              miliaran, dan deretan sembilan angka tanpa pemisah hampir mustahil
              dibaca ulang untuk memastikan tidak ada digit yang kelebihan.
              Yang disimpan di state tetap angka murni; pemisah titik hanya
              lapisan tampilan, dan dibuang lagi sebelum dihitung.
            */}
            <div className="flex items-stretch border border-hair bg-panel focus-within:border-ink">
              <span className="flex select-none items-center px-2 text-xs text-muted">
                Rp
              </span>
              <input
                type="text"
                inputMode="numeric"
                value={angka > 0 ? angka.toLocaleString("id-ID") : acuan}
                onChange={(e) => setAcuan(e.target.value.replace(/[^\d]/g, ""))}
                placeholder="5.000.000.000"
                aria-label="Nilai acuan rupiah per tahun untuk stasiun berpaparan 100"
                className="data-num w-full bg-transparent py-1.5 pr-2 text-xs text-ink outline-none"
              />
            </div>
          </label>

          {hasil != null && (
            <div className="mt-2 border border-ink bg-canvas p-2.5">
              <p className="data-num text-lg font-semibold leading-tight text-ink">
                Rp {Math.round(hasil).toLocaleString("id-ID")}
                <span className="text-[11px] font-medium text-muted"> / tahun</span>
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                Perhitungan: Rp {angka.toLocaleString("id-ID")} x{" "}
                {cei.toFixed(1)} / 100. Nilai acuan berasal dari Anda, bukan dari
                sistem; yang dihitung di sini hanya proporsi paparannya.
              </p>
            </div>
          )}
        </>
      )}
    </Section>
  );
}

/**
 * Petik bukti terpendek dari kalimat dasar sebuah kelompok pengunjung.
 *
 * Kalimat dasarnya panjang dan lengkap - itu tetap dipertahankan untuk pembaca
 * yang ingin menelusuri. Tetapi calon pengiklan yang membandingkan beberapa
 * stasiun butuh satu angka yang bisa dipindai sekilas, dan angka itu sudah ada
 * di dalam kalimatnya: "76%", "12 sekolah", "2 pasar".
 */
function ringkasBukti(dasar: string): string {
  const persen = dasar.match(/(\d+)%/);
  if (persen) return `${persen[1]}% kawasan`;

  const cacah = dasar.match(/terdapat (\d+) ([a-z ]+?) dalam/i);
  if (cacah) {
    const benda = cacah[2].trim().split(" ").slice(0, 2).join(" ");
    return `${cacah[1]} ${benda}`;
  }

  return "";
}

function labelKelas(kelas: string | null | undefined): string {
  const peta: Record<string, string> = {
    hunian: "permukiman",
    kantor: "perkantoran",
    niaga: "pertokoan",
    wisata: "tempat wisata",
    industri: "kawasan industri",
  };
  return kelas ? peta[kelas] ?? kelas : "-";
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
                  ini berdasarkan luas lantai bangunan, sehingga gedung
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
          {/*
            Tiap kelompok membawa BUKTINYA, dalam satuannya sendiri.
            Sengaja BUKAN persentase pengunjung. Kelompok di sini datang dari dua
            sistem ukur yang berbeda - sebagian dari porsi luas kawasan, sebagian
            dari cacahan titik minat - dan keduanya tidak punya penyebut bersama.
            Memaksanya jadi satu set persentase berarti mengarang angka, dan lebih
            buruk lagi: porsi luas BUKAN porsi orang. Kawasan yang 76% ruangnya
            perkantoran tidak berarti 76% orang yang melintas adalah pekerja
            kantor - siapa yang melintas tidak pernah kami hitung.
          */}
          <ul className="mt-1.5 flex flex-col gap-1.5">
            {audiens.map((a) => (
              <li
                key={a.kelompok}
                className="flex items-baseline justify-between gap-2 border border-hair px-2 py-1"
              >
                <span className="min-w-0 text-[11px] text-ink">{a.kelompok}</span>
                <span className="data-num shrink-0 text-[10px] text-muted">
                  {ringkasBukti(a.dasar)}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
            Angka di sebelah kanan menunjukkan dasar penarikan tiap kelompok, dan
            satuannya berbeda-beda: sebagian berupa porsi luas kawasan, sebagian
            berupa jumlah tempat. Karena satuannya tidak sama, angka-angka
            tersebut tidak dapat dijumlahkan menjadi 100 persen.
          </p>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">
            Komposisi pengunjung belum disajikan dalam bentuk persentase karena
            jumlah orang yang melintas belum diukur secara langsung. Persentase
            yang diturunkan dari luas kawasan akan menyiratkan ketelitian yang
            belum dimiliki datanya.
          </p>
        </div>
      )}

      <div className="mt-3 border-t border-canvas pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Format iklan yang disarankan
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
          Waktu singgah di stasiun ini <strong>{waktu_singgah.label}</strong>, {" "}
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
          Bagaimana profil ini disusun
        </summary>
        <div className="mt-1.5 flex flex-col gap-1.5 text-[10px] leading-relaxed text-muted">
          <p>
            Disusun dari {dasar.jumlah_narasi} pengamatan lapangan dan{" "}
            {dasar.jumlah_penilaian_keramaian} penilaian keramaian dari pedagang
            serta petugas di kawasan ini.
          </p>
          <p>
            Kelompok pengunjung disimpulkan dari peruntukan lahan di sekitar
            stasiun yang disilangkan dengan pola keramaian antar-waktu, dua hal
            yang sama-sama terukur. Kami tidak menghitung jumlah orang, tidak
            merekam identitas siapa pun, dan tidak menilai pengunjung dari
            penampilannya.
          </p>
          <p>
            Perlu diingat, peruntukan lahan menggambarkan fungsi bangunan di
            kawasan itu, bukan pekerjaan orang yang tinggal di sana. Kawasan
            permukiman tetap dihuni pekerja kantor, bedanya, permukiman adalah
            titik asal perjalanan, sedangkan kawasan perkantoran titik tujuannya.
          </p>
        </div>
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
  onSorot,
}: {
  stationId: number | null;
  stationName: string;
  laporan: LaporanArea | null;
  loading: boolean;
  error: string | null;
  onSorot: (titik: { lon: number; lat: number; nama: string } | null) => void;
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
                      ? `${a.iklan.total} media iklan · ${a.iklan.per_jenis.length} jenis`
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
          stationId={stationId}
          areas={laporan.areas}
          sponsorship={sponsorship}
          segmenAwal={katalog}
          onSorot={onSorot}
          onClose={() => {
            setKatalog(null);
            onSorot(null);
          }}
        />
      )}
    </div>
  );
}

// SponsorshipSection, Penyaringan, dan judulPendek DIHAPUS dari sini.
// Katalog sponsorship kini hidup di KatalogModal, satu halaman bersama katalog
// ruang iklan, dua daftar yang tujuannya berbeda, dipisahkan segmen, alih-alih
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
 * Karena itu ia selalu tampil, bukan hanya ketika datanya kurang, angka
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
          Seberapa kuat datanya
        </span>
        <span className="data-num text-[11px] text-ink-soft">
          {terpakai}/{total} terukur · {confidence.toFixed(2)}
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

      {/*
        Kalimat lama: "Skor disusun dari 3 variabel, jadi tidak sebanding
        dengan stasiun yang datanya lengkap." Itu KELIRU - skornya disusun dari
        kelima variabel, dengan yang belum terukur diisi estimasi shrinkage.
        Yang berbeda hanya porsi pengukuran langsungnya.
      */}
      <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
        {teks}.{" "}
        {terpakai < total
          ? `Skor tetap dihitung dari kelima variabel; ${total - terpakai} di antaranya ` +
            "estimasi dari stasiun berkarakter serupa, bukan hasil pengukuran langsung " +
            "di lapangan."
          : "Kelima variabel terukur langsung di lapangan."}
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
        {value || ", "}
      </dd>
    </div>
  );
}
