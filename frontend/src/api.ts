import type {
  LabTourData,
  MapData,
  Point,
  PointType,
  Pose,
  ReceptionAction,
  RobotSettings,
  RobotStatus,
  SpeechStatus,
  TourStatus,
  TourStopData,
} from "./types";

export interface AddPointCommand {
  name: string;
  type?: PointType;
  x?: number;
  y?: number;
  theta?: number;
}

export interface MoveCommand {
  linear_x: number;
  angular_z: number;
}

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
  health: () => request<{ status: string; mock: boolean }>("/api/health"),
  getStatus: () => request<RobotStatus>("/api/robot/status"),
  getPose: () => request<Pose>("/api/robot/pose"),
  getPoints: () => request<Point[]>("/api/navigation/points"),
  addPoint: (command: AddPointCommand) =>
    request<Point>("/api/navigation/points", {
      method: "POST",
      body: JSON.stringify(command),
    }),
  deletePoint: (name: string) =>
    request<{ ok: boolean; point: string }>(
      `/api/navigation/points/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    ),
  getMap: () => request<MapData>("/api/map/current"),
  move: (command: MoveCommand) =>
    request("/api/robot/move", {
      method: "POST",
      body: JSON.stringify(command),
    }),
  stop: () => request("/api/robot/stop", { method: "POST" }),
  emergencyStop: () =>
    request("/api/robot/emergency-stop", { method: "POST" }),
  releaseEmergencyStop: () =>
    request("/api/robot/release-emergency-stop", { method: "POST" }),
  setManualMode: (enabled: boolean) =>
    request("/api/robot/mode/manual", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
  relocalize: () => request("/api/robot/relocalize", { method: "POST" }),
  navigateTo: (pointName: string) =>
    request("/api/navigation/goto", {
      method: "POST",
      body: JSON.stringify({ point_name: pointName }),
    }),
  goToCoordinate: (x: number, y: number, theta = 0) =>
    request("/api/navigation/goto-coordinate", {
      method: "POST",
      body: JSON.stringify({ x, y, theta }),
    }),
  cancelNavigation: () =>
    request("/api/navigation/cancel", { method: "POST" }),
  getSettings: () => request<RobotSettings>("/api/settings"),
  updateSettings: (settings: RobotSettings) =>
    request<RobotSettings>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
  getActions: () => request<ReceptionAction[]>("/api/reception/actions"),
  executeAction: (actionId: string) =>
    request<{ ok: boolean; events?: string[] }>(
      `/api/reception/actions/${actionId}/execute`,
      { method: "POST" }
    ),
  voiceCommand: (text: string) =>
    request<{ ok: boolean; matched_action?: string; events?: string[] }>(
      "/api/reception/voice",
      { method: "POST", body: JSON.stringify({ text }) }
    ),
  getSpeechStatus: () => request<SpeechStatus>("/api/speech/status"),
  speak: (text: string, interrupt = true) =>
    request<{ ok: boolean; method?: string; text?: string }>("/api/speech/say", {
      method: "POST",
      body: JSON.stringify({ text, interrupt }),
    }),
  stopSpeech: () => request("/api/speech/stop", { method: "POST" }),
  getTourFull: () => request<LabTourData>("/api/tour/full"),
  getTourStatus: () => request<TourStatus>("/api/tour/status"),
  startTour: (lang: "fr" | "en" = "fr") =>
    request<{ ok: boolean; status?: TourStatus; error?: string }>(
      `/api/tour/start?lang=${lang}`,
      { method: "POST" }
    ),
  haltTour: () => request("/api/tour/halt", { method: "POST" }),
  stopTour: () => request("/api/tour/stop", { method: "POST" }),
  addTourStop: (stop: Partial<TourStopData>) =>
    request<{ ok: boolean; tour: LabTourData }>("/api/tour/stops", {
      method: "POST",
      body: JSON.stringify(stop),
    }),
  updateTourStop: (stopId: string, stop: Partial<TourStopData>) =>
    request<{ ok: boolean; tour: LabTourData }>(`/api/tour/stops/${stopId}`, {
      method: "PUT",
      body: JSON.stringify(stop),
    }),
  deleteTourStop: (stopId: string) =>
    request<{ ok: boolean; tour: LabTourData }>(`/api/tour/stops/${stopId}`, {
      method: "DELETE",
    }),
};
