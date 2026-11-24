import { useEffect, useMemo, useState } from "react";
import { Chat } from "./components/Chat";
import { MealWeek } from "./components/MealWeek";
import { Receipt } from "./components/Receipt";
import { Settings } from "./components/Settings";
import { TraceView } from "./components/TraceView";
import { Workouts } from "./components/Workouts";
import { createBackend } from "./runtime/backend";
import { loadSettings, type ModelSettings } from "./runtime/settings";
import type { AppState, ChatResponse, Turn } from "./types";

type Tab = "basket" | "meals" | "workouts" | "trace";
type View = "chat" | Tab;
const TABS: { id: Tab; label: string }[] = [
  { id: "basket", label: "Basket" },
  { id: "meals", label: "Meals" },
  { id: "workouts", label: "Workouts" },
  { id: "trace", label: "Agent trace" },
];
const PROVIDER_LABEL: Record<string, string> = { offline: "Demo mode", anthropic: "Claude", azure: "Azure AI" };
const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function App() {
  const backend = useMemo(createBackend, []);
  const [state, setState] = useState<AppState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [tab, setTab] = useState<Tab>("basket");
  const [view, setView] = useState<View>("chat"); // small screens show one view at a time
  const [fresh, setFresh] = useState<Set<Tab>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState("Starting FitBasket…");
  const [model, setModel] = useState("");
  const [settings, setSettings] = useState<ModelSettings>(loadSettings);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    backend
      .start(setLoading)
      .then((s) => {
        setState(s.state);
        setTurns(s.turns);
        setLoading("");
      })
      .catch((e: Error) => {
        setLoading("");
        setError(e.message);
      });
  }, [backend]);

  useEffect(() => {
    if (loading) return;
    backend
      .describe()
      .then((d) => setModel(d.provider === "offline" ? "Demo mode" : `${PROVIDER_LABEL[d.provider] ?? d.provider} (${d.model})`))
      .catch(() => setModel(""));
  }, [backend, loading, settings]);

  async function send(text: string) {
    setTurns((t) => [...t, { role: "user", text }]);
    setBusy(true);
    setError(null);
    try {
      const res = await backend.chat(text);
      setTurns((t) => [...t, { role: "assistant", text: res.reply, meta: res }]);
      setState(res.state);
      setLast(res);
      const touched = new Set(res.tool_events.filter((e) => e.ok).map((e) => e.name));
      const updated: Tab[] = [];
      if (touched.has("build_shopping_basket")) updated.push("basket");
      if (touched.has("create_meal_plan") || touched.has("swap_meal")) updated.push("meals");
      if (touched.has("create_workout_plan")) updated.push("workouts");
      if (updated.length) {
        setTab(updated[0]);
        setFresh((f) => new Set([...f, ...updated]));
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    if (!window.confirm("Start over? This clears your plan, basket and chat on this device.")) return;
    const s = await backend.reset();
    setState(s.state);
    setTurns([]);
    setLast(null);
    setFresh(new Set());
    setView("chat");
  }

  function open(next: View) {
    setView(next);
    if (next !== "chat") {
      setTab(next);
      setFresh((f) => {
        const copy = new Set(f);
        copy.delete(next);
        return copy;
      });
    }
  }

  if (loading) {
    return (
      <div className="boot" role="status">
        <span className="brand-mark brand-mark-lg" aria-hidden="true" />
        <p>{loading}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          FitBasket
        </div>
        {state && (
          <ul className="who" aria-label="Profile">
            <li>{state.profile.name}</li>
            <li>{sentence(state.profile.goal.replace("_", " "))}</li>
            <li>{sentence(state.profile.diet)}</li>
            {state.profile.allergies.length > 0 && <li>No {state.profile.allergies.join(", ")}</li>}
            {state.profile.weekly_budget != null && <li>${state.profile.weekly_budget} a week</li>}
          </ul>
        )}
        <div className="topbar-right">
          {backend.kind === "browser" ? (
            <button type="button" className="ghost" onClick={() => setShowSettings(true)}>
              {model || "AI model"}
            </button>
          ) : (
            model && <span className="model">{model}</span>
          )}
          <button type="button" className="ghost" onClick={reset}>
            Start over
          </button>
        </div>
      </header>

      <main className="layout" data-view={view}>
        <Chat turns={turns} busy={busy} error={error} onSend={send} />
        <aside className="panel">
          <nav className="tabs" role="tablist" aria-label="Plan views">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                type="button"
                aria-selected={tab === t.id}
                className={tab === t.id ? "active" : undefined}
                onClick={() => open(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <div className="panel-body" role="tabpanel">
            {tab === "basket" && <Receipt basket={state?.basket ?? null} />}
            {tab === "meals" && <MealWeek plan={state?.meal_plan ?? null} />}
            {tab === "workouts" && <Workouts plan={state?.workout_plan ?? null} />}
            {tab === "trace" && <TraceView last={last} />}
          </div>
        </aside>
      </main>

      <nav className="bottom-nav" aria-label="Sections">
        {([{ id: "chat", label: "Chat" }, ...TABS.slice(0, 3)] as { id: View; label: string }[]).map((t) => (
          <button
            key={t.id}
            type="button"
            aria-current={view === t.id ? "page" : undefined}
            onClick={() => open(t.id)}
          >
            <NavIcon id={t.id} />
            {t.label}
            {t.id !== "chat" && fresh.has(t.id as Tab) && <span className="dot" aria-label="updated" />}
          </button>
        ))}
      </nav>

      {showSettings && (
        <Settings
          initial={settings}
          onClose={(saved) => {
            setShowSettings(false);
            if (saved) setSettings(saved);
          }}
        />
      )}
    </div>
  );
}

function NavIcon({ id }: { id: View }) {
  const paths: Record<string, string> = {
    chat: "M4 5h16v11H9l-5 4z",
    basket: "M3 9h18l-2 11H5zM8 9l4-5 4 5",
    meals: "M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M16 3c-2 2-2 6 0 8v10",
    workouts: "M3 10v4M6 7v10M18 7v10M21 10v4M6 12h12",
  };
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d={paths[id] ?? ""} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}
