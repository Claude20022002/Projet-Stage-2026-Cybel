import { api } from "./api";
import { renderControls, renderEventsLog } from "./components/controls";
import { renderLayout } from "./components/layout";
import { computeScaleMetersPerPixel, drawMap, renderMapCanvas } from "./components/mapView";
import { renderMapInfoCard } from "./components/legend";
import { renderPointsList } from "./components/pointsList";
import { renderReceptionPanel } from "./components/receptionPanel";
import { renderRobotCard, renderStatusBar } from "./components/statusBar";
import { toggleVoiceListening } from "./voice";
import { bindSettingsEvents, renderSettingsPage } from "./pages/settings";
import { connectTelemetry } from "./telemetry";
import {
  state,
  subscribe,
  setActions,
  setMap,
  setPage,
  setPoints,
  setSelectedPoint,
  setSettings,
  pushEvent,
} from "./state";

const MOVE_SPEED = 0.2;
const ROTATE_SPEED = 0.5;
let moveInterval: number | null = null;
let controlsBound = false;
let lastPointsKey = "";
let lastSelectedPoint: string | null = null;
let lastMapKey = "";
let lastPage = state.page;
let lastVoiceListening = false;
let lastSpeechSpeaking = false;
let lastPeopleCount = 0;
let pingStartedAt: number | null = null;
let pingRaf: number | null = null;

function renderDashboardContent(): string {
  const manualMode = state.status?.nav_mode === "manual";
  const softEstop = state.status?.soft_estop ?? false;

  return `
    <div class="dashboard">
      <div id="status-bar-container">${renderStatusBar(state.status, state.wsConnected, state.speech, state.people.length, state.pose)}</div>
      <main class="dashboard__main">
        <div class="dashboard__left">
          <div id="robot-card-container">${renderRobotCard(state.status, state.wsConnected)}</div>
          <div id="points-panel-container">${renderPointsList(state.points, state.selectedPoint)}</div>
          <div id="legend-card-container">${renderMapInfoCard(state.map)}</div>
          <div id="reception-panel-container">${renderReceptionPanel(state.actions, state.voiceListening, state.speech)}</div>
        </div>
        <div id="map-panel-container">${renderMapCanvas(state.map, softEstop)}</div>
        <div id="controls-panel-container">${renderControls(manualMode, softEstop)}</div>
      </main>
    </div>
  `;
}

function renderApp(): void {
  const app = document.getElementById("app");
  if (!app) return;

  const content =
    state.page === "settings"
      ? renderSettingsPage(state.settings)
      : renderDashboardContent();

  app.innerHTML = renderLayout(state.page, content);
  lastPage = state.page;
  controlsBound = false;

  bindLayoutEvents();
  if (state.page === "dashboard") {
    bindPointEvents();
    bindReceptionEvents();
    bindControlEvents();
    bindMapToolbarEvents();
    updateMapCanvas();
  } else {
    bindSettingsEvents(() => api.getSettings().then(setSettings).catch(() => {}));
  }
}

function bindLayoutEvents(): void {
  document.querySelectorAll("[data-page]").forEach((el) => {
    el.addEventListener("click", () => {
      const page = (el as HTMLElement).dataset.page as "dashboard" | "settings";
      if (page && page !== state.page) setPage(page);
    });
  });
}

function updateStatusBar(): void {
  const el = document.getElementById("status-bar-container");
  if (el) el.innerHTML = renderStatusBar(state.status, state.wsConnected, state.speech, state.people.length);
}

function updatePointsPanel(force = false): void {
  if (state.page !== "dashboard") return;

  const pointsKey = state.points.map((p) => p.id).join(",");
  const selectionChanged = state.selectedPoint !== lastSelectedPoint;
  const pointsChanged = pointsKey !== lastPointsKey;

  if (!force && !pointsChanged && !selectionChanged) {
    document.querySelectorAll("[data-point]").forEach((el) => {
      const name = (el as HTMLElement).dataset.point;
      el.classList.toggle("point-item--selected", name === state.selectedPoint);
    });
    const navigateBtn = document.getElementById("btn-navigate");
    const label = navigateBtn?.querySelector("span:last-child");
    if (label) label.textContent = `Aller vers ${state.selectedPoint ?? "…"}`;
    if (navigateBtn) (navigateBtn as HTMLButtonElement).disabled = !state.selectedPoint;
    return;
  }

  lastPointsKey = pointsKey;
  lastSelectedPoint = state.selectedPoint;

  const el = document.getElementById("points-panel-container");
  if (el) {
    el.innerHTML = renderPointsList(state.points, state.selectedPoint);
    bindPointEvents();
  }
}

