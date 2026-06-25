import { formatClock, t } from "../i18n";
import type { Lang, RobotStatus, SpeechStatus } from "../types";

export function renderStatusBar(
  lang: Lang,
  robot: RobotStatus | null,
  speech: SpeechStatus | null,
  busy: boolean
): string {
  const labels = t[lang];
  const connected = robot?.connected ?? false;
  const battery = robot?.battery ?? 0;
  const charging = robot?.charger ?? false;
  const speaking = speech?.speaking ?? false;
  const estop = robot?.soft_estop ?? false;

  let statusLabel: string = labels.statusOffline;
  let statusClass = "status-pill--offline";
  if (estop) {
    statusLabel = labels.statusEstop;
    statusClass = "status-pill--danger";
  } else if (!connected) {
    statusLabel = labels.statusOffline;
    statusClass = "status-pill--offline";
  } else if (speaking) {
    statusLabel = labels.statusSpeaking;
    statusClass = "status-pill--speak";
  } else if (robot?.nav_status === 602) {
    statusLabel = labels.statusNavigating;
    statusClass = "status-pill--nav";
  } else if (robot?.nav_status === 601 || robot?.nav_status === 603) {
    statusLabel = labels.statusReady;
    statusClass = "status-pill--ok";
  } else {
    statusLabel = robot?.nav_status_label || labels.statusReady;
    statusClass = "status-pill--warn";
  }

  const batteryClass =
    battery <= 20 ? "battery--low" : battery <= 50 ? "battery--mid" : "battery--ok";

  return `
    <header class="kiosk-header">
      <div class="kiosk-header__left">
        <span class="status-pill ${statusClass}">${statusLabel}</span>
        <span class="status-net ${connected ? "status-net--on" : "status-net--off"}" title="${connected ? labels.statusConnected : labels.statusOffline}"></span>
      </div>
      <div class="kiosk-header__center">
        <time class="kiosk-clock" id="kiosk-clock">${formatClock(new Date(), lang)}</time>
      </div>
      <div class="kiosk-header__right">
        <div class="battery ${batteryClass}" aria-label="${labels.statusBattery} ${battery}%">
          ${charging ? `<span class="battery__charge">${labels.statusCharging}</span>` : ""}
          <span class="battery__icon" aria-hidden="true">⚡</span>
          <span class="battery__value">${battery}%</span>
        </div>
        <button id="btn-lang" class="kiosk-lang" type="button" ${busy ? "disabled" : ""}>
          ${labels.langToggle}
        </button>
      </div>
    </header>
  `;
}
