type Props = {
  stationCount: number;
  loading: boolean;
  /** Nama stasiun terpilih, dipakai sebagai judul laporan. */
  stationName: string | null;
  onEkspor: () => void;
  onPeringkat: () => void;
};

export default function AppHeader({
  stationCount,
  loading,
  stationName,
  onEkspor,
  onPeringkat,
}: Props) {
  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-ink bg-canvas px-3 sm:px-4">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center bg-accent text-white">
        <StationMark />
      </div>

      <span className="text-lg font-bold tracking-tight">StaSIUN</span>

      <span className="hidden h-5 w-px bg-hair sm:block" />

      <span className="label-caps hidden text-ink-soft sm:block">
        Station Spatial Intelligence for Urban Network
      </span>

      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <span className="data-num hidden text-[11px] text-muted md:block">
          {loading ? "Memuat data…" : `${stationCount} stasiun KAI · DKI Jakarta`}
        </span>

        {/*
          Dua pintu yang berlaku di seluruh halaman, bukan per tab. Peringkat
          dulu berupa angka bergaris bawah di tengah paragraf - sasaran klik
          selebar tiga karakter yang tidak pernah terbaca sebagai tombol.
        */}
        <button
          type="button"
          onClick={onPeringkat}
          aria-label="Peringkat Stasiun"
          className="flex items-center gap-2 border border-hair bg-panel px-2.5 py-1.5 text-xs font-semibold text-ink-soft hover:border-ink hover:text-ink sm:px-3"
        >
          <RankMark />
          <span className="hidden sm:inline">Peringkat Stasiun</span>
        </button>

        <button
          type="button"
          onClick={onEkspor}
          aria-label="Ekspor Laporan"
          title={stationName ? `Laporan ${stationName}` : "Pilih stasiun dulu"}
          className="flex items-center gap-2 border border-ink bg-ink px-2.5 py-1.5 text-xs font-semibold text-panel hover:opacity-90 sm:px-3"
        >
          <DownloadMark />
          <span className="hidden sm:inline">Ekspor Laporan</span>
        </button>

        <span className="label-caps hidden text-muted lg:block">Prototype</span>
      </div>
    </header>
  );
}

function StationMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="5" y="3" width="14" height="14" />
      <path d="M5 11h14" />
      <path d="M9 21l1.5-4M15 21l-1.5-4" />
    </svg>
  );
}

function DownloadMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="13"
      height="13"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3v12" />
      <path d="M7 11l5 5 5-5" />
      <path d="M4 21h16" />
    </svg>
  );
}

function RankMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="13"
      height="13"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 20V10" />
      <path d="M12 20V4" />
      <path d="M19 20v-7" />
    </svg>
  );
}
