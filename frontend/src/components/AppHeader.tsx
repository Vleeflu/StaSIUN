type Props = {
  stationCount: number;
  loading: boolean;
};

export default function AppHeader({ stationCount, loading }: Props) {
  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-ink bg-canvas px-4">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center bg-accent text-white">
        <StationMark />
      </div>

      <span className="text-lg font-bold tracking-tight">StaSIUN</span>

      <span className="hidden h-5 w-px bg-hair sm:block" />

      <span className="label-caps hidden text-ink-soft sm:block">
        Station Spatial Intelligence for Urban Network
      </span>

      <div className="ml-auto flex items-center gap-4">
        <span className="data-num hidden text-[11px] text-muted md:block">
          {loading ? "Memuat data…" : `${stationCount} stasiun KAI · DKI Jakarta`}
        </span>

        {/* Ekspor laporan belum ada di backend, jadi tombolnya sengaja mati
            supaya tidak menjanjikan sesuatu yang belum bisa dilakukan. */}
        <button
          type="button"
          disabled
          title="Belum tersedia"
          className="flex cursor-not-allowed items-center gap-2 border border-hair bg-canvas px-3 py-1.5 text-xs font-semibold text-muted"
        >
          <DownloadMark />
          Ekspor Laporan
        </button>

        <span className="label-caps hidden text-muted lg:block">Mode demo</span>
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
