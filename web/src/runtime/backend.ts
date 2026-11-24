import { api } from "../api";
import type { AppState, ChatResponse, Turn } from "../types";
import { loadSettings } from "./settings";

export interface Started {
  state: AppState;
  turns: Turn[];
}

export interface Backend {
  kind: "server" | "browser";
  start(onProgress: (text: string) => void): Promise<Started>;
  describe(): Promise<{ provider: string; model: string }>;
  chat(message: string): Promise<ChatResponse>;
  reset(): Promise<Started>;
}

function store(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

// ---------- FastAPI server ----------

const SESSION_KEY = "fitbasket.session";

function serverBackend(): Backend {
  let sessionId = "";
  const begin = (s: { session_id: string; state: AppState }): Started => {
    sessionId = s.session_id;
    store(SESSION_KEY, sessionId);
    return { state: s.state, turns: [] };
  };
  return {
    kind: "server",
    async start() {
      const saved = read(SESSION_KEY);
      const s = saved ? await api.getSession(saved).catch(() => api.newSession()) : await api.newSession();
      return begin(s);
    },
    describe: () => api.health(),
    chat: (message) => api.chat(sessionId, message),
    reset: async () => begin(await api.newSession()),
  };
}

// ---------- Python in the browser (GitHub Pages) ----------

const SAVED_KEY = "fitbasket.saved";

function browserBackend(): Backend {
  const worker = new Worker(new URL("./pyWorker.ts", import.meta.url), { type: "module" });
  const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  let nextId = 1;
  let onProgress: (text: string) => void = () => {};

  worker.onmessage = (event: MessageEvent) => {
    const msg = event.data;
    if (msg.type === "progress") return onProgress(msg.text);
    const p = pending.get(msg.id);
    if (!p) return;
    pending.delete(msg.id);
    if (msg.error) p.reject(new Error(msg.error));
    else p.resolve(msg.result);
  };

  const call = <T,>(method: string, ...args: unknown[]) =>
    new Promise<T>((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve: resolve as (v: unknown) => void, reject });
      worker.postMessage({ id, method, args });
    });

  const persist = (saved: unknown) => store(SAVED_KEY, JSON.stringify(saved));

  return {
    kind: "browser",
    start(progress) {
      onProgress = progress;
      return call<Started>("init", read(SAVED_KEY));
    },
    describe: () => call("describe", loadSettings()),
    async chat(message) {
      const res = await call<ChatResponse & { saved?: unknown; error?: string }>("chat", message, loadSettings());
      if (res.error) throw new Error(res.error);
      persist(res.saved);
      return res;
    },
    async reset() {
      const res = await call<Started & { saved: unknown }>("reset");
      persist(res.saved);
      return res;
    },
  };
}

export const RUNTIME: "server" | "browser" = import.meta.env.VITE_RUNTIME === "browser" ? "browser" : "server";

export function createBackend(): Backend {
  return RUNTIME === "browser" ? browserBackend() : serverBackend();
}
