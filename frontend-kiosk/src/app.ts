import { api } from "./api";
import { renderStatusBar } from "./components/statusBar";
import { phaseLabel, t } from "./i18n";
import {
  renderCompleted,
  renderDestinations,
  renderStandby,
  renderTraveling,
  renderWelcome,
} from "./screens/home";
import { connectKioskTelemetry } from "./telemetry";
import type {
  ActiveFlow,
  KioskConfig,
  KioskDestination,
  Lang,
  LabTourInfo,
  ReceptionAction,
  RobotStatus,
  SpeechStatus,
  TourScreen,
  TourStatus,
} from "./types";

let lang: Lang = "fr";
let screen: TourScreen = "welcome";
let activeFlow: ActiveFlow = null;
let tour: LabTourInfo | null = null;
let status: TourStatus | null = null;
let config: KioskConfig | null = null;
let destinations: KioskDestination[] = [];
let featuredDestinations: KioskDestination[] = [];
let receptionActions: ReceptionAction[] = [];
let selectedDestination: string | null = null;
let robotStatus: RobotStatus | null = null;
let speechStatus: SpeechStatus | null = null;
let searchQuery = "";
let busy = false;
let message = "";
let clockTimer: number | null = null;
let standbyTimer: number | null = null;
let toastTimer: number | null = null;
let sawNavigating = false;
let lastInteractionAt = Date.now();

function tr() {
  return t[lang];
}

function resetStandbyTimer(): void {
  lastInteractionAt = Date.now();
  if (standbyTimer !== null) window.clearTimeout(standbyTimer);
  const timeout = (config?.standby_timeout_seconds ?? 90) * 1000;
  if (timeout <= 0 || screen === "running" || screen === "dest_running") return;
  standbyTimer = window.setTimeout(() => {
    if (Date.now() - lastInteractionAt >= timeout - 500) {
      screen = "standby";
      render();
    }
  }, timeout);
}

function showToast(text: string): void {
  message = text;
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    message = "";
    toastTimer = null;
    render();
  }, 4000);
}

function pickReceptionActions(
  all: ReceptionAction[],
  cfg: KioskConfig | null
): ReceptionAction[] {
  const ids = cfg?.reception_actions ?? [];
  const picked = ids
    .map((id) => all.find((a) => a.id === id))
    .filter((a): a is ReceptionAction => Boolean(a));
  if (picked.length) return picked.slice(0, 4);
  return all.filter((a) => a.category === "accueil" && a.id !== "guided_tour").slice(0, 3);
}

function tourSpeechCaption(): string | undefined {
  if (!status || activeFlow !== "tour" || screen !== "running") return undefined;
  if (status.phase === "presenting" || status.phase === "intro" || status.phase === "outro") {
    if (status.message && status.message.length > 12) return status.message;
    if (speechStatus?.speaking && speechStatus.last_text) return speechStatus.last_text;
  }
  if (speechStatus?.speaking && speechStatus.last_text) return speechStatus.last_text;
  return undefined;
}

function pickFeatured(
  all: KioskDestination[],
  cfg: KioskConfig | null
): KioskDestination[] {
  const names = cfg?.featured_destinations ?? [];
  const picked = names
    .map((name) => all.find((d) => d.name === name))
    .filter((d): d is KioskDestination => Boolean(d));
  if (picked.length >= 4) return picked.slice(0, 4);
  const rest = all.filter((d) => !picked.some((p) => p.name === d.name));
  return [...picked, ...rest].slice(0, 4);
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
  if (robotStatus.nav_status === 602) sawNavigating = true;
  if (robotStatus.nav_status === 604) {
    screen = "completed";
    return;
  }
  if (sawNavigating && robotStatus.nav_status === 603) {
    screen = "completed";
  }
}

function startTelemetry(): void {
  connectKioskTelemetry({
    onRobotStatus: (robot) => {
      robotStatus = robot;
      if (activeFlow === "destination") syncScreenFromRobotStatus();
      if (
        screen === "running" ||
        screen === "dest_running" ||
        screen === "welcome" ||
        screen === "standby"
      ) {
        render();
      }
    },
    onSpeech: (speech) => {
      speechStatus = speech;
      if (screen === "running" || screen === "dest_running") render();
    },
    onTourStatus: (tourStatus) => {
      status = tourStatus;
      if (activeFlow === "tour") {
        syncScreenFromTourStatus();
        if (screen === "running" || screen === "completed") render();
      }
    },
  });
}

