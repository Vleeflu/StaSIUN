"use client";

import { useEffect, useState } from "react";

import { apiGet, urlApi } from "@/lib/api";

type Persona = { id: string; label: string };

// Daftarnya DIAMBIL DARI BACKEND, tidak ditulis ulang di sini. Sebelumnya
// labelnya disalin ke frontend dan langsung melenceng - dokumennya menulis
// "Perencana kawasan dan regulator" sementara pemilihnya menawarkan
// "Regulator & pemerintah daerah". Dua tempat untuk satu daftar berarti
// keduanya pasti berbeda, cepat atau lambat.
const CADANGAN: Persona[] = [{ id: "pengelola", label: "Pengelola aset stasiun" }];

/**
 * Satu pintu ekspor untuk seluruh fitur, bukan satu tombol per tab.
 *
 * Sebelumnya kotak unduh ini menempel di dalam Ikhtisar, sehingga pembaca yang
 * sedang membuka Ad-Space atau Tenant tidak punya cara mengunduh apa pun tanpa
 * berpindah tab dulu - padahal dokumennya memang memuat semua bagian sekaligus.
 * Menaruhnya di header membuat satu-satunya tombol ekspor berlaku untuk seluruh
 * halaman, dan letaknya tidak berubah ke mana pun pengguna pergi.
 */
export default function EksporModal({
  stationId,
  stationName,
  onClose,
}: {
  stationId: number | null;
  stationName: string | null;
  onClose: () => void;
}) {
  const [persona, setPersona] = useState("pengelola");
  const [daftar, setDaftar] = useState<Persona[]>(CADANGAN);

  useEffect(() => {
    let batal = false;
    apiGet<{ persona: Persona[] }>("/persona")
      .then((d) => !batal && d.persona?.length && setDaftar(d.persona))
      .catch(() => {
        /* Pemilih tetap bisa dipakai dengan persona bawaan. */
      });
    return () => {
      batal = true;
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const alamat =
    stationId === null
      ? null
      : urlApi(`/stations/${stationId}/ekspor?persona=${persona}`);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Ekspor laporan"
      onClick={onClose}
    >
      <div
        className="flex max-h-[88vh] w-full max-w-md flex-col border border-ink bg-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-hair p-4">
          <div className="min-w-0">
            <p className="label-caps text-accent">Ekspor laporan</p>
            <h2 className="mt-1 text-xl font-bold leading-tight tracking-[-0.01em]">
              {stationName ?? "Belum ada stasiun terpilih"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Tutup ekspor"
            className="shrink-0 border border-hair px-2 py-1 text-sm leading-none text-ink-soft hover:border-ink hover:text-ink"
          >
            ✕
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {alamat === null ? (
            <p className="text-xs leading-relaxed text-ink-soft">
              Pilih dulu satu stasiun di peta. Laporannya memuat skor, ruang
              iklan, kelayakan usaha, dan hak penamaan untuk stasiun itu, jadi
              ia butuh stasiun sebagai acuan.
            </p>
          ) : (
            <>
              <p className="text-xs leading-relaxed text-ink-soft">
                Seluruh analisis stasiun ini dalam satu dokumen yang bisa
                dibagikan, potensi kawasan, ruang iklan, kelayakan usaha, dan
                hak penamaan sekaligus. Pilih dulu siapa pembacanya; urutan dan
                penekanannya menyesuaikan.
              </p>

              <label className="mt-3 block">
                <span className="label-caps mb-1 block text-[9px] text-muted">
                  Pembaca dokumen
                </span>
                <select
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  className="w-full border border-hair bg-panel px-2 py-2 text-xs text-ink-soft"
                >
                  {daftar.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </label>

              <a
                href={alamat}
                target="_blank"
                rel="noreferrer"
                className="mt-3 block w-full border border-ink bg-ink px-3 py-2.5 text-center text-xs font-semibold text-panel hover:opacity-90"
              >
                Buka dokumen laporan →
              </a>

              {/*
                Petunjuk menyimpan PDF sengaja ditaruh DI SINI, bukan di dalam
                dokumennya. Petunjuk yang ditulis di dalam dokumen akan ikut
                tercetak, dan pembaca laporan akan menerima lembar berisi
                instruksi untuk dirinya sendiri yang sama sekali tidak relevan.
              */}
              <div className="mt-3 border border-hair bg-canvas p-2.5">
                <p className="label-caps mb-1 text-[9px] text-muted">
                  Cara menyimpan sebagai PDF
                </p>
                <ol className="flex list-decimal flex-col gap-0.5 pl-4 text-[10px] leading-relaxed text-ink-soft">
                  <li>Dokumen terbuka di tab baru.</li>
                  <li>
                    Tekan <strong>Ctrl + P</strong> (Windows) atau{" "}
                    <strong>Cmd + P</strong> (Mac).
                  </li>
                  <li>
                    Pada pilihan <em>Destination</em> atau <em>Printer</em>,
                    pilih <strong>Save as PDF</strong>.
                  </li>
                  <li>
                    Aktifkan <em>Background graphics</em> agar garis dan warna
                    judulnya ikut tercetak.
                  </li>
                  <li>Klik <strong>Save</strong>, lalu pilih lokasi berkasnya.</li>
                </ol>
              </div>

              <p className="mt-2 text-[10px] leading-relaxed text-muted">
                Persona mengubah urutan bagian, penekanan, dan tampilan dokumen,
                tetapi tidak mengubah angkanya. Metadata keyakinan selalu
                disertakan pada seluruh versi.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
