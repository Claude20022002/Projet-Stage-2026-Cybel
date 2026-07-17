export type Lang = "fr" | "en";

export type TourScreen =
  | "standby"
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

export interface DetectedPerson {
  id: string;
  x: number;
  y: number;
  distance: number;
}

export interface VisitorPublic {
  id: string;
  name: string;
  civility: "M." | "Mme" | "";
  consent: boolean;
  enrolled_at: string;
  last_identified_at: string | null;
}

export type VoiceKind =
  | "action"
  | "navigation"
  | "faq"
  | "faq+navigation"
  | "unknown"
  | "empty";

export interface VoiceResult {
  ok: boolean;
  understood: boolean;
  kind: VoiceKind;
  transcript: string;
  reply: string;
  action?: string | null;
  point?: string | null;
  error?: string | null;
}

export type VoiceState = "idle" | "listening" | "processing" | "answer";

export interface KioskConfig {
  organization_name_fr: string;
  organization_name_en: string;
  welcome_message_fr: string;
  welcome_message_en: string;
  logo_url: string;
  standby_timeout_seconds: number;
  featured_destinations: string[];
  reception_actions?: string[];
  kiosk_variant?: string;
  kiosk_variant_label_fr?: string;
  kiosk_variant_label_en?: string;
  presence_welcome_enabled?: boolean;
  presence_max_distance_m?: number;
  presence_cooldown_seconds?: number;
  presence_speak_welcome?: boolean;
  face_recognition_enabled?: boolean;
  face_recognition_threshold?: number;
}

export interface ReceptionAction {
  id: string;
  label: string;
  label_en?: string;
  description: string;
  icon: string;
  category: string;
}

export interface RobotStatus {
  connected: boolean;
  battery: number;
  charger: boolean;
  soft_estop: boolean;
  nav_status: number;
  nav_status_label: string;
  nav_mode_label: string;
  localization_percent: number;
  localization_label: string;
  navigating_to: string | null;
}

export interface SpeechStatus {
  speaking: boolean;
  last_text: string;
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

export interface AppState {
  lang: Lang;
  screen: TourScreen;
  activeFlow: ActiveFlow;
  tour: LabTourInfo | null;
  status: TourStatus | null;
  destinations: KioskDestination[];
  featuredDestinations: KioskDestination[];
  selectedDestination: string | null;
  robotStatus: RobotStatus | null;
  speech: SpeechStatus | null;
  config: KioskConfig | null;
  searchQuery: string;
  busy: boolean;
  message: string;
}
