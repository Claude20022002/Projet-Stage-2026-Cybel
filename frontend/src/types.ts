export type PointType =
  | "charging"
  | "common"
  | "gate"
  | "access"
  | "ride"
  | "wait"
  | "label"
  | "stop";

export interface Pose {
  x: number;
  y: number;
  theta: number;
}

export interface RobotStatus {
  connected: boolean;
  mock: boolean;
  chassis_id: string;
  battery: number;
  charger: boolean;
  soft_estop: boolean;
  hard_estop: boolean;
  nav_status: number;
  nav_status_label: string;
  control_state: number;
  nav_mode: string;
  nav_mode_label: string;
  localization_percent: number;
  localization_label: string;
  velocity: [number, number];
  current_building_name: string;
  current_floor_name: string;
  current_goal: Pose | null;
  navigating_to: string | null;
  returning_to_charge: boolean;
  charge_state: string;
  charge_state_label: string;
}

export interface Point {
  id: string;
  name: string;
  type: PointType;
  x: number;
  y: number;
  theta: number;
  floor: string;
  kiosk_visible?: boolean;
  source?: "ros" | "local" | "merged";
}

export interface MapMetadata {
  name: string;
  floor: string;
  width: number;
  height: number;
  resolution: number;
  origin_x: number;
  origin_y: number;
  area_sqm: number | null;
}

export interface MapData {
  metadata: MapMetadata;
  data: number[];
}

export interface RobotSettings {
  speed_gear: "low" | "medium" | "high";
  travel_mode: "safety" | "balance" | "efficiency";
  directional_mode: "arrows" | "joystick";
  robot_host: string;
  mock_mode: boolean;
}

export interface LidarPoint {
  x: number;
  y: number;
  distance: number;
}

export interface DetectedPerson {
  id: string;
  x: number;
  y: number;
  distance: number;
}

export interface ReceptionAction {
  id: string;
  label: string;
  description: string;
  icon: string;
  category: "accueil" | "navigation" | "maintenance" | "sécurité";
  speech?: string | null;
  target_point?: string | null;
  route_name?: string | null;
}

export interface SpeechStatus {
  speaking: boolean;
  last_text: string;
  last_method: string;
  mock: boolean;
}

export type AppPage = "dashboard" | "tour" | "patrol" | "settings" | "visitors";

export interface VisitorPublic {
  id: string;
  name: string;
  civility: string;
  consent: boolean;
  enrolled_at: string;
  last_identified_at: string | null;
}

/** Statut de détection faciale en direct (jamais d'image, uniquement le
 * résultat du matching) — diffusé par le backend embarqué du kiosque à
 * chaque frame où un visage est vu (correspondance ou non). */
export interface FaceStatusEvent {
  detected: boolean;
  matched: boolean;
  confidence: number;
  visitor?: VisitorPublic;
}

export interface TourStopData {
  id: string;
  name_fr: string;
  name_en?: string;
  equipment_fr: string;
  equipment_en?: string;
  speech_fr: string;
  speech_en?: string;
  target_point?: string;
  x?: number;
  y?: number;
  theta?: number;
  approach_speech_fr?: string;
  approach_speech_en?: string;
  dwell_seconds?: number;
}

export interface LabTourData {
  id: string;
  title_fr: string;
  title_en: string;
  subtitle_fr?: string;
  subtitle_en?: string;
  intro_speech_fr?: string;
  intro_speech_en?: string;
  outro_speech_fr?: string;
  outro_speech_en?: string;
  stops: TourStopData[];
}

export type TourState = "idle" | "running" | "completed" | "stopped" | "error";

export interface TourStatus {
  state: TourState;
  lang: string;
  current_index: number;
  total_stops: number;
  current_stop_id: string | null;
  current_stop_name: string;
  current_equipment: string;
  phase: string;
  message: string;
  error: string | null;
}

export type PatrolMode = "cycle" | "round_trip" | "random";
export type PatrolState = "idle" | "running" | "stopped" | "error";

export interface PatrolStopData {
  id: string;
  name: string;
  name_en?: string;
  speech_fr?: string;
  speech_en?: string;
  target_point?: string;
  x?: number;
  y?: number;
  theta?: number;
  dwell_seconds?: number;
}

export interface PatrolTaskData {
  id: string;
  name: string;
  mode: PatrolMode;
  intro_speech_fr?: string;
  intro_speech_en?: string;
  stops: PatrolStopData[];
}

export interface PatrolStatus {
  state: PatrolState;
  task_id: string | null;
  task_name: string;
  mode: PatrolMode;
  lang: string;
  current_index: number;
  total_stops: number;
  cycle_count: number;
  current_stop_id: string | null;
  current_stop_name: string;
  phase: string;
  message: string;
  error: string | null;
}

export interface DiagnosticsSnapshot {
  mock: boolean;
  overall_ok: boolean;
  rosbridge: { ok: boolean; connected?: boolean; host?: string; last_message_age_s?: number | null; stale?: boolean };
  mqtt: { ok: boolean; enabled?: boolean; active?: boolean };
  adb_tts: { ok: boolean; configured_serial?: string; last_connect_ok?: boolean; queue_size?: number };
  persistence: { ok: boolean; backend: string; data_dir: string };
}

export interface AppState {
  page: AppPage;
  status: RobotStatus | null;
  pose: Pose | null;
  map: MapData | null;
  lidar: LidarPoint[];
  people: DetectedPerson[];
  actions: ReceptionAction[];
  points: Point[];
  selectedPoint: string | null;
  settings: RobotSettings | null;
  tour: LabTourData | null;
  tourStatus: TourStatus | null;
  tourEditingStopId: string | null;
  patrolTasks: PatrolTaskData[];
  selectedPatrolTaskId: string | null;
  patrolStatus: PatrolStatus | null;
  patrolEditingStopId: string | null;
  events: string[];
  wsConnected: boolean;
  voiceListening: boolean;
  speech: SpeechStatus | null;
  visitors: VisitorPublic[];
  faceStatus: FaceStatusEvent | null;
  faceStatusAt: number | null;
}
