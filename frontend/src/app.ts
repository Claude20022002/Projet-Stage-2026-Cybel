import { api } from "./api";
import { renderControls, renderEventsLog } from "./components/controls";
import { drawMap, renderMapCanvas } from "./components/mapView";
import { renderPointsList } from "./components/pointsList";
import { renderStatusBar } from "./components/statusBar";
import { connectTelemetry } from "./telemetry";
import {
  state,
  subscribe,
  setPoints,
  setSelectedPoint,
  pushEvent,
} from "./state";

const MOVE_SPEED = 0.2;
const ROTATE_SPEED = 0.5;
let moveInterval: number | null = null;
let controlsBound = false;

function renderShell(): void {
  const app = document.getElementById("app");
  if (!app) return;

  const manualMode = state.status?.nav_mode === "manual";
  const softEstop = state.status?.soft_estop ?? false;

  app.innerHTML = `
    <div class="dashboard">
      <div id="status-bar-container"></div>
      <main class="dashboard__main">
        <div id="points-panel-container"></div>
        ${renderMapCanvas()}
        <div id="controls-panel-container">${renderControls(manualMode, softEstop)}</div>
      </main>
    </div>
  `;

  controlsBound = false;
  bindControlEvents();
  updateAll();
}

function updateAll(): void {
  updateStatusBar();
  updatePointsPanel();
  updateMap();
  updateControls();
  updateEventsLog();
}

function updateStatusBar(): void {
  const el = document.getElementById("status-bar-container");
  if (el) el.innerHTML = renderStatusBar(state.status, state.wsConnected);
}

function updatePointsPanel(): void {
  const el = document.getElementById("points-panel-container");
  if (el) {
    el.innerHTML = renderPointsList(state.points, state.selectedPoint);
    bindPointEvents();
  }
}

function updateMap(): void {
  const canvas = document.getElementById("map-canvas") as HTMLCanvasElement | null;
  if (canvas) {
    drawMap(
      canvas,
      state.pose,
      state.points,
      state.selectedPoint,
      state.status?.current_goal ?? null
    );
  }
}

function updateControls(): void {
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
  updateStatusBar();
  updateMap();
  updateEventsLog();

  const navigateBtn = document.getElementById("btn-navigate") as HTMLButtonElement | null;
  if (navigateBtn) {
    navigateBtn.disabled = !state.selectedPoint;
    navigateBtn.textContent = `Aller vers ${state.selectedPoint ?? "…"}`;
  }

  document.querySelectorAll("[data-point]").forEach((el) => {
    const name = (el as HTMLElement).dataset.point;
    el.classList.toggle("point-item--selected", name === state.selectedPoint);
  });

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

export async function initApp(): Promise<void> {
  renderShell();
  subscribe(onStateChange);

  try {
    const health = await api.health();
    pushEvent(
      health.mock
        ? "Backend connecté — mode simulation actif"
        : "Backend connecté — mode robot réel"
    );
    setPoints(await api.getPoints());
    if (state.points.length > 0) {
      setSelectedPoint(state.points[0].name);
    }
  } catch (err) {
    pushEvent(`Impossible de joindre le backend : ${(err as Error).message}`);
  }

  connectTelemetry();
}
