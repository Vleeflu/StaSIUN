"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { apiPost } from "@/lib/api";
import type { StationFeature } from "@/types/station";

type ChatMessage = { role: "user" | "assistant"; content: string };

const SUGGESTIONS = [
  "Stasiun mana saja yang interchange?",
  "Apa itu SEPI dan bagaimana dihitungnya?",
  "Kenapa Gambir tidak dilayani KRL?",
];

/**
 * Model kadang tetap menyelipkan markdown dan LaTeX walau sudah dilarang di
 * prompt. Panel ini merender teks polos, jadi penandanya dibersihkan dulu.
 */
function toPlainText(text: string): string {
  return text
    .replace(/\*\*/g, "")
    .replace(/(^|\s)\*(\S)/g, "$1$2")
    .replace(/(\S)\*(\s|$)/g, "$1$2")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\$/g, "");
}

type Props = {
  station: StationFeature | null;
};

export default function ChatPanel({ station }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Menyimpan stasiun yang konteksnya sengaja dilepas user, bukan sekadar
  // benar/salah. Dengan begitu pindah ke stasiun lain otomatis memunculkan
  // chip-nya lagi tanpa perlu efek tambahan.
  const [dismissedId, setDismissedId] = useState<string | number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  const context = station && station.id !== dismissedId ? station : null;

  useEffect(() => {
    const box = scrollRef.current;
    if (box) box.scrollTop = box.scrollHeight;
  }, [messages, sending]);

  async function send(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const history = messages;
    setMessages([...history, { role: "user", content: trimmed }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await apiPost<{ reply: string }>("/chat", {
        message: trimmed,
        history,
        // Backend memakai ini supaya pertanyaan seperti "lin apa saja di sini"
        // tahu stasiun mana yang sedang dibuka.
        station_id: typeof context?.id === "number" ? context.id : null,
      });

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Gagal menghubungi asisten."
      );
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-xs leading-relaxed text-ink-soft">
              Asisten ini dibekali seluruh daftar stasiun di database beserta
              lin, kode, dan statusnya. Skor SEPI dan turunannya belum dihitung,
              jadi kalau ditanya soal itu dia akan bilang belum ada — bukan
              mengarang angka.
            </p>

            <div className="flex flex-col gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => void send(s)}
                  className="border border-hair px-3 py-2 text-left text-xs text-ink-soft hover:border-ink hover:text-ink"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <ul className="flex flex-col gap-4">
          {messages.map((m, i) => (
            <li
              key={i}
              className={m.role === "user" ? "flex justify-end" : undefined}
            >
              {m.role === "user" ? (
                <p className="max-w-[85%] border border-hair bg-canvas px-3 py-2 text-xs leading-relaxed">
                  {m.content}
                </p>
              ) : (
                <div className="border-l-2 border-accent pl-3">
                  <p className="label-caps mb-1 text-muted">Asisten</p>
                  <p className="whitespace-pre-wrap text-xs leading-relaxed">
                    {toPlainText(m.content)}
                  </p>
                </div>
              )}
            </li>
          ))}
        </ul>

        {sending && (
          <p className="label-caps mt-4 text-muted">Sedang menyusun jawaban…</p>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 border border-accent bg-accent-soft px-3 py-2 text-xs leading-relaxed"
          >
            {error}
          </p>
        )}
      </div>

      <div className="shrink-0 border-t border-hair">
        {context && (
          <div className="flex items-center gap-2 border-b border-hair px-3 py-2">
            <span className="label-caps shrink-0 text-muted">Konteks</span>
            <span className="truncate text-xs text-ink">
              {context.properties.name}
            </span>
            <button
              type="button"
              onClick={() => setDismissedId(context.id ?? null)}
              aria-label={`Lepas konteks ${context.properties.name}`}
              className="ml-auto shrink-0 border border-hair px-1.5 text-xs leading-5 text-muted hover:border-ink hover:text-ink"
            >
              ✕
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2 p-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            placeholder="Tanya soal stasiun atau metodenya…"
            aria-label="Pertanyaan untuk asisten"
            className="min-w-0 flex-1 border border-hair bg-panel px-3 py-2 text-xs outline-none placeholder:text-muted focus:border-ink disabled:bg-canvas"
          />
          <button
            type="submit"
            disabled={sending || input.trim() === ""}
            className="shrink-0 bg-ink px-3 py-2 text-xs font-semibold text-white disabled:bg-hair disabled:text-muted"
          >
            Kirim
          </button>
        </form>
      </div>
    </div>
  );
}
