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
}

export interface Point {
  id: string;
  name: string;
  type: PointType;
  x: number;
  y: number;
  theta: number;
  floor: string;
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

export type AppPage = "dashboard" | "settings";

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
  events: string[];
  wsConnected: boolean;
  voiceListening: boolean;
  speech: SpeechStatus | null;
}
