/**
 * Panneau staff de la semaine d'intégration — TEMPORAIRE-INTEGRATION-2026.
 *
 * Appui long (3 s) dans le coin haut-gauche de l'écran tactile → code staff →
 * panneau : mode événement (les deux écrans), circulation, annonce immédiate.
 * Le code est vérifié par le backend ; le démarrer/arrêter la circulation passe
 * par /api/event/circulation/*. Arrêter ne demande pas de code.
 *
 * Autonome : monte son propre élément hors de #app (que le kiosque réécrit à
 * chaque rendu). Pour retirer la fonctionnalité : supprimer ce fichier,
 * staffPanel.css et l'appel initStaffPanel() dans app.ts.
 */
import "./staffPanel.css";

const LONG_PRESS_MS = 3000;
const POLL_MS = 2000;
const IDLE_CLOSE_MS = 120_000;
const PIN_LENGTH = 4;

type View = "closed" | "pin" | "panel";

interface CirculationStatus {
  state: "idle" | "running" | "stopped" | "error";
  phase?: string;
  cycle?: number;
  current_stop?: string;
  legs_ok?: number;
  legs_failed?: number;
  message?: string;
  error?: string | null;
  history: { at: string; event: string; [key: string]: unknown }[];
}

interface CirculationPayload {
  event_enabled: boolean;
  config: { stops?: string[]; dwell_seconds?: number; return_point?: string };
  status: CirculationStatus;
  announcer_running: boolean;
}

interface RobotStatus {
  connected: boolean;
  battery: number;
  hard_estop: boolean;
  soft_estop: boolean;
  localization_percent: number;
  nav_status_label: string;
}

let view: View = "closed";
let pin = "";
let pinError = "";
let feedback = "";
let busy = false;
let data: CirculationPayload | null = null;
let robot: RobotStatus | null = null;
let pollTimer: number | null = null;
let idleTimer: number | null = null;
let root: HTMLElement;

async function post<T>(path: string, body: object = {}): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) throw new Error(json.error || res.statusText);
  return json;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<T>;
}

export function initStaffPanel(): void {
  // Le bundle est chargé dans <head> sans defer (index.html, WebView Android 7.1) :
  // au démarrage, <body> n'existe pas encore.
  if (!document.body) {
    document.addEventListener("DOMContentLoaded", initStaffPanel);
    return;
  }
  root = document.createElement("div");
  root.id = "staff-root";
  document.body.appendChild(root);
  render();
}

// ---- cycle de vie -------------------------------------------------------------
function open(next: View): void {
  view = next;
  touchIdle();
  render();
}

function close(): void {
  view = "closed";
  pin = "";
  pinError = "";
  feedback = "";
  data = null;
  if (pollTimer !== null) window.clearInterval(pollTimer);
  if (idleTimer !== null) window.clearTimeout(idleTimer);
  pollTimer = idleTimer = null;
  render();
}

function touchIdle(): void {
  if (idleTimer !== null) window.clearTimeout(idleTimer);
  idleTimer = window.setTimeout(close, IDLE_CLOSE_MS);
}

async function refresh(): Promise<void> {
  try {
    const [circ, rob] = await Promise.all([
      get<CirculationPayload>("/api/event/circulation"),
      get<RobotStatus>("/api/robot/status").catch(() => null),
    ]);
    data = circ;
    robot = rob;
  } catch {
    feedback = "Backend injoignable";
  }
  if (view === "panel") render();
}

// ---- actions ------------------------------------------------------------------
async function submitPin(): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    await post("/api/event/staff/verify", { pin });
    pinError = "";
    view = "panel";
    await refresh();
    pollTimer = window.setInterval(() => void refresh(), POLL_MS);
  } catch {
    pinError = "Code incorrect";
    pin = "";
  } finally {
    busy = false;
    render();
  }
}

async function act(label: string, run: () => Promise<unknown>, reload = false): Promise<void> {
  if (busy) return;
  busy = true;
  feedback = `${label}…`;
  render();
  try {
    await run();
    feedback = `${label} : OK`;
    if (reload) {
      // Le kiosque relit sa config (mode événement) au démarrage.
      window.location.reload();
      return;
    }
  } catch (err) {
    feedback = `${label} : ${err instanceof Error ? err.message : "échec"}`;
  } finally {
    busy = false;
  }
  await refresh();
  render();
}

// ---- rendu --------------------------------------------------------------------
const STATE_LABEL: Record<CirculationStatus["state"], string> = {
  idle: "À l'arrêt",
  running: "En cours",
  stopped: "Arrêtée",
  error: "Interrompue",
};

function renderPin(): string {
  const dots = Array.from({ length: PIN_LENGTH }, (_, i) =>
    `<span class="staff-pin__dot ${i < pin.length ? "is-filled" : ""}"></span>`
  ).join("");
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK"]
    .map((k) => `<button type="button" class="staff-key" data-key="${k}">${k}</button>`)
    .join("");
  return `
    <div class="staff-modal staff-modal--pin">
      <h2>Accès staff</h2>
      <div class="staff-pin">${dots}</div>
      <p class="staff-error">${pinError}</p>
      <div class="staff-keypad">${keys}</div>
      <button type="button" class="staff-btn staff-btn--ghost" data-act="close">Annuler</button>
    </div>`;
}