function updateMapPanel(force = false): void {
  if (state.page !== "dashboard") return;

  const mapKey = state.map
    ? `${state.map.metadata.name}-${state.map.metadata.width}`
    : "";
  if (force || (mapKey && mapKey !== lastMapKey)) {
    lastMapKey = mapKey;
    const el = document.getElementById("map-panel-container");
    if (el) el.innerHTML = renderMapCanvas(state.map);
  }
  updateMapCanvas();
}

function updateMapCanvas(): void {
  const canvas = document.getElementById("map-canvas") as HTMLCanvasElement | null;
  if (canvas) {
    drawMap(
      canvas,
      state.pose,
      state.points,
      state.selectedPoint,
      state.status?.current_goal ?? null,
      state.map,
      state.lidar,
      state.people
    );
  }
}

function updateReceptionPanel(): void {
  if (state.page !== "dashboard") return;
  const el = document.getElementById("reception-panel-container");
  if (el) {
    el.innerHTML = renderReceptionPanel(state.actions, state.voiceListening, state.speech);
    bindReceptionEvents();
  }
}

function bindReceptionEvents(): void {
  document.getElementById("btn-voice")?.addEventListener("click", () => {
    toggleVoiceListening();
  });

  document.getElementById("btn-speak")?.addEventListener("click", async () => {
    const input = document.getElementById("speech-text") as HTMLTextAreaElement | null;
    const text = input?.value.trim();
    if (!text) return;
    try {
      await api.speak(text);
    } catch (err) {
      pushEvent(`TTS : ${(err as Error).message}`);
    }
  });

  document.getElementById("btn-stop-speech")?.addEventListener("click", async () => {
    try {
      await api.stopSpeech();
      pushEvent("Synthèse vocale interrompue");
    } catch (err) {
      pushEvent(`Erreur : ${(err as Error).message}`);
    }
  });

  document.querySelectorAll("[data-action]").forEach((el) => {
    el.addEventListener("click", async () => {
      const actionId = (el as HTMLElement).dataset.action;
      if (!actionId) return;
      try {
        const result = await api.executeAction(actionId);
        result.events?.forEach((e) => pushEvent(e));
      } catch (err) {
        pushEvent(`Erreur action : ${(err as Error).message}`);
      }
    });
  });
}

function updateControls(): void {
  if (state.page !== "dashboard") return;
  const el = document.getElementById("controls-panel-container");
  if (!el) return;

  const manualMode = state.status?.nav_mode === "manual";
  const softEstop = state.status?.soft_estop ?? false;
  el.innerHTML = renderControls(manualMode, softEstop);
  controlsBound = false;
  bindControlEvents();
}

function updateEventsLog(): void {
  const el = document.getElementById("events-log");
  if (el) el.innerHTML = renderEventsLog(state.events);
}

function bindPointEvents(): void {
  document.querySelectorAll("[data-point]").forEach((el) => {
    el.addEventListener("click", () => {
      setSelectedPoint((el as HTMLElement).dataset.point ?? null);
    });
  });

  document.getElementById("btn-navigate")?.addEventListener("click", async () => {
    if (!state.selectedPoint) return;
    try {
      await api.navigateTo(state.selectedPoint);
    } catch (err) {
      pushEvent(`Erreur navigation : ${(err as Error).message}`);
    }
  });

  document.getElementById("btn-cancel-nav")?.addEventListener("click", async () => {
    try {
      await api.cancelNavigation();
    } catch (err) {
      pushEvent(`Erreur : ${(err as Error).message}`);
    }
  });
}

