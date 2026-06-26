import type {
  KioskConfig,
  KioskDestination,
  LabTourInfo,
  Lang,
  ReceptionAction,
  RobotStatus,
  SpeechStatus,
  TourStatus,
} from "./types";

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
  getConfig: () => request<KioskConfig>("/api/kiosk/config"),
  getTour: () => request<LabTourInfo>("/api/tour"),
  getTourStatus: () => request<TourStatus>("/api/tour/status"),
  startTour: (lang: Lang) =>
    request<{ ok: boolean; status?: TourStatus }>(`/api/tour/start?lang=${lang}`, {
      method: "POST",
    }),
  stopTour: () =>
    request<{ ok: boolean; status?: TourStatus }>("/api/tour/stop", { method: "POST" }),
  haltAll: () =>
    request<{ ok: boolean; message?: string }>("/api/tour/halt", { method: "POST" }),
  cancelNavigation: () =>
    request<{ ok: boolean; error?: string }>("/api/navigation/cancel", { method: "POST" }),
  goHome: () =>
    request<{ ok: boolean; error?: string }>("/api/charge/go-home", { method: "POST" }),
  getDiagnostics: () =>
    request<{ overall_ok: boolean; blocking_reason?: string }>("/api/diagnostics"),
  getDestinations: () => request<KioskDestination[]>("/api/reception/destinations"),
  getActions: () => request<ReceptionAction[]>("/api/reception/actions"),
  goDestination: (pointName: string, lang: Lang) =>
    request<{ ok: boolean; point: string; events?: string[] }>("/api/reception/go", {
      method: "POST",
      body: JSON.stringify({ point_name: pointName, lang }),
    }),
  runAction: (actionId: string, lang: Lang) =>
    request<{ ok: boolean; error?: string; events?: string[] }>(
      `/api/reception/actions/${actionId}/execute?lang=${lang}`,
      { method: "POST" }
    ),
  getRobotStatus: () => request<RobotStatus>("/api/robot/status"),
  getSpeechStatus: () => request<SpeechStatus>("/api/speech/status"),
  say: (text: string) =>
    request<{ ok: boolean }>("/api/speech/say", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
};
