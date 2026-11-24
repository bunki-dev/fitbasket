import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Turn } from "../types";
import { Arrow } from "./Doodles";

const STARTERS = [
  "Plan my meals and build this week's shop",
  "I'm allergic to peanuts and my budget is $140",
  "Make me a 4-day workout for abs, I play cricket on Saturday",
  "How do I do a dead bug?",
];

interface Props {
  turns: Turn[];
  busy: boolean;
  error: string | null;
  onSend: (text: string) => void;
}

export function Chat({ turns, busy, error, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, busy]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onSend(text);
  }

  return (
    <section className="chat" aria-label="Conversation">
      <div className="chat-log" role="log" aria-live="polite">
        {turns.length === 0 && (
          <div className="chat-empty">
            <h1>
              Eat well, shop smart,
              <br />
              train around life.
            </h1>
            <p>
              Tell me your goal, allergies, budget and the days you train. I'll plan the week's meals, fill your
              trolley from the specials and what's already in the pantry, and write your workouts.
            </p>
            <p className="margin-note starters-note">
              or start with one of these
              <Arrow />
            </p>
            <div className="starters">
              {STARTERS.map((s) => (
                <button key={s} type="button" onClick={() => onSend(s)} disabled={busy}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`turn turn-${t.role}`}>
            <p>{t.text}</p>
            {t.meta && t.meta.tool_events.length > 0 && (
              <p className="turn-meta">
                Used {t.meta.tool_events.map((e) => e.name.replace(/_/g, " ")).join(", ")} in{" "}
                {(t.meta.latency_ms / 1000).toFixed(1)}s
              </p>
            )}
          </div>
        ))}
        {busy && <div className="turn turn-assistant turn-pending">Writing your list…</div>}
        {error && (
          <div className="chat-error" role="alert">
            Something went wrong: {error}
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <label htmlFor="msg" className="visually-hidden">
          Message
        </label>
        <textarea
          id="msg"
          rows={2}
          value={draft}
          placeholder="e.g. Swap Tuesday's dinner for something vegetarian"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) submit(e);
          }}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </section>
  );
}