function bindControlEvents(): void {
  if (controlsBound) return;
  controlsBound = true;

  document.getElementById("toggle-manual")?.addEventListener("change", async (e) => {
    const enabled = (e.target as HTMLInputElement).checked;
    try {
      await api.setManualMode(enabled);
    } catch (err) {
      pushEvent(`Erreur mode manuel : ${(err as Error).message}`);
    }
  });

  document.getElementById("btn-stop")?.addEventListener("click", () => {
    stopMoveLoop();
    api.stop().catch((err) => pushEvent(`Erreur : ${err.message}`));
  });

  document.getElementById("btn-estop")?.addEventListener("click", () => {
    stopMoveLoop();
    api.emergencyStop().catch((err) => pushEvent(`Erreur : ${err.message}`));
  });

  document.getElementById("btn-release-estop")?.addEventListener("click", () => {
    api.releaseEmergencyStop().catch((err) => pushEvent(`Erreur : ${err.message}`));
  });

  document.querySelectorAll("[data-move]").forEach((el) => {
    const direction = (el as HTMLElement).dataset.move!;

    const start = () => {
      if (state.status?.nav_mode !== "manual") return;
      stopMoveLoop();
      const cmd = getMoveCommand(direction);
      if (!cmd) return;
      api.move(cmd).catch(() => {});
      moveInterval = window.setInterval(() => {
        api.move(cmd).catch(() => {});
      }, 100);
    };

    const stop = () => {
      if (moveInterval) {
        stopMoveLoop();
        api.move({ linear_x: 0, angular_z: 0 }).catch(() => {});
      }
    };

    el.addEventListener("mousedown", start);
    el.addEventListener("mouseup", stop);
    el.addEventListener("mouseleave", stop);
    el.addEventListener("touchstart", (e) => {
      e.preventDefault();
      start();
    });
    el.addEventListener("touchend", stop);
  });
}

function getMoveCommand(direction: string) {
  switch (direction) {
    case "forward":
      return { linear_x: MOVE_SPEED, angular_z: 0 };
    case "backward":
      return { linear_x: -MOVE_SPEED, angular_z: 0 };
    case "left":
      return { linear_x: 0, angular_z: ROTATE_SPEED };
    case "right":
      return { linear_x: 0, angular_z: -ROTATE_SPEED };
    default:
      return null;
  }
}

function stopMoveLoop(): void {
  if (moveInterval) {
    window.clearInterval(moveInterval);
    moveInterval = null;
  }
}

function onStateChange(): void {
  if (state.page !== lastPage) {
    renderApp();
    return;
  }

  if (state.page === "dashboard") {
    updateStatusBar();
    updatePointsPanel();
    if (
      state.voiceListening !== lastVoiceListening ||
      (state.speech?.speaking ?? false) !== lastSpeechSpeaking
    ) {
      lastVoiceListening = state.voiceListening;
      lastSpeechSpeaking = state.speech?.speaking ?? false;
      updateReceptionPanel();
      updateStatusBar();
    }
    if (state.people.length !== lastPeopleCount) {
      lastPeopleCount = state.people.length;
      updateStatusBar();
    }
    updateMapPanel();
    updateMapCanvas();
    updateEventsLog();

    const prevManual = document.getElementById("toggle-manual") as HTMLInputElement | null;
    const newManual = state.status?.nav_mode === "manual";
    const newEstop = state.status?.soft_estop ?? false;
    const container = document.getElementById("controls-panel-container");
    if (container) {
      const needsRerender =
        !prevManual ||
        prevManual.checked !== newManual ||
        Boolean(document.getElementById("btn-estop")) === newEstop ||
        Boolean(document.getElementById("btn-release-estop")) !== newEstop;
      if (needsRerender) updateControls();
    }
  }
}

export async function initApp(): Promise<void> {
  renderApp();
  subscribe(onStateChange);

  try {
    const health = await api.health();
    pushEvent(
      health.mock
        ? "Backend connecté — mode simulation actif"
        : "Backend connecté — mode robot réel"
    );
    setPoints(await api.getPoints());
    try {
      setMap(await api.getMap());
    } catch {
      pushEvent("Carte non disponible pour le moment");
    }
    try {
      setSettings(await api.getSettings());
    } catch {
      /* settings optionnels au démarrage */
    }
    try {
      setActions(await api.getActions());
    } catch {
      pushEvent("Actions d'accueil non chargées");
    }
    if (state.points.length > 0) {
      setSelectedPoint(state.points[0].name);
    }
  } catch (err) {
    pushEvent(`Impossible de joindre le backend : ${(err as Error).message}`);
  }

  connectTelemetry();
}
