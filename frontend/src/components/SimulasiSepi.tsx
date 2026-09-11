"use client";

import { useEffect, useState } from "react";

import {
  useSepiSimulation,
  type BobotSepi,
} from "@/hooks/useSepiSimulation";

const VARIABEL: Array<{ key: keyof BobotSepi; label: string }> = [
  { key: "T", label: "Transportasi" },
  { key: "E", label: "Ekonomi" },
  { key: "A", label: "Aksesibilitas" },
  { key: "U", label: "Urban" },
  { key: "C", label: "Komersial" },
];

const RATA: BobotSepi = { T: 0.2, E: 0.2, A: 0.2, U: 0.2, C: 0.2 };

const CINCIN = [5, 10, 15];

type Props = {
  stationId: number | null;
  stationName: string;
  /** Skor resmi, untuk dibandingkan dengan hasil simulasi. */
  sepiResmi: number;
  rankResmi: number;
  /**
   * Bobot kiriman tombol asisten. `nonce` baru membuka panel, mengisi slider,
   * dan langsung menghitung - pengguna melihat hitungan yang sama dengan yang
   * dibaca asisten, lalu bebas menggeser dari situ.
   */
  preset?: { bobot: Record<string, number>; nonce: number } | null;
};

/**
 * Kontrol "bagaimana kalau" untuk skor SEPI.
 *
 * Bobot resmi berasal dari Entropy + AHP, dan itu tetap angka yang dilaporkan.
 * Panel ini menjawab pertanyaan yang berbeda: seandainya prioritas bisnisnya
 * lain — misalnya yang dicari murni arus penumpang — stasiun mana yang naik.
 *
 * Hasilnya sengaja tidak disimpan dan selalu diberi label "simulasi". Kalau ia
 * bisa menimpa skor resmi, angka yang dilaporkan akan bergantung pada siapa
 * yang terakhir menggeser slider.
 */
