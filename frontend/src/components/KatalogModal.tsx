"use client";

import { useEffect, useState } from "react";

import { useStationScore } from "@/hooks/useStationScore";
import { urlFoto } from "@/lib/api";
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
  stationId,
  areas,
  sponsorship,
  segmenAwal = "iklan",
  onClose,
}: {
  stasiun: string;
  stationId: number | null;
  areas: AreaStasiun[];
  sponsorship: LaporanSponsorship | null;
  segmenAwal?: Segmen;
  onClose: () => void;
}) {
  const [segmen, setSegmen] = useState<Segmen>(segmenAwal);
  // Titik yang sedang dibuka rinciannya. Null berarti sedang melihat daftar.
  const [terpilih, setTerpilih] = useState<AreaStasiun | null>(null);
  const { score } = useStationScore(stationId, 10);
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

        {terpilih ? (
          <DetailTitik
            area={terpilih}
            cei={score?.paparan?.cei ?? null}
            kelasPaparan={score?.paparan?.kelas ?? null}
            onKembali={() => setTerpilih(null)}
          />
        ) : (
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
                    <KartuIklan key={a.id} area={a} onBuka={() => setTerpilih(a)} />
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
        )}
      </div>
    </div>
  );
}

/**
 * Rincian satu titik iklan, memenuhi seluruh halaman timbul.
 *
 * Daftar katalog menjawab "ada apa saja di sini"; halaman ini menjawab "titik
 * ini layak dipakai untuk apa". Urutannya mengikuti pertanyaan yang muncul di
 * kepala calon pemasang: di mana, ada apa, seberapa luas jangkauannya, cocok
 * untuk iklan seperti apa, seramai apa, dan akhirnya - seperti apa rupanya.
 */
