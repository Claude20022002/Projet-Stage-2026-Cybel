import { api } from "./api";
import { phaseLabel, pointIcon, t } from "./i18n";
import type {
  ActiveFlow,
  KioskDestination,
  Lang,
  LabTourInfo,
  RobotStatus,
  TourScreen,
  TourStatus,
} from "./types";

let lang: Lang = "fr";
let screen: TourScreen = "welcome";
let activeFlow: ActiveFlow = null;
let tour: LabTourInfo | null = null;
let status: TourStatus | null = null;
let destinations: KioskDestination[] = [];
let selectedDestination: string | null = null;
let robotStatus: RobotStatus | null = null;
let busy = false;
let message = "";
let pollTimer: number | null = null;
let toastTimer: number | null = null;
let sawNavigating = false;

function tr() {
  return t[lang];
}

function headerTitle(): string {
  if (screen === "destinations" || screen === "dest_running") {
    return tr().destinationsTitle;
  }
  return tourTitle();
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

function syncScreenFromTourStatus(): void {
  if (!status || activeFlow !== "tour") return;
  if (status.state === "running") {
    screen = "running";
    return;
  }
  if (status.state === "completed" || status.state === "stopped" || status.state === "error") {
    if (screen === "running") screen = "completed";
  }
}

function syncScreenFromRobotStatus(): void {
  if (!robotStatus || activeFlow !== "destination" || screen !== "dest_running") return;
  if (robotStatus.nav_status === 602) {
    sawNavigating = true;
  }
  if (robotStatus.nav_status === 604) {
    stopPolling();
    screen = "completed";
    return;
  }
  if (sawNavigating && robotStatus.nav_status === 603) {
    stopPolling();
    screen = "completed";
  }
}

function startPolling(): void {
  stopPolling();
  pollTimer = window.setInterval(async () => {
    try {
      if (activeFlow === "tour") {
        status = await api.getTourStatus();
        syncScreenFromTourStatus();
        if (status.state !== "running") stopPolling();
      } else if (activeFlow === "destination") {
        robotStatus = await api.getRobotStatus();
        syncScreenFromRobotStatus();
        if (screen !== "dest_running") stopPolling();
      }
      render();
    } catch {
      /* ignore transient network errors */
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
          <span class="kiosk__title">${headerTitle()}</span>
        </div>
        <button id="btn-lang" class="kiosk__lang" type="button" ${busy ? "disabled" : ""}>
          ${tr().langToggle}
        </button>
      </header>
      ${screen === "welcome" ? renderWelcome() : ""}
      ${screen === "destinations" ? renderDestinations() : ""}
      ${screen === "dest_running" ? renderDestRunning() : ""}
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
        <p class="hero__hint">${tr().chooseMode}</p>
      </section>

      <section class="mode-picker">
        <button id="btn-mode-tour" class="mode-card" type="button" ${busy ? "disabled" : ""}>
          <span class="mode-card__icon" aria-hidden="true">🗺️</span>
          <strong class="mode-card__title">${tr().modeTour}</strong>
          <span class="mode-card__hint">${tr().modeTourHint}</span>
        </button>
        <button id="btn-mode-dest" class="mode-card" type="button" ${busy ? "disabled" : ""}>
          <span class="mode-card__icon" aria-hidden="true">📍</span>
          <strong class="mode-card__title">${tr().modeDestinations}</strong>
          <span class="mode-card__hint">${tr().modeDestinationsHint}</span>
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

function renderDestinations(): string {
  if (!destinations.length) {
    return `
      <main class="kiosk__main kiosk__main--destinations">
        <section class="hero hero--compact">
          <p class="hero__hint">${tr().actionError}</p>
          <button id="btn-back-welcome" class="btn-secondary" type="button">${tr().back}</button>
        </section>
      </main>
    `;
  }

  return `
    <main class="kiosk__main kiosk__main--destinations">
      <p class="destinations__hint">${tr().destinationsHint}</p>
      <div class="destinations-grid">
        ${destinations
          .map(
            (dest) => `
          <button
            class="dest-card"
            type="button"
            data-dest="${dest.name}"
            ${busy ? "disabled" : ""}
          >
            <span class="dest-card__icon" aria-hidden="true">${pointIcon(dest.type)}</span>
            <span class="dest-card__name">${dest.name}</span>
          </button>
        `
          )
          .join("")}
      </div>
      <button id="btn-back-welcome" class="btn-secondary" type="button" ${busy ? "disabled" : ""}>
        ${tr().back}
      </button>
    </main>
  `;
}

function renderDestRunning(): string {
  const label = selectedDestination || tr().destRunning;
  const statusLabel = robotStatus?.nav_status_label || tr().destRunning;

  return `
    <main class="kiosk__main kiosk__main--running">
      <div class="tour-status">
        <div class="tour-status__badge">${tr().destRunning}</div>
        <p class="tour-status__step">${statusLabel}</p>
      </div>

      <section class="tour-focus">
        <h2 class="tour-focus__equipment">${label}</h2>
        <p class="tour-focus__follow">${tr().destFollow}</p>
      </section>
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
  if (activeFlow === "destination") {
    const failed = robotStatus?.nav_status === 604;
    return `
      <main class="kiosk__main kiosk__main--completed">
        <section class="hero hero--compact">
          <div class="hero__icon" aria-hidden="true">${failed ? "⚠️" : "✅"}</div>
          <h1 class="hero__title">${failed ? tr().destError : tr().destCompleted}</h1>
          <p class="hero__hint">${failed ? tr().destErrorHint : tr().destCompletedHint}</p>
          <button id="btn-restart" class="btn-primary" type="button" ${busy ? "disabled" : ""}>
            ${tr().newDestination}
          </button>
        </section>
      </main>
    `;
  }

  const state = status?.state;
  let title: string = tr().tourCompleted;
  let hint: string = tr().completedHint;
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

  document.getElementById("btn-mode-tour")?.addEventListener("click", () => void startTour());
  document.getElementById("btn-mode-dest")?.addEventListener("click", () => void openDestinations());
  document.getElementById("btn-back-welcome")?.addEventListener("click", () => {
    screen = "welcome";
    activeFlow = null;
    render();
  });

  document.querySelectorAll<HTMLButtonElement>("[data-dest]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.dest;
      if (name) void goToDestination(name);
    });
  });

  document.getElementById("btn-restart")?.addEventListener("click", () => {
    if (activeFlow === "destination") {
      screen = "destinations";
      selectedDestination = null;
      robotStatus = null;
      sawNavigating = false;
    } else {
      screen = "welcome";
      status = null;
      activeFlow = null;
    }
    render();
  });
  document.getElementById("btn-stop")?.addEventListener("click", () => void stopTour());
}

async function openDestinations(): Promise<void> {
  if (busy) return;
  busy = true;
  render();
  try {
    destinations = await api.getDestinations();
    screen = "destinations";
    activeFlow = null;
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function goToDestination(pointName: string): Promise<void> {
  if (busy) return;
  busy = true;
  selectedDestination = pointName;
  sawNavigating = false;
  render();
  try {
    await api.goDestination(pointName, lang);
    activeFlow = "destination";
    screen = "dest_running";
    robotStatus = await api.getRobotStatus();
    startPolling();
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
    screen = "destinations";
    selectedDestination = null;
  } finally {
    busy = false;
    render();
  }
}

async function startTour(): Promise<void> {
  if (busy) return;
  busy = true;
  render();
  try {
    const result = await api.startTour(lang);
    status = result.status ?? (await api.getTourStatus());
    activeFlow = "tour";
    screen = "running";
    startPolling();
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
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
    [tour, status, destinations] = await Promise.all([
      api.getTour(),
      api.getTourStatus(),
      api.getDestinations(),
    ]);
    syncScreenFromTourStatus();
    if (status?.state === "running") {
      activeFlow = "tour";
      startPolling();
    }
  } catch {
    showToast(t.fr.actionError);
  }
  render();
}
