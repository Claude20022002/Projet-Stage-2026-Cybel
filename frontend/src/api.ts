import type {
  MapData,
  Point,
  Pose,
  ReceptionAction,
  RobotSettings,
  RobotStatus,
} from "./types";

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
  navigateTo: (pointName: string) =>
    request("/api/navigation/goto", {
      method: "POST",
      body: JSON.stringify({ point_name: pointName }),
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
};
