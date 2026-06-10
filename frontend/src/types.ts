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

export interface AppState {
  status: RobotStatus | null;
  pose: Pose | null;
  points: Point[];
  selectedPoint: string | null;
  events: string[];
  wsConnected: boolean;
}
