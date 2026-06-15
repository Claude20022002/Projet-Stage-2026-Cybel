import type { FaqEntry, Lang, ReceptionAction } from "./types";

const API_BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  getActions: () => request<ReceptionAction[]>("/api/reception/actions"),
  executeAction: (actionId: string, lang: Lang) =>
    request<{ ok: boolean; events?: string[] }>(
      `/api/reception/actions/${actionId}/execute?lang=${lang}`,
      { method: "POST" }
    ),
  getFaq: () => request<FaqEntry[]>("/api/knowledge/faq"),
  speak: (text: string, interrupt = true) =>
    request<{ ok: boolean; method?: string }>("/api/speech/say", {
      method: "POST",
      body: JSON.stringify({ text, interrupt }),
    }),
};