function renderPanel(): string {
  const st = data?.status;
  const running = st?.state === "running";
  const enabled = Boolean(data?.event_enabled);
  const stops = data?.config.stops?.join(" → ") || "—";
  const estop = robot?.hard_estop || robot?.soft_estop;
  const history = (st?.history || [])
    .slice(-6)
    .reverse()
    .map((h) => {
      const detail = Object.entries(h)
        .filter(([k]) => k !== "at" && k !== "event")
        .map(([, v]) => String(v))
        .join(" · ");
      return `<li><b>${h.at}</b> ${h.event} ${detail}</li>`;
    })
    .join("");

  return `
    <div class="staff-modal">
      <header class="staff-head">
        <h2>Semaine d'intégration</h2>
        <button type="button" class="staff-btn staff-btn--ghost" data-act="close">Fermer</button>
      </header>

      <section class="staff-robot">
        <span>Batterie <b>${robot ? `${robot.battery} %` : "—"}</b></span>
        <span>Localisation <b>${robot ? `${Math.round(robot.localization_percent)} %` : "—"}</b></span>
        <span>Navigation <b>${robot?.nav_status_label ?? "—"}</b></span>
        <span class="${estop ? "is-alert" : ""}">Arrêt d'urgence <b>${estop ? "ENCLENCHÉ" : "non"}</b></span>
      </section>

      <section class="staff-block">
        <h3>Écrans (mode événement)</h3>
        <p>${enabled ? "Visuels de l'intégration affichés, kiosque verrouillé." : "Kiosque normal."}</p>
        <button type="button" class="staff-btn" data-act="${enabled ? "mode-off" : "mode-on"}" ${busy ? "disabled" : ""}>
          ${enabled ? "Désactiver le mode événement" : "Activer le mode événement"}
        </button>
      </section>

      <section class="staff-block">
        <h3>Circulation — <span class="staff-state staff-state--${st?.state ?? "idle"}">${STATE_LABEL[st?.state ?? "idle"]}</span></h3>
        <p>Parcours : ${stops}${data?.config.dwell_seconds != null ? ` · pause ${data.config.dwell_seconds} s` : ""}</p>
        ${running ? `<p>Cycle ${st?.cycle} · ${st?.current_stop || ""} · trajets réussis ${st?.legs_ok ?? 0}, ratés ${st?.legs_failed ?? 0}</p>` : ""}
        ${st?.message ? `<p class="staff-msg">${st.message}</p>` : ""}
        ${st?.error && st.error !== st.message ? `<p class="staff-error">${st.error}</p>` : ""}
        <div class="staff-row">
          ${
            running
              ? `<button type="button" class="staff-btn staff-btn--danger" data-act="circ-stop">Arrêter la circulation</button>`
              : `<button type="button" class="staff-btn staff-btn--go" data-act="circ-start" ${busy || !enabled ? "disabled" : ""}>Démarrer la circulation</button>`
          }
        </div>
        ${!enabled && !running ? `<p class="staff-hint">Activer d'abord le mode événement.</p>` : ""}
      </section>

      <section class="staff-block">
        <h3>Annonces</h3>
        <button type="button" class="staff-btn" data-act="announce" ${busy ? "disabled" : ""}>Faire une annonce maintenant</button>
      </section>

      ${feedback ? `<p class="staff-feedback">${feedback}</p>` : ""}
      ${history ? `<ul class="staff-history">${history}</ul>` : ""}
    </div>`;
}

function render(): void {
  if (!root) return;
  const hotspot = `<div class="staff-hotspot" id="staff-hotspot" aria-hidden="true"></div>`;
  if (view === "closed") {
    root.innerHTML = hotspot;
  } else {
    root.innerHTML = `<div class="staff-backdrop">${view === "pin" ? renderPin() : renderPanel()}</div>`;
  }
  bind();
}

function bind(): void {
  const hotspot = document.getElementById("staff-hotspot");
  if (hotspot) {
    let timer: number | null = null;
    const startPress = (e: Event) => {
      e.preventDefault();
      timer = window.setTimeout(() => open("pin"), LONG_PRESS_MS);
    };
    const cancelPress = () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = null;
    };
    hotspot.addEventListener("touchstart", startPress);
    hotspot.addEventListener("mousedown", startPress);
    for (const evt of ["touchend", "touchcancel", "touchmove", "mouseup", "mouseleave"]) {
      hotspot.addEventListener(evt, cancelPress);
    }
  }

  root.querySelectorAll<HTMLElement>("[data-key]").forEach((btn) => {
    btn.addEventListener("click", () => {
      touchIdle();
      const key = btn.dataset.key || "";
      if (key === "⌫") pin = pin.slice(0, -1);
      else if (key === "OK") return void submitPin();
      else if (pin.length < PIN_LENGTH) pin += key;
      pinError = "";
      if (pin.length === PIN_LENGTH) return void submitPin();
      render();
    });
  });

  root.querySelectorAll<HTMLElement>("[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      touchIdle();
      switch (btn.dataset.act) {
        case "close":
          close();
          break;
        case "mode-on":
          void act("Activation du mode événement", () => post("/api/event/mode", { pin, enabled: true }), true);
          break;
        case "mode-off":
          void act("Désactivation du mode événement", () => post("/api/event/mode", { pin, enabled: false }), true);
          break;
        case "circ-start":
          void act("Démarrage de la circulation", () => post("/api/event/circulation/start", { pin }));
          break;
        case "circ-stop":
          void act("Arrêt de la circulation", () => post("/api/event/circulation/stop"));
          break;
        case "announce":
          void act("Annonce", () => post("/api/event/announce/say"));
          break;
      }
    });
  });
}
