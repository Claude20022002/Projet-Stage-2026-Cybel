import type {
  DetectedPerson,
  RobotStatus,
  SpeechStatus,
  TourStatus,
  VisitorPublic,
  VoiceKind,
} from "./types";

export type VoiceEvent = {
  transcript: string;
  reply: string;
  kind: VoiceKind;
  ok: boolean;
};

export type TelemetryHandlers = {
  onRobotStatus?: (status: RobotStatus) => void;
  onSpeech?: (speech: SpeechStatus) => void;
  onTourStatus?: (status: TourStatus) => void;
  onPeople?: (people: DetectedPerson[]) => void;
  onVisitorIdentified?: (visitor: VisitorPublic, confidence: number) => void;
  onVoice?: (event: VoiceEvent) => void;
  onConnected?: (connected: boolean) => void;
};

let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let handlers: TelemetryHandlers = {};

function getWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/telemetry`;
}

export function connectKioskTelemetry(next: TelemetryHandlers): void {
  handlers = next;
  if (socket) socket.close();

  socket = new WebSocket(getWsUrl());

  socket.onopen = () => {
    handlers.onConnected?.(true);
  };

  socket.onclose = () => {
    handlers.onConnected?.(false);
    if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(() => connectKioskTelemetry(handlers), 2500);
  };

  socket.onerror = () => {
    handlers.onConnected?.(false);
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data) as Record<string, unknown>;
    const type = data.type as string;
    if (type === "status") {
      handlers.onRobotStatus?.(data as unknown as RobotStatus);
    } else if (type === "speech") {
      handlers.onSpeech?.({
        speaking: Boolean(data.speaking),
        last_text: String(data.last_text ?? ""),
      });
    } else if (type === "tour") {
      handlers.onTourStatus?.(data as unknown as TourStatus);
    } else if (type === "people" && Array.isArray(data.people)) {
      handlers.onPeople?.(data.people as DetectedPerson[]);
    } else if (type === "visitor" && data.visitor) {
      handlers.onVisitorIdentified?.(data.visitor as VisitorPublic, Number(data.confidence ?? 0));
    }
  };
}

export function disconnectKioskTelemetry(): void {
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  socket?.close();
  socket = null;
}
