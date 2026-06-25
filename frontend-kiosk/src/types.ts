export type Lang = "fr" | "en";

export type TourScreen =
  | "welcome"
  | "destinations"
  | "dest_running"
  | "running"
  | "completed";

export type ActiveFlow = "tour" | "destination" | null;

export type TourState = "idle" | "running" | "completed" | "stopped" | "error";

export type TourPhase = "" | "intro" | "navigating" | "presenting" | "dwell" | "outro";

export type PointType =
  | "charging"
  | "common"
  | "gate"
  | "access"
  | "ride"
  | "wait"
  | "label"
  | "stop";

export interface KioskDestination {
  id: string;
  name: string;
  type: PointType;
  x: number;
  y: number;
  theta?: number;
}

export interface RobotStatus {
  connected: boolean;
  nav_status: number;
  nav_status_label: string;
  navigating_to: string | null;
}

export interface TourStopPreview {
  id: string;
  name_fr: string;
  name_en: string;
  equipment_fr: string;
  equipment_en: string;
  target_point?: string;
  x?: number;
  y?: number;
  theta?: number;
}

export interface LabTourInfo {
  id: string;
  title_fr: string;
  title_en: string;
  subtitle_fr: string;
  subtitle_en: string;
  stops: TourStopPreview[];
}

export interface TourStatus {
  state: TourState;
  lang: string;
  current_index: number;
  total_stops: number;
  current_stop_id: string | null;
  current_stop_name: string;
  current_equipment: string;
  phase: TourPhase;
  message: string;
  error: string | null;
}
