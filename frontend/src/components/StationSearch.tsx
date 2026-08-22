"use client";

import { useId, useMemo, useState, type KeyboardEvent } from "react";

import type { StationFeature } from "@/types/station";

const MAKS_SARAN = 8;

type Props = {
  stations: StationFeature[];
  loading: boolean;
  error: string | null;
  onSelect: (station: StationFeature) => void;
};

export default function StationSearch({
  stations,
  loading,
  error,
  onSelect,
}: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const listId = useId();

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return stations
      .filter((f) => f.properties.name.toLowerCase().includes(q))
      .slice(0, MAKS_SARAN);
  }, [query, stations]);

  const showDropdown = open && query.trim() !== "";

  function pilih(station: StationFeature) {
    onSelect(station);
    setQuery(station.properties.name);
    setOpen(false);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!showDropdown || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      pilih(results[activeIndex]);
    }
  }

  return (
    <div className="w-80 max-w-[calc(100vw-2rem)]">
      <input
        type="text"
        role="combobox"
        aria-expanded={showDropdown}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={
          showDropdown && results.length > 0
            ? `${listId}-opt-${activeIndex}`
            : undefined
        }
        aria-label="Cari stasiun"
        value={query}
        placeholder={loading ? "Memuat data stasiun…" : "Cari stasiun…"}
        disabled={loading || error !== null}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIndex(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 shadow-lg outline-none placeholder:text-slate-400 focus:border-slate-500 disabled:bg-slate-100"
      />

      {error !== null && (
        <p
          role="alert"
          className="mt-1 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700 shadow-lg"
        >
          {error}
        </p>
      )}

      {showDropdown && results.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          onMouseDown={(e) => e.preventDefault()}
          className="mt-1 max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
        >
          {results.map((f, i) => (
            <li
              key={String(f.id ?? f.properties.name)}
              id={`${listId}-opt-${i}`}
              role="option"
              aria-selected={i === activeIndex}
            >
              <button
                type="button"
                tabIndex={-1}
                onClick={() => pilih(f)}
                onMouseEnter={() => setActiveIndex(i)}
                className={`block w-full px-4 py-2 text-left text-sm ${
                  i === activeIndex ? "bg-slate-100" : "bg-white"
                }`}
              >
                <span className="text-slate-900">{f.properties.name}</span>
                {f.properties.kecamatan && (
                  <span className="ml-2 text-xs text-slate-500">
                    {f.properties.kecamatan}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {showDropdown && results.length === 0 && !loading && error === null && (
        <p className="mt-1 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-500 shadow-lg">
          Tidak ada stasiun yang cocok
        </p>
      )}
    </div>
  );
}
