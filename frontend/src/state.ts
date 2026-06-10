import type {
  AppPage,
  AppState,
  DetectedPerson,
  LidarPoint,
  MapData,
  Point,
  Pose,
  ReceptionAction,
  RobotSettings,
  RobotStatus,
} from "./types";

type Listener = () => void;

const MAX_EVENTS = 8;

export const state: AppState = {
  page: "dashboard",
  status: null,
  pose: null,
  map: null,
  lidar: [],
  people: [],
  actions: [],
  points: [],
  selectedPoint: null,
  settings: null,
  events: [],
  wsConnected: false,
  voiceListening: false,
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

export function setPage(page: AppPage): void {
  state.page = page;
  notify();
}

export function setSettings(settings: RobotSettings): void {
  state.settings = settings;
  notify();
}

export function setLidar(points: LidarPoint[]): void {
  state.lidar = points;
  notify();
}

export function setPeople(people: DetectedPerson[]): void {
  state.people = people;
  notify();
}

export function setActions(actions: ReceptionAction[]): void {
  state.actions = actions;
  notify();
}

export function setVoiceListening(listening: boolean): void {
  state.voiceListening = listening;
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
