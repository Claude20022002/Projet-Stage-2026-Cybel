import type { LabTourInfo, Lang, TourStatus } from "./types";

const API_BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    try {
      const body = JSON.parse(detail) as { error?: string; detail?: string };
      throw new Error(body.error || body.detail || detail || response.statusText);
    } catch (err) {
      if (err instanceof Error && err.message !== detail) throw err;
      throw new Error(detail || response.statusText);
    }
  }
  return response.json() as Promise<T>;
}

export const api = {
  getTour: () => request<LabTourInfo>("/api/tour"),
  getTourStatus: () => request<TourStatus>("/api/tour/status"),
  startTour: (lang: Lang) =>
    request<{ ok: boolean; status?: TourStatus }>(`/api/tour/start?lang=${lang}`, {
      method: "POST",
    }),
  stopTour: () =>
    request<{ ok: boolean; status?: TourStatus }>("/api/tour/stop", { method: "POST" }),
};
