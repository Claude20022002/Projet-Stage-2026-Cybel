import { icons } from "../icons";
import type { RobotStatus, SpeechStatus } from "../types";

function localizationClass(percent: number): string {
  if (percent < 60) return "loc-low";
  if (percent < 80) return "loc-mid";
  return "loc-good";
}

function batteryClass(level: number): string {
  if (level <= 20) return "battery-low";
  if (level <= 50) return "battery-mid";
  return "battery-good";
}

export function renderStatusBar(
  status: RobotStatus | null,
  wsConnected: boolean,
  speech: SpeechStatus | null = null
): string {
  if (!status) {
    return `
      <header class="status-bar">
        <div class="status-bar__left">
          <span class="brand">CYBEL</span>
          <span class="badge badge--loading">Chargement…</span>
        </div>
      </header>
    `;
  }

  const locClass = localizationClass(status.localization_percent);
  const batClass = batteryClass(status.battery);

  return `
    <header class="status-bar">
      <div class="status-bar__left">
        <span class="chassis-id">${status.chassis_id}</span>
        ${
          status.mock
            ? '<span class="badge badge--mock">Mode simulation</span>'
            : ""
        }
        <span class="badge badge--with-icon ${wsConnected ? "badge--ok" : "badge--warn"}">
          ${wsConnected ? icons.wifi("icon icon--badge", 14) : icons.wifiOff("icon icon--badge", 14)}
          <span>${wsConnected ? "Connecté" : "Déconnecté"}</span>
        </span>
      </div>
      <div class="status-bar__center">
        <div class="metric">
          <span class="metric__label">État</span>
          <span class="metric__value">${status.nav_status_label}</span>
        </div>
        <div class="metric">
          <span class="metric__label">Mode</span>
          <span class="metric__value">${status.nav_mode_label}</span>
        </div>
        <div class="metric">
          <span class="metric__label">Localisation</span>
          <span class="metric__value ${locClass}">
            ${status.localization_label} (${status.localization_percent.toFixed(0)}%)
          </span>
        </div>
        ${
          status.navigating_to
            ? `<div class="metric">
                <span class="metric__label">Destination</span>
                <span class="metric__value metric__value--active">${status.navigating_to}</span>
              </div>`
            : ""
        }
      </div>
      <div class="status-bar__right">
        <div class="battery ${batClass}">
          ${icons.battery("icon icon--battery", 18)}
          <span class="battery__level">${status.battery}%</span>
        </div>
        ${
          status.charger
            ? `<span class="badge badge--charge badge--with-icon">${icons.plug("icon icon--badge", 14)}<span>En charge</span></span>`
            : ""
        }
        ${
          speech?.speaking
            ? `<span class="badge badge--speaking badge--with-icon">${icons.volume("icon icon--badge", 14)}<span>Parle</span></span>`
            : ""
        }
        ${
          status.soft_estop
            ? `<span class="badge badge--danger badge--with-icon">${icons.alertTriangle("icon icon--badge", 14)}<span>E-STOP ACTIF</span></span>`
            : ""
        }
      </div>
    </header>
  `;
}
