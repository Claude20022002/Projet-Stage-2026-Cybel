import {
  setLidar,
  setMap,
  setPeople,
  setPoints,
  setPose,
  setStatus,
  setWsConnected,
  pushEvent,
} from "./state";
import type {
  DetectedPerson,
  LidarPoint,
  MapData,
  Point,
  Pose,
  RobotStatus,
} from "./types";

let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;

function getWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/telemetry`;
}

export function connectTelemetry(): void {
  if (socket) socket.close();

  socket = new WebSocket(getWsUrl());

  socket.onopen = () => {
    setWsConnected(true);
    pushEvent("Connexion télémétrie établie");
  };

  socket.onclose = () => {
    setWsConnected(false);
    pushEvent("Télémétrie déconnectée — reconnexion…");
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connectTelemetry, 2000);
  };

  socket.onerror = () => {
    setWsConnected(false);
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data) as Record<string, unknown>;
    const type = data.type as string;

    if (type === "status") {
      setStatus(data as unknown as RobotStatus);
    } else if (type === "pose") {
      setPose(data as unknown as Pose);
    } else if (type === "map" && data.metadata && data.data) {
      setMap(data as unknown as MapData);
    } else if (type === "points" && Array.isArray(data.points)) {
      setPoints(data.points as Point[]);
    } else if (type === "lidar" && Array.isArray(data.points)) {
      setLidar(data.points as LidarPoint[]);
    } else if (type === "people" && Array.isArray(data.people)) {
      setPeople(data.people as DetectedPerson[]);
    } else if (type === "event" && typeof data.message === "string") {
      pushEvent(data.message);
    }
  };
}

export function disconnectTelemetry(): void {
  if (reconnectTimer) window.clearTimeout(reconnectTimer);
  reconnectTimer = null;
  socket?.close();
  socket = null;
}