function startClock(): void {
  if (clockTimer !== null) return;
  clockTimer = window.setInterval(() => {
    const el = document.getElementById("kiosk-clock");
    if (el) {
      el.textContent = new Date().toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-GB", {
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }, 30000);
}

function renderBody(): string {
  switch (screen) {
    case "standby":
      return renderStandby(lang, config);
    case "welcome":
      return renderWelcome(lang, config, tour, featuredDestinations, receptionActions, busy);
    case "destinations":
      return renderDestinations(lang, destinations, searchQuery, busy);
    case "dest_running":
      return renderTraveling(
        lang,
        selectedDestination || tr().destRunning,
        robotStatus?.nav_status_label || tr().destRunning,
        "destination"
      );
    case "running": {
      const current = status?.current_index ?? -1;
      const total = status?.total_stops ?? tour?.stops.length ?? 0;
      const equipment = status?.current_equipment || "…";
      const phase = status?.phase ? phaseLabel(status.phase, lang) : "";
      return renderTraveling(lang, equipment, status?.message || tr().tourRunning, "tour", {
        current,
        total,
        phase,
      }, tourSpeechCaption());
    }
    case "completed":
      if (activeFlow === "destination") {
        return renderCompleted(lang, "destination", robotStatus?.nav_status === 604);
      }
      return renderCompleted(lang, "tour", false, status?.state, status?.error);
    default:
      return renderWelcome(lang, config, tour, featuredDestinations, receptionActions, busy);
  }
}

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="kiosk" data-screen="${screen}">
      ${screen === "standby" ? "" : renderStatusBar(lang, robotStatus, speechStatus, busy)}
      ${renderBody()}
      ${message ? `<div class="kiosk-toast" role="status">${message}</div>` : ""}
    </div>
  `;

  bindEvents();
  resetStandbyTimer();
}

function bindEvents(): void {
  document.getElementById("btn-lang")?.addEventListener("click", () => {
    if (busy) return;
    touch();
    lang = lang === "fr" ? "en" : "fr";
    render();
  });

  document.getElementById("screen-standby")?.addEventListener("click", () => {
    touch();
    screen = "welcome";
    render();
  });

  document.getElementById("btn-mode-tour")?.addEventListener("click", () => void startTour());
  document.getElementById("btn-mode-dest")?.addEventListener("click", () => void openDestinations());
  document.getElementById("btn-assistance")?.addEventListener("click", () => void runAssistance());

  document.getElementById("btn-back-welcome")?.addEventListener("click", () => {
    touch();
    screen = "welcome";
    activeFlow = null;
    searchQuery = "";
    render();
  });

  document.getElementById("dest-search")?.addEventListener("input", (event) => {
    touch();
    searchQuery = (event.target as HTMLInputElement).value;
    render();
    const input = document.getElementById("dest-search") as HTMLInputElement | null;
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = button.dataset.action;
      if (actionId) void runReceptionAction(actionId);
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-dest]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.dest;
      if (name) void goToDestination(name);
    });
  });

  document.getElementById("btn-restart")?.addEventListener("click", () => {
    touch();
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

function touch(): void {
  lastInteractionAt = Date.now();
}

async function openDestinations(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    destinations = await api.getDestinations();
    featuredDestinations = pickFeatured(destinations, config);
    screen = "destinations";
    activeFlow = null;
    searchQuery = "";
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function goToDestination(pointName: string): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  selectedDestination = pointName;
  sawNavigating = false;
  render();
  try {
    await api.goDestination(pointName, lang);
    activeFlow = "destination";
    screen = "dest_running";
    robotStatus = await api.getRobotStatus();
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
  touch();
  busy = true;
  render();
  try {
    const result = await api.startTour(lang);
    status = result.status ?? (await api.getTourStatus());
    activeFlow = "tour";
    screen = "running";
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
  touch();
  busy = true;
  render();
  try {
    if (activeFlow === "destination") {
      await api.haltAll();
      screen = "destinations";
      selectedDestination = null;
      sawNavigating = false;
      showToast(tr().destStopped);
    } else {
      const result = await api.stopTour();
      status = result.status ?? (await api.getTourStatus());
      screen = "completed";
    }
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function runAssistance(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    await api.runAction("inform_waiting", lang);
    showToast(tr().assistanceHint);
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
  } finally {
    busy = false;
    render();
  }
}

async function runReceptionAction(actionId: string): Promise<void> {
  if (busy) return;
  touch();
  if (actionId === "guided_tour") {
    await startTour();
    return;
  }
  if (actionId === "return_charge") {
    busy = true;
    render();
    try {
      await api.goHome();
      showToast(lang === "fr" ? "Retour à la borne lancé" : "Returning to charger");
    } catch (err) {
      const text = err instanceof Error ? err.message : tr().actionError;
      showToast(text);
    } finally {
      busy = false;
      render();
    }
    return;
  }
  busy = true;
  render();
  try {
    const result = await api.runAction(actionId, lang);
    if (result.events?.some((e) => e.includes("Navigation"))) {
      activeFlow = "destination";
      screen = "dest_running";
      selectedDestination = result.events.find((e) => e.includes("vers"))?.split("vers ").pop() ?? null;
      sawNavigating = false;
      robotStatus = await api.getRobotStatus();
    } else {
      showToast(tr().assistanceHint);
    }
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
  } finally {
    busy = false;
    render();
  }
}

export async function initApp(): Promise<void> {
  render();
  startClock();
  startTelemetry();
  try {
    const [tourInfo, tourStatus, dests, actions, kioskConfig, robot, speech] = await Promise.all([
      api.getTour(),
      api.getTourStatus(),
      api.getDestinations(),
      api.getActions(),
      api.getConfig(),
      api.getRobotStatus().catch(() => null),
      api.getSpeechStatus().catch(() => null),
    ]);
    tour = tourInfo;
    status = tourStatus;
    destinations = dests;
    config = kioskConfig;
    featuredDestinations = pickFeatured(destinations, config);
    receptionActions = pickReceptionActions(actions, config);
    robotStatus = robot;
    speechStatus = speech;
    syncScreenFromTourStatus();
    if (status?.state === "running") {
      activeFlow = "tour";
      screen = "running";
    }
  } catch {
    showToast(t.fr.actionError);
  }
  render();
}
