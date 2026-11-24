import { useEffect, useState } from "react";
import { api } from "./api";
import { Chat } from "./components/Chat";
import { MealWeek } from "./components/MealWeek";
import { Receipt } from "./components/Receipt";
import { TraceView } from "./components/TraceView";
import { Workouts } from "./components/Workouts";
import type { AppState, ChatResponse, Turn } from "./types";

type Tab = "basket" | "meals" | "workouts" | "trace";
const TABS: { id: Tab; label: string }[] = [
  { id: "basket", label: "Basket" },
  { id: "meals", label: "Meals" },
  { id: "workouts", label: "Workouts" },
  { id: "trace", label: "Agent trace" },
];
const sentence = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const SESSION_KEY = "fitbasket.session";

function readSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

function writeSession(id: string) {
  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch {
    /* storage unavailable: session lasts for this page only */
  }
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState<AppState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [tab, setTab] = useState<Tab>("basket");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState<string>("");

  useEffect(() => {
    api.health().then((h) => setModel(`${h.provider} / ${h.model}`)).catch(() => setModel(""));
    const saved = readSession();
    const start = saved
      ? api.getSession(saved).catch(() => api.newSession())
      : api.newSession();
    start
      .then((s) => {
        setSessionId(s.session_id);
        setState(s.state);
        writeSession(s.session_id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function send(text: string) {
    if (!sessionId) return;
    setTurns((t) => [...t, { role: "user", text }]);
    setBusy(true);
    setError(null);
    try {
      const res = await api.chat(sessionId, text);
      setTurns((t) => [...t, { role: "assistant", text: res.reply, meta: res }]);
      setState(res.state);
      setLast(res);
      const touched = new Set(res.tool_events.filter((e) => e.ok).map((e) => e.name));
      if (touched.has("build_shopping_basket")) setTab("basket");
      else if (touched.has("create_meal_plan") || touched.has("swap_meal")) setTab("meals");
      else if (touched.has("create_workout_plan")) setTab("workouts");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    const s = await api.newSession();
    setSessionId(s.session_id);
    setState(s.state);
    writeSession(s.session_id);
    setTurns([]);
    setLast(null);
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
          {model && <span className="model">{model}</span>}
          <button type="button" className="ghost" onClick={reset}>
            Start over
          </button>
        </div>
      </header>
      <main className="layout">
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
                onClick={() => setTab(t.id)}
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
    </div>
  );
}
