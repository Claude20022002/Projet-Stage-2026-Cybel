import { api } from "./api";
import { phaseLabel, t } from "./i18n";
import type { LabTourInfo, Lang, TourScreen, TourStatus } from "./types";

let lang: Lang = "fr";
let screen: TourScreen = "welcome";
let tour: LabTourInfo | null = null;
let status: TourStatus | null = null;
let busy = false;
let message = "";
let pollTimer: number | null = null;
let toastTimer: number | null = null;

function tr() {
  return t[lang];
}

function tourTitle(): string {
  if (!tour) return tr().title;
  return lang === "en" ? tour.title_en : tour.title_fr;
}

function tourSubtitle(): string {
  if (!tour) return tr().subtitle;
  return lang === "en" ? tour.subtitle_en : tour.subtitle_fr;
}

function stopName(stop: { name_fr: string; name_en: string }): string {
  return lang === "en" ? stop.name_en : stop.name_fr;
}

function equipmentName(stop: { equipment_fr: string; equipment_en: string }): string {
  return lang === "en" ? stop.equipment_en : stop.equipment_fr;
}

function showToast(text: string): void {
  message = text;
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    message = "";
    toastTimer = null;
    render();
  }, 3500);
}

function syncScreenFromStatus(): void {
  if (!status) return;
  if (status.state === "running") {
    screen = "running";
    return;
  }
  if (status.state === "completed" || status.state === "stopped" || status.state === "error") {
    if (screen === "running") screen = "completed";
  }
}

function startPolling(): void {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    try {
      status = await api.getTourStatus();
      syncScreenFromStatus();
      render();
    } catch {
      /* ignore transient network errors during tour */
    }
  }, 1500);
}

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="kiosk">
      <header class="kiosk__header">
        <div class="kiosk__brand">
          <span class="kiosk__logo">CYBEL</span>
          <span class="kiosk__title">${tourTitle()}</span>
        </div>
        <button id="btn-lang" class="kiosk__lang" type="button" ${busy ? "disabled" : ""}>
          ${tr().langToggle}
        </button>
      </header>
      ${screen === "welcome" ? renderWelcome() : ""}
      ${screen === "running" ? renderRunning() : ""}
      ${screen === "completed" ? renderCompleted() : ""}
      ${message ? `<div class="kiosk__toast">${message}</div>` : ""}
    </div>
  `;

  bindEvents();
}

function renderWelcome(): string {
  const stops = tour?.stops ?? [];
  return `
    <main class="kiosk__main kiosk__main--welcome">
      <section class="hero">
        <div class="hero__icon" aria-hidden="true">🤖</div>
        <h1 class="hero__title">${tourTitle()}</h1>
        <p class="hero__subtitle">${tourSubtitle()}</p>
        <p class="hero__hint">${tr().idleHint}</p>
        <button id="btn-start" class="btn-primary" type="button" ${busy ? "disabled" : ""}>
          <span class="btn-primary__icon" aria-hidden="true">▶</span>
          ${tr().startTour}
        </button>
      </section>
      ${
        stops.length
          ? `
        <section class="route-preview">
          <h2 class="route-preview__title">${tr().stopsPreview}</h2>
          <ol class="route-preview__list">
            ${stops
              .map(
                (stop, index) => `
              <li class="route-preview__item">
                <span class="route-preview__num">${index + 1}</span>
                <div>
                  <strong>${equipmentName(stop)}</strong>
                  <span>${stopName(stop)}</span>
                </div>
              </li>
            `
              )
              .join("")}
          </ol>
        </section>
      `
          : ""
      }
    </main>
  `;
}

function renderRunning(): string {
  const current = status?.current_index ?? -1;
  const total = status?.total_stops ?? tour?.stops.length ?? 0;
  const progress = total > 0 ? Math.max(0, ((current + 1) / total) * 100) : 0;
  const phase = status?.phase ? phaseLabel(status.phase, lang) : "";
  const equipment = status?.current_equipment || "…";
  const stopNameText = status?.current_stop_name || tr().followRobot;
  const statusMessage = status?.message || tr().tourRunning;

  return `
    <main class="kiosk__main kiosk__main--running">
      <div class="tour-status">
        <div class="tour-status__badge">${tr().tourRunning}</div>
        ${
          total > 0
            ? `
          <p class="tour-status__step">
            ${tr().step} <strong>${Math.max(current + 1, 1)}</strong> ${tr().of} <strong>${total}</strong>
          </p>
          <div class="progress" aria-hidden="true">
            <div class="progress__bar" style="width: ${progress}%"></div>
          </div>
        `
            : ""
        }
      </div>

      <section class="tour-focus">
        ${phase ? `<span class="tour-focus__phase">${phase}</span>` : ""}
        <h2 class="tour-focus__equipment">${equipment}</h2>
        <p class="tour-focus__location">${stopNameText}</p>
        <p class="tour-focus__message">${statusMessage}</p>
        <p class="tour-focus__follow">${tr().followRobot}</p>
      </section>

      <button id="btn-stop" class="btn-danger" type="button" ${busy ? "disabled" : ""}>
        ${tr().stopTour}
      </button>
    </main>
  `;
}

function renderCompleted(): string {
  const state = status?.state;
  let title = tr().tourCompleted;
  let hint = tr().completedHint;
  if (state === "stopped") {
    title = tr().tourStopped;
    hint = tr().stoppedHint;
  } else if (state === "error") {
    title = tr().tourError;
    hint = status?.error || tr().errorHint;
  }

  return `
    <main class="kiosk__main kiosk__main--completed">
      <section class="hero hero--compact">
        <div class="hero__icon" aria-hidden="true">${state === "error" ? "⚠️" : "✅"}</div>
        <h1 class="hero__title">${title}</h1>
        <p class="hero__hint">${hint}</p>
        <button id="btn-restart" class="btn-primary" type="button" ${busy ? "disabled" : ""}>
          ${tr().newTour}
        </button>
      </section>
    </main>
  `;
}

function bindEvents(): void {
  document.getElementById("btn-lang")?.addEventListener("click", () => {
    if (busy) return;
    lang = lang === "fr" ? "en" : "fr";
    render();
  });

  document.getElementById("btn-start")?.addEventListener("click", () => void startTour());
  document.getElementById("btn-restart")?.addEventListener("click", () => {
    screen = "welcome";
    status = null;
    render();
  });
  document.getElementById("btn-stop")?.addEventListener("click", () => void stopTour());
}

async function startTour(): Promise<void> {
  if (busy) return;
  busy = true;
  render();
  try {
    const result = await api.startTour(lang);
    status = result.status ?? (await api.getTourStatus());
    screen = "running";
    startPolling();
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function stopTour(): Promise<void> {
  if (busy) return;
  busy = true;
  render();
  try {
    const result = await api.stopTour();
    status = result.status ?? (await api.getTourStatus());
    stopPolling();
    screen = "completed";
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

export async function initApp(): Promise<void> {
  render();
  try {
    [tour, status] = await Promise.all([api.getTour(), api.getTourStatus()]);
    syncScreenFromStatus();
    if (status?.state === "running") startPolling();
  } catch {
    showToast(t.fr.actionError);
  }
  render();
}
