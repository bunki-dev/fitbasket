import type { FoodEntryOut } from "./runtime/foodlog";
import type { AppState, ChatResponse } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; provider: string; model: string }>("/api/health"),
  newSession: () =>
    request<{ session_id: string; state: AppState }>("/api/sessions", { method: "POST", body: "{}" }),
  getSession: (id: string) => request<{ session_id: string; state: AppState }>(`/api/sessions/${id}`),
  chat: (id: string, message: string, food_log: FoodEntryOut[] = []) =>
    request<ChatResponse>(`/api/sessions/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, food_log }),
    }),
};