export default function SimulasiSepi({
  stationId,
  stationName,
  sepiResmi,
  rankResmi,
  preset = null,
}: Props) {
  const [buka, setBuka] = useState(false);
  const [bobot, setBobot] = useState<BobotSepi>(RATA);
  const [menit, setMenit] = useState(10);
  const { hasil, memuat, error, jalankan, bersihkan } = useSepiSimulation();

  const presetNonce = preset?.nonce ?? null;
  useEffect(() => {
    if (!preset) return;
    const dariAsisten = Object.fromEntries(
      VARIABEL.map((v) => [v.key, Number(preset.bobot[v.key] ?? 0)])
    ) as unknown as BobotSepi;
    setBuka(true);
    setBobot(dariAsisten);
    setMenit(10);
    void jalankan(dariAsisten, 10, stationId);
    // Hanya nonce yang memicu: objek preset yang sama tidak boleh menghitung ulang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetNonce]);

  const total = Object.values(bobot).reduce((a, b) => a + b, 0);
  // Dinormalisasi saat dikirim, jadi pengguna tidak perlu membuat jumlahnya
  // tepat 1 — yang penting perbandingan antar variabelnya.
  const terkirim = Object.fromEntries(
    VARIABEL.map((v) => [v.key, total > 0 ? bobot[v.key] / total : 0.2])
  ) as unknown as BobotSepi;

  const dipilih = hasil?.stasiun_dipilih ?? null;
  const selisih = dipilih ? dipilih.sepi - sepiResmi : 0;
  const geser = dipilih ? rankResmi - dipilih.peringkat : 0;

  if (!buka) {
    return (
      <button
        type="button"
        onClick={() => setBuka(true)}
        className="mt-3 w-full border border-hair px-3 py-2 text-left text-xs text-ink-soft hover:border-ink hover:text-ink"
      >
        Coba prioritas lain →
        <span className="mt-0.5 block text-[10px] text-muted">
          Ubah bobot variabel, lihat peringkat {stationName} bergeser ke mana
        </span>
      </button>
    );
  }

  return (
    <div className="mt-3 border border-hair p-3">
      <div className="flex items-baseline justify-between">
        <p className="label-caps text-ink-soft">Simulasi prioritas</p>
        <button
          type="button"
          onClick={() => {
            setBuka(false);
            bersihkan();
          }}
          className="text-[11px] text-muted hover:text-ink"
        >
          tutup
        </button>
      </div>

      <p className="mt-1 text-[10px] leading-relaxed text-muted">
        Seandainya prioritasnya berbeda dari bobot resmi — stasiun mana yang
        naik? Hasilnya tidak menggantikan skor resmi.
      </p>

      <div className="mt-3 flex flex-col gap-2">
        {VARIABEL.map((v) => (
          <label key={v.key} className="flex items-center gap-2">
            <span className="data-num w-3 shrink-0 text-[11px] font-semibold text-ink-soft">
              {v.key}
            </span>
            <input
              type="range"
              min={0}
              max={100}
              value={Math.round(bobot[v.key] * 100)}
              onChange={(e) =>
                setBobot({ ...bobot, [v.key]: Number(e.target.value) / 100 })
              }
              className="h-1 min-w-0 flex-1 accent-accent"
              aria-label={`Bobot ${v.label}`}
            />
            <span className="data-num w-9 shrink-0 text-right text-[11px] text-muted">
              {total > 0 ? Math.round((bobot[v.key] / total) * 100) : 0}%
            </span>
          </label>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span className="text-[11px] text-muted">Jangkauan</span>
        {CINCIN.map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMenit(m)}
            className={`border px-2 py-1 text-[11px] ${
              m === menit
                ? "border-ink bg-ink text-white"
                : "border-hair text-muted hover:border-ink hover:text-ink"
            }`}
          >
            {m} mnt
          </button>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() => jalankan(terkirim, menit, stationId)}
          disabled={memuat || total === 0}
          className="flex-1 border border-ink bg-ink px-3 py-2 text-xs text-white disabled:opacity-40"
        >
          {memuat ? "Menghitung…" : "Hitung ulang"}
        </button>
        <button
          type="button"
          onClick={() => {
            setBobot(RATA);
            setMenit(10);
            bersihkan();
          }}
          className="border border-hair px-3 py-2 text-xs text-muted hover:border-ink hover:text-ink"
        >
          Rata
        </button>
      </div>

      {error && <p className="mt-2 text-[11px] text-accent">{error}</p>}

      {dipilih && (
        <div className="mt-3 border-t border-hair pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-ink-soft">{stationName}</span>
            <span className="data-num text-lg font-semibold">
              {dipilih.sepi.toFixed(1)}
              <span className="ml-1 text-[11px] font-normal text-muted">
                ({selisih >= 0 ? "+" : ""}
                {selisih.toFixed(1)})
              </span>
            </span>
          </div>
          <p className="mt-1 text-[11px] text-muted">
            Peringkat #{dipilih.peringkat}{" "}
            {geser === 0
              ? "— tidak bergeser"
              : geser > 0
                ? `— naik ${geser} tingkat`
                : `— turun ${Math.abs(geser)} tingkat`}{" "}
            · {dipilih.kelas}
          </p>

          <p className="mt-2 text-[10px] leading-relaxed text-muted">
            Tiga teratas:{" "}
            {hasil?.peringkat
              .slice(0, 3)
              .map((r) => `${r.stasiun} ${r.sepi.toFixed(1)}`)
              .join(" · ")}
          </p>
        </div>
      )}

      {hasil && !dipilih && (
        <p className="mt-3 border-t border-hair pt-3 text-[11px] text-muted">
          {stationName} tidak ikut terskor pada cincin {menit} menit. Stasiun
          tanpa poligon jangkauan, atau yang dilintasi tanpa berhenti, memang
          tidak dinilai.
        </p>
      )}
    </div>
  );
}
