import type { AppState, MapData, Point, Pose, RobotStatus } from "./types";

type Listener = () => void;

const MAX_EVENTS = 8;

export const state: AppState = {
  status: null,
  pose: null,
  map: null,
  points: [],
  selectedPoint: null,
  events: [],
  wsConnected: false,
};

const listeners = new Set<Listener>();

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function notify(): void {
  listeners.forEach((listener) => listener());
}

export function setStatus(status: RobotStatus): void {
  state.status = status;
  notify();
}

export function setPose(pose: Pose): void {
  state.pose = pose;
  notify();
}

export function setMap(map: MapData): void {
  state.map = map;
  notify();
}

export function setPoints(points: Point[]): void {
  state.points = points;
  notify();
}

export function setSelectedPoint(name: string | null): void {
  state.selectedPoint = name;
  notify();
}

export function setWsConnected(connected: boolean): void {
  state.wsConnected = connected;
  notify();
}

export function pushEvent(message: string): void {
  const time = new Date().toLocaleTimeString("fr-FR");
  state.events = [`${time} — ${message}`, ...state.events].slice(0, MAX_EVENTS);
  notify();
}
