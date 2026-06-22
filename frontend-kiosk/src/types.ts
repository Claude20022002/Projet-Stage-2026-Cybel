export type Lang = "fr" | "en";

export type TourScreen = "welcome" | "running" | "completed";

export type TourState = "idle" | "running" | "completed" | "stopped" | "error";

export type TourPhase = "" | "intro" | "navigating" | "presenting" | "dwell" | "outro";

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
