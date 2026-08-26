"use client";

import { useId, useMemo, useState, type KeyboardEvent } from "react";

import { lineLabel } from "@/lib/lines";
import { parseLines } from "@/types/station";
import type { StationFeature } from "@/types/station";

const MAX_SUGGESTIONS = 8;

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
      .slice(0, MAX_SUGGESTIONS);
  }, [query, stations]);

  const showDropdown = open && query.trim() !== "";

  function choose(station: StationFeature) {
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
      choose(results[activeIndex]);
    }
  }

  return (
    <div className="relative">
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
        placeholder={loading ? "Memuat data stasiun…" : "mis. Manggarai"}
        disabled={loading || error !== null}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIndex(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        className="w-full border border-hair bg-panel px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-ink disabled:bg-canvas disabled:text-muted"
      />

      {error !== null && (
        <p
          role="alert"
          className="mt-2 border border-accent bg-accent-soft px-3 py-2 text-xs text-ink"
        >
          {error}
        </p>
      )}

      {/* Dropdown mengambang di atas isi panel supaya seksi di bawahnya tidak
          ikut terdorong tiap kali user mengetik. */}
      {showDropdown && results.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          onMouseDown={(e) => e.preventDefault()}
          className="absolute left-0 right-0 top-full z-20 mt-px max-h-72 overflow-y-auto border border-ink bg-panel"
        >
          {results.map((f, i) => {
            const codes = parseLines(f.properties.lines);
            return (
              <li
                key={String(f.id ?? f.properties.name)}
                id={`${listId}-opt-${i}`}
                role="option"
                aria-selected={i === activeIndex}
              >
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => choose(f)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`block w-full px-3 py-2 text-left ${
                    i === activeIndex ? "bg-accent text-white" : "bg-panel"
                  }`}
                >
                  <span className="block text-sm font-medium">
                    {f.properties.name}
                  </span>
                  <span
                    className={`block text-xs ${
                      i === activeIndex ? "text-white/80" : "text-muted"
                    }`}
                  >
                    {codes.length > 0
                      ? lineLabel(codes)
                      : (f.properties.network ?? "Tanpa lin")}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {showDropdown && results.length === 0 && !loading && error === null && (
        <p className="absolute left-0 right-0 top-full z-20 mt-px border border-hair bg-panel px-3 py-2 text-xs text-muted">
          Tidak ada stasiun yang cocok
        </p>
      )}
    </div>
  );
}
