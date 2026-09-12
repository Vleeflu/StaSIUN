"use client";

import { useEffect, useState } from "react";

import type { AreaStasiun, LaporanSponsorship } from "@/types/station";

type Segmen = "iklan" | "fasilitas";

/**
 * Katalog lengkap dalam satu halaman timbul, dua segmen.
 *
 * Sebelumnya seluruh katalog ditumpuk di panel samping selebar 400 px:
 * daftar area iklan, daftar peluang sponsorship, foto, kutipan. Panjang ke
 * bawah tanpa ujung, dan yang paling penting - dua katalog yang tujuannya
 * berbeda - terbaca seperti satu daftar panjang yang sama.
 *
 * Di sini panel samping cukup memberi cuplikan; yang mau melihat semuanya
 * membuka halaman ini, dan memilih sendiri katalog mana yang sedang ia cari.
 */
export default function KatalogModal({
  stasiun,
  areas,
  sponsorship,
  segmenAwal = "iklan",
  onClose,
}: {
  stasiun: string;
  areas: AreaStasiun[];
  sponsorship: LaporanSponsorship | null;
  segmenAwal?: Segmen;
  onClose: () => void;
}) {
  const [segmen, setSegmen] = useState<Segmen>(segmenAwal);
  const [diStasiunSaja, setDiStasiunSaja] = useState(false);

  // Esc menutup. Halaman timbul yang hanya bisa ditutup lewat satu tombol kecil
  // di pojok memaksa pengguna mencari jalan keluar; Esc itu yang pertama dicoba
  // orang, dan biayanya lima baris.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Titik yang PUNYA catatan media iklan - termasuk yang jumlahnya tidak
  // dicatat surveyor. Menyaringnya dengan `total > 0` akan menghilangkan
  // lokasi nyata seperti deretan videotron koridor Sudirman-BNI City, yang
  // jelas ada tetapi tidak pernah dihitung satuannya.
  const areaIklan = areas.filter((a) => a.iklan.per_jenis.length > 0);
  const tampil = diStasiunSaja ? areaIklan.filter((a) => a.di_stasiun) : areaIklan;
  const peluang = sponsorship?.peluang ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Katalog ${stasiun}`}
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-3xl flex-col border border-ink bg-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hair p-4">
          <div className="min-w-0">
            <p className="label-caps text-accent">Katalog</p>
            <h2 className="mt-1 text-xl font-bold leading-tight tracking-[-0.01em]">
              {stasiun}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup katalog"
            className="shrink-0 border border-hair px-2 py-1 text-sm leading-none text-ink-soft hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </header>

        <nav className="flex shrink-0 border-b border-hair" aria-label="Jenis katalog">
          {(
            [
              { id: "iklan" as const, label: `Ruang iklan · ${areaIklan.length}` },
              { id: "fasilitas" as const, label: `Perbaikan fasilitas · ${peluang.length}` },
            ]
          ).map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setSegmen(s.id)}
              aria-current={segmen === s.id ? "page" : undefined}
              className={`label-caps flex-1 border-b-2 px-3 py-2.5 ${
                segmen === s.id
                  ? "border-accent text-accent"
                  : "border-transparent text-muted hover:text-ink-soft"
              }`}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {segmen === "iklan" ? (
            <>
              <div className="mb-3 flex items-baseline justify-between gap-3">
                <p className="text-xs leading-relaxed text-ink-soft">
                  Daftar titik media iklan di {stasiun} beserta karakteristik
                  paparannya, disusun dari pengamatan lapangan.
                </p>
                <label className="flex shrink-0 cursor-pointer items-center gap-1.5 text-[11px] text-muted">
                  <input
                    type="checkbox"
                    checked={diStasiunSaja}
                    onChange={(e) => setDiStasiunSaja(e.target.checked)}
                    className="accent-accent"
                  />
                  Hanya di dalam stasiun
                </label>
              </div>

              {tampil.length === 0 ? (
                <p className="text-xs text-muted">
                  {diStasiunSaja
                    ? "Tidak ada media iklan yang tercatat di dalam stasiun."
                    : "Belum ada media iklan yang tercatat di stasiun ini."}
                </p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {tampil.map((a) => (
                    <KartuIklan key={a.id} area={a} />
                  ))}
                </ul>
              )}
            </>
          ) : (
            <>
              <p className="mb-3 text-xs leading-relaxed text-ink-soft">
                Fasilitas yang teridentifikasi perlu pembenahan dan dapat
                ditawarkan sebagai kemitraan: sponsor menanggung biaya
                perbaikan, mereknya melekat pada fasilitas yang diperbaiki.
              </p>
              {peluang.length === 0 ? (
                <p className="text-xs text-muted">
                  Belum ada fasilitas yang dapat ditawarkan sebagai kemitraan di
                  stasiun ini.
                </p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {peluang.map((p) => (
                    <KartuFasilitas key={p.id} peluang={p} />
                  ))}
                </ul>
              )}
              {sponsorship && <Penyaringan laporan={sponsorship} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function KartuIklan({ area }: { area: AreaStasiun }) {
  const jenis = area.iklan.per_jenis.map((j) => j.jenis);
  return (
    <li className="border border-hair p-3">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="min-w-0 text-sm font-semibold leading-snug text-ink">{area.nama}</h3>
        <span className="label-caps shrink-0 text-[9px] text-muted">
          {area.di_stasiun ? "di dalam stasiun" : `${area.jarak_m} m dari stasiun`}
        </span>
      </div>

      {/*
        Status terisi/kosong TIDAK ditampilkan sama sekali.
        Villyan menegaskan ini dua kali: yang relevan bagi calon pemasang adalah
        media apa yang ADA di titik ini, sedangkan keterisian diurus pengelola
        dan sudah usang begitu halaman ini dibuka.
      */}
      <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
        {area.iklan.total > 0 ? (
          <>
            <strong className="text-accent">{area.iklan.total} media iklan</strong> di
            titik ini
            {jenis.length > 0 && `: ${jenis.join(", ")}`}.
          </>
        ) : (
          <>
            Media iklan tercatat di titik ini
            {jenis.length > 0 && `: ${jenis.join(", ")}`} — jumlah satuannya tidak
            dicatat surveyor.
          </>
        )}
      </p>

      {area.waktu_singgah?.label && area.waktu_singgah.label !== "tidak terbaca" && (
        <p className="mt-1 text-xs leading-relaxed text-ink-soft">
          Waktu singgah di titik ini <strong>{area.waktu_singgah.label}</strong> —{" "}
          {area.waktu_singgah.alasan}.
        </p>
      )}

      {area.iklan.kutipan[0] && (
        <p className="mt-2 border-l-2 border-hair pl-2 text-[11px] italic leading-relaxed text-muted">
          “{area.iklan.kutipan[0]}”
        </p>
      )}

      {area.foto.length > 0 && (
        <div className="mt-2 flex gap-1.5 overflow-x-auto">
          {area.foto.map((url) => (
            <a key={url} href={url} target="_blank" rel="noreferrer" className="shrink-0">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={`Foto ${area.nama}`}
                loading="lazy"
                className="h-16 w-24 border border-hair object-cover"
              />
            </a>
          ))}
        </div>
      )}
    </li>
  );
}

function KartuFasilitas({ peluang }: { peluang: LaporanSponsorship["peluang"][number] }) {
  const u = peluang.usulan;
  return (
    <li className="border border-hair p-3">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="min-w-0 text-sm font-semibold leading-snug text-ink">
          {peluang.lokasi.nama_titik || peluang.jenis}
        </h3>
        <span className="label-caps shrink-0 text-[9px] text-muted">{peluang.stasiun}</span>
      </div>

      <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
        <strong>{u.bentuk}</strong> — kondisi {peluang.jenis} di titik ini perlu
        pembenahan
        {peluang.jumlah_laporan > 1 && `, dilaporkan ${peluang.jumlah_laporan} kali`}.
      </p>

      <p className="mt-1 text-[11px] leading-relaxed text-muted">
        {u.kewenangan === "aset stasiun"
          ? "Berada di aset stasiun, sehingga kemitraan cukup melalui pengelola stasiun."
          : "Berada di luar lahan stasiun, sehingga memerlukan izin pengelola jalan dan tidak dapat ditawarkan sebagai aset stasiun."}
      </p>

      {peluang.keluhan && (
        <p className="mt-2 border-l-2 border-hair pl-2 text-[11px] italic leading-relaxed text-muted">
          “{peluang.keluhan}”
        </p>
      )}
    </li>
  );
}

/**
 * Apa saja yang DISARING sebelum daftar ini terbentuk.
 *
 * Daftar yang rapi selalu terlihat lebih meyakinkan daripada yang berantakan,
 * dan itu justru bahayanya: pembaca tidak punya cara tahu berapa banyak yang
 * dibuang, dan atas dasar apa. Kalimat ini membuat penyaringnya ikut terlihat.
 */
function Penyaringan({ laporan }: { laporan: LaporanSponsorship }) {
  const bagian = [
    laporan.laporan_digabung > 0 && `${laporan.laporan_digabung} laporan kembar digabung`,
    laporan.dibantah_validasi_spasial > 0 &&
      `${laporan.dibantah_validasi_spasial} tidak cocok dengan data lapangan`,
    laporan.tanpa_bentuk_sponsorship > 0 &&
      `${laporan.tanpa_bentuk_sponsorship} tidak punya bentuk kemitraan yang masuk akal`,
    laporan.terlalu_jauh_dari_stasiun > 0 &&
      `${laporan.terlalu_jauh_dari_stasiun} terlalu jauh dari stasiun`,
    laporan.bukan_keluhan_fasilitas > 0 &&
      `${laporan.bukan_keluhan_fasilitas} ternyata soal dagangan, bukan fasilitas`,
  ].filter(Boolean);

  if (bagian.length === 0) return null;

  return (
    <p className="mt-3 border-t border-canvas pt-2 text-[10px] leading-relaxed text-muted">
      Sebelum masuk daftar ini, catatan lapangan disaring dulu: {bagian.join(", ")}.
    </p>
  );
}