function DetailTitik({
  area,
  cei,
  kelasPaparan,
  onKembali,
}: {
  area: AreaStasiun;
  cei: number | null;
  kelasPaparan: string | null;
  onKembali: () => void;
}) {
  const rincian = area.iklan.per_jenis
    .map((j) => ({ jenis: j.jenis, jumlah: j.terpakai + j.kosong }))
    .sort((a, b) => b.jumlah - a.jumlah);
  const waktu = Object.entries(area.keramaian).filter(([, v]) => v);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4">
      <button
        type="button"
        onClick={onKembali}
        className="mb-3 border border-hair px-2 py-1 text-[11px] text-muted hover:border-ink hover:text-ink"
      >
        ← Kembali ke katalog
      </button>

      <h3 className="text-lg font-bold leading-snug tracking-[-0.01em]">{area.nama}</h3>
      <p className="mt-1 text-[11px] text-muted">
        {area.di_stasiun ? "Di dalam area stasiun" : `${area.jarak_m} m dari stasiun`} ·{" "}
        {area.jumlah_titik} catatan lapangan
      </p>

      <div className="mt-4 border-t border-canvas pt-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Media iklan di titik ini
        </p>
        {rincian.length === 0 ? (
          <p className="mt-1 text-xs text-muted">Belum ada media tercatat.</p>
        ) : (
          <>
            <p className="mt-1 text-xs leading-relaxed text-ink-soft">
              {area.iklan.total > 0
                ? `${area.iklan.total} unit, terdiri dari:`
                : "Tercatat ada, jumlah satuannya tidak dicatat surveyor:"}
            </p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {rincian.map((j) => (
                <li key={j.jenis} className="flex items-baseline gap-2 text-xs">
                  <span className="data-num w-8 shrink-0 text-ink-soft">
                    {j.jumlah > 0 ? `${j.jumlah}×` : "—"}
                  </span>
                  <span className="text-ink-soft">{j.jenis}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {cei != null && (
        <div className="mt-4 border-t border-canvas pt-3">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Nilai paparan stasiun
            </p>
            <span className="data-num text-lg font-semibold text-ink">
              {cei.toFixed(1)}
              <span className="text-[10px] font-medium text-muted">/100</span>
            </span>
          </div>
          <span className="mt-1.5 block h-1.5 w-full bg-canvas">
            <span
              className="block h-full bg-accent"
              style={{ width: `${Math.round(cei)}%` }}
            />
          </span>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
            {kelasPaparan}.{" "}
            {cei >= 70
              ? "Jangkauannya luas — layak untuk merek besar yang mengejar kesadaran luas."
              : cei >= 40
                ? "Jangkauannya menengah — paling efektif untuk merek yang menyasar komuter harian."
                : "Jangkauannya terbatas — cocok untuk penawaran lokal, dan itu perlu disampaikan sejak awal."}
          </p>
          <p className="mt-1 text-[10px] leading-relaxed text-muted">
            Nilai ini berlaku untuk STASIUN, bukan untuk titik ini sendiri. Yang
            membedakan antar-titik adalah pola singgah dan keramaiannya di bawah.
          </p>
        </div>
      )}

      {area.waktu_singgah?.label && area.waktu_singgah.label !== "tidak terbaca" && (
        <div className="mt-4 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Iklan yang cocok di titik ini
          </p>
          <p className="mt-1 text-xs leading-relaxed text-ink-soft">
            Waktu singgah <strong>{area.waktu_singgah.label}</strong> —{" "}
            {area.waktu_singgah.alasan}
            {area.waktu_singgah.dari_pola_stasiun && " (mengikuti pola umum stasiun ini)"}.
          </p>
          {area.format_iklan?.bentuk && (
            <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
              Format: <strong>{area.format_iklan.bentuk}</strong>.
            </p>
          )}
          {area.sektor_iklan?.sektor?.length > 0 && (
            <>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-soft">
                Sektor yang masuk akal: {area.sektor_iklan.sektor.join(", ")}.
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-muted">
                {area.sektor_iklan.dasar}
              </p>
            </>
          )}
        </div>
      )}

      {waktu.length > 0 && (
        <div className="mt-4 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Keramaian di titik ini
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {waktu.map(([rentang, v]) => (
              <li key={rentang} className="flex items-center gap-2 text-xs">
                <span className="w-12 shrink-0 capitalize text-ink-soft">{rentang}</span>
                <span className="flex h-2 flex-1 overflow-hidden bg-canvas">
                  <span
                    className="block h-full bg-accent"
                    style={{ width: `${((v!.setara_1_5 - 1) / 4) * 100}%` }}
                  />
                </span>
                <span className="data-num shrink-0 text-ink-soft">{v!.setara_1_5}/5</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {area.iklan.kutipan.length > 0 && (
        <div className="mt-4 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Catatan surveyor
          </p>
          {area.iklan.kutipan.map((k) => (
            <p
              key={k}
              className="mt-1.5 border-l-2 border-hair pl-2 text-[11px] italic leading-relaxed text-muted"
            >
              &ldquo;{k}&rdquo;
            </p>
          ))}
        </div>
      )}

      {area.foto.length > 0 && (
        <div className="mt-4 border-t border-canvas pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Foto lapangan
          </p>
          <div className="mt-1.5 grid grid-cols-2 gap-2">
            {area.foto.map((url) => (
              <a key={url} href={url} target="_blank" rel="noreferrer">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={urlFoto(url)}
                  alt={`Foto ${area.nama}`}
                  loading="lazy"
                  className="h-40 w-full border border-hair object-cover"
                />
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KartuIklan({ area, onBuka }: { area: AreaStasiun; onBuka: () => void }) {
  // Terpakai dan kosong dijumlahkan jadi satu angka per jenis: status
  // keterisian tidak ditampilkan, hanya inventarisnya.
  const rincian = area.iklan.per_jenis
    .map((j) => ({ jenis: j.jenis, jumlah: j.terpakai + j.kosong }))
    .sort((a, b) => b.jumlah - a.jumlah);
  return (
    // Seluruh kartu yang diklik, bukan tombol kecil di sudutnya. Kartunya sudah
    // memuat ringkasan titik itu; menyembunyikan jalan ke rinciannya di balik
    // satu label sempit membuat sasaran kliknya jauh lebih kecil daripada
    // benda yang sebenarnya sedang dipilih pembaca.
    //
    // `role="button"` dipakai, bukan elemen <button>, karena di dalam kartu ada
    // tautan foto - dan tautan tidak boleh bersarang di dalam tombol.
    <li
      role="button"
      tabIndex={0}
      onClick={onBuka}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onBuka();
        }
      }}
      className="group cursor-pointer border border-hair p-3 transition-colors hover:border-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      <div className="flex w-full items-baseline justify-between gap-3 text-left">
        <h3 className="min-w-0 text-sm font-semibold leading-snug text-ink underline decoration-transparent underline-offset-2 transition-colors group-hover:decoration-hair">
          {area.nama}
        </h3>
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
            titik ini:
          </>
        ) : (
          <>Media iklan tercatat di titik ini, jumlah satuannya tidak dicatat surveyor:</>
        )}
      </p>

      {/*
        Rincian PER JENIS, bukan sekadar nama-nama yang dirangkai koma.
        "7 media iklan: landscape digital, koridor BRT, charging station" tidak
        memberi tahu berapa banyak masing-masing - padahal justru itu yang
        dibutuhkan orang yang menimbang mau memasang di mana.
      */}
      <ul className="mt-1 flex flex-col gap-0.5">
        {rincian.map((j) => (
          <li key={j.jenis} className="flex items-baseline gap-2 text-[11px] leading-relaxed">
            <span className="data-num shrink-0 text-ink-soft">
              {j.jumlah > 0 ? `${j.jumlah}×` : "—"}
            </span>
            <span className="text-ink-soft">{j.jenis}</span>
          </li>
        ))}
      </ul>

      {area.waktu_singgah?.label && area.waktu_singgah.label !== "tidak terbaca" && (
        <div className="mt-2 border-t border-canvas pt-2">
          <p className="text-[11px] leading-relaxed text-ink-soft">
            <span className="label-caps mr-1 text-[9px] text-muted">Pola singgah</span>
            <strong>{area.waktu_singgah.label}</strong> — {area.waktu_singgah.alasan}
            {area.waktu_singgah.dari_pola_stasiun && (
              <span className="text-muted"> (mengikuti pola umum stasiun ini)</span>
            )}
            .
          </p>

          {area.format_iklan?.bentuk && (
            <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
              <span className="label-caps mr-1 text-[9px] text-muted">Format</span>
              {area.format_iklan.bentuk}.
            </p>
          )}

          {area.sektor_iklan?.sektor?.length > 0 && (
            <>
              <p className="mt-1 text-[11px] leading-relaxed text-ink-soft">
                <span className="label-caps mr-1 text-[9px] text-muted">Sektor</span>
                {area.sektor_iklan.sektor.join(", ")}.
              </p>
              {area.sektor_iklan.catatan && (
                <p className="mt-1 text-[10px] leading-relaxed text-muted">
                  {area.sektor_iklan.catatan}
                </p>
              )}
              <p className="mt-0.5 text-[10px] leading-relaxed text-muted">
                {area.sektor_iklan.dasar}
              </p>
            </>
          )}
        </div>
      )}

      {area.iklan.kutipan[0] && (
        <p className="mt-2 border-l-2 border-hair pl-2 text-[11px] italic leading-relaxed text-muted">
          “{area.iklan.kutipan[0]}”
        </p>
      )}

      {area.foto.length > 0 && (
        // Klik pada foto berhenti di sini: fotonya membuka tab baru, dan tanpa
        // penghentian ini rincian titiknya ikut terbuka di belakang tab itu.
        <div
          className="mt-2 flex gap-1.5 overflow-x-auto"
          onClick={(e) => e.stopPropagation()}
        >
          {area.foto.map((url) => (
            <FotoSurvei key={url} url={url} nama={area.nama} />
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

/**
 * Foto survei yang tidak pernah tampil sebagai gambar rusak.
 *
 * 76 dari sekitar 3.400 foto Activity berformat HEIC - format bawaan kamera
 * iPhone - dan hanya Safari yang bisa menampilkannya. Di Chrome dan Firefox
 * gambarnya gagal dimuat, dan yang terlihat pembaca cuma kotak kosong tanpa
 * penjelasan. CDN MAPID tidak menyediakan konversi: dicoba dengan `?format=jpg`
 * dan `?f=jpg`, balasannya tetap `image/heic`.
 *
 * Maka kegagalannya ditangani apa adanya: kotaknya diganti tautan yang
 * menjelaskan kenapa dan tetap bisa dibuka. Penanganannya tidak dikhususkan
 * untuk HEIC - `onError` menangkap sebab apa pun, termasuk tautan kedaluwarsa.
 */
function FotoSurvei({ url, nama }: { url: string; nama: string }) {
  const [gagal, setGagal] = useState(false);

  // HEIC kini DIKONVERSI di backend, bukan disembunyikan. Placeholder hanya
  // dipakai kalau konversinya pun gagal - misalnya berkasnya rusak atau CDN
  // sedang tidak bisa dihubungi.
  if (gagal) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="flex h-16 w-24 shrink-0 flex-col items-center justify-center border border-dashed border-hair px-1 text-center text-[9px] leading-tight text-muted hover:border-ink hover:text-ink"
      >
        <span className="font-semibold">Foto</span>
        <span>buka di tab baru</span>
      </a>
    );
  }

  return (
    <a href={url} target="_blank" rel="noreferrer" className="shrink-0">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={urlFoto(url)}
        alt={`Foto ${nama}`}
        loading="lazy"
        onError={() => setGagal(true)}
        className="h-16 w-24 border border-hair object-cover"
      />
    </a>
  );
}
