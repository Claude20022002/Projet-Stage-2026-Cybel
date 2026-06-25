import type { PatrolStatus, PatrolTaskData } from "../types";

export function renderPatrolPanel(
  tasks: PatrolTaskData[],
  selectedTaskId: string | null,
  patrolStatus: PatrolStatus | null,
  editingStopId: string | null,
  options?: { pageMode?: boolean }
): string {
  const pageMode = options?.pageMode ?? false;
  const task = tasks.find((t) => t.id === selectedTaskId) ?? tasks[0] ?? null;
  const running = patrolStatus?.state === "running";
  const stops = task?.stops ?? [];
  const editing = editingStopId
    ? stops.find((s) => s.id === editingStopId) ?? null
    : null;

  return `
    <section class="patrol-panel card${pageMode ? " patrol-panel--page" : ""}">
      <div class="patrol-panel__header${pageMode ? " patrol-panel__header--solo" : ""}">
        ${pageMode ? "" : "<h2>Patrouille</h2>"}
        <span class="patrol-panel__badge patrol-panel__badge--${patrolStatus?.state ?? "idle"}">
          ${patrolStatusLabel(patrolStatus)}
        </span>
      </div>

      <div class="patrol-panel__task-select">
        <label for="patrol-task-select">Tâche</label>
        <select id="patrol-task-select" ${running ? "disabled" : ""}>
          ${tasks
            .map(
              (t) => `
            <option value="${t.id}" ${task?.id === t.id ? "selected" : ""}>${t.name}</option>
          `
            )
            .join("")}
        </select>
        ${task ? `<span class="patrol-panel__mode">Mode : ${modeLabel(task.mode)}</span>` : ""}
      </div>

      ${
        running
          ? `<p class="patrol-panel__live">
              Cycle <strong>${patrolStatus?.cycle_count ?? 0}</strong>
              — arrêt ${Math.max((patrolStatus?.current_index ?? 0) + 1, 1)} / ${patrolStatus?.total_stops ?? stops.length}
              <br /><strong>${patrolStatus?.current_stop_name ?? "…"}</strong>
              <br /><span class="patrol-panel__phase">${patrolPhaseHint(patrolStatus)}</span>
            </p>`
          : `<p class="patrol-panel__hint">${stops.length} point(s) de contrôle — boucle jusqu'à arrêt manuel.</p>`
      }

      ${
        patrolStatus?.state === "error" && patrolStatus.error
          ? `<p class="patrol-panel__error" role="alert">${patrolStatus.error}</p>`
          : ""
      }

      <div class="patrol-panel__controls">
        <button
          id="btn-patrol-start"
          class="btn btn--primary btn--block"
          type="button"
          ${running || !task ? "disabled" : ""}
        >
          Démarrer la patrouille
        </button>
        <button
          id="btn-patrol-stop"
          class="btn btn--secondary btn--block"
          type="button"
          ${running ? "" : "disabled"}
        >
          Arrêter la patrouille
        </button>
      </div>

      <div class="patrol-panel__stops">
        <div class="patrol-panel__stops-header">
          <h3>Points de contrôle</h3>
          <button id="btn-patrol-add" class="btn btn--secondary btn--sm" type="button" ${running || !task ? "disabled" : ""}>
            + Ajouter
          </button>
        </div>
        <ul class="patrol-stop-list">
          ${stops
            .map(
              (stop, index) => `
            <li class="patrol-stop-item ${editingStopId === stop.id ? "patrol-stop-item--active" : ""}">
              <div class="patrol-stop-item__main">
                <span class="patrol-stop-item__num">${index + 1}</span>
                <div>
                  <strong>${stop.name}</strong>
                  <span class="patrol-stop-item__coords">${formatCoords(stop)}</span>
                </div>
              </div>
              <div class="patrol-stop-item__actions">
                <button class="btn btn--ghost btn--sm" data-patrol-edit="${stop.id}" type="button" ${running ? "disabled" : ""}>Modifier</button>
                <button class="btn btn--ghost btn--sm btn--danger-text" data-patrol-delete="${stop.id}" type="button" ${running ? "disabled" : ""}>Suppr.</button>
              </div>
            </li>
          `
            )
            .join("")}
        </ul>
      </div>

      ${
        task && !running
          ? `
        <div class="patrol-panel__editor">
          <h3>${editing ? `Modifier : ${editing.name}` : "Nouveau point"}</h3>
          ${renderStopForm(task.id, editing)}
        </div>
      `
          : ""
      }
    </section>
  `;
}

function modeLabel(mode: string): string {
  switch (mode) {
    case "round_trip":
      return "Aller-retour";
    case "random":
      return "Aléatoire";
    default:
      return "Cycle";
  }
}

function patrolStatusLabel(status: PatrolStatus | null): string {
  switch (status?.state) {
    case "running":
      return status.phase === "navigating" ? "En déplacement" : "En patrouille";
    case "stopped":
      return "Interrompue";
    case "error":
      return "Erreur";
    default:
      return "Au repos";
  }
}

function patrolPhaseHint(status: PatrolStatus | null): string {
  if (!status || status.state !== "running") return "";
  if (status.phase === "navigating") return "Déplacement vers le point de contrôle…";
  if (status.phase === "announcing") return "Annonce sur place…";
  if (status.phase === "dwell") return "Surveillance du point…";
  return status.message;
}

function formatCoords(stop: { x?: number; y?: number; target_point?: string }): string {
  if (stop.target_point) return `POI : ${stop.target_point}`;
  if (stop.x != null && stop.y != null) {
    return `(${stop.x.toFixed(2)}, ${stop.y.toFixed(2)})`;
  }
  return "—";
}

function renderStopForm(taskId: string, editing: { id: string; name: string; speech_fr?: string; x?: number; y?: number; theta?: number; dwell_seconds?: number } | null): string {
  return `
    <form id="patrol-stop-form" class="tour-stop-form">
      <input type="hidden" id="patrol-task-id" value="${taskId}" />
      <input type="hidden" id="patrol-stop-id" value="${editing?.id ?? ""}" />
      <label>Nom du point
        <input id="patrol-name" type="text" required value="${editing?.name ?? ""}" />
      </label>
      <label>Annonce TTS (FR)
        <textarea id="patrol-speech-fr" rows="2">${editing?.speech_fr ?? ""}</textarea>
      </label>
      <div class="tour-stop-form__row">
        <label>X <input id="patrol-x" type="number" step="0.01" value="${editing?.x ?? ""}" /></label>
        <label>Y <input id="patrol-y" type="number" step="0.01" value="${editing?.y ?? ""}" /></label>
        <label>θ <input id="patrol-theta" type="number" step="0.01" value="${editing?.theta ?? 0}" /></label>
      </div>
      <label>Temps sur place (s)
        <input id="patrol-dwell" type="number" min="0" step="1" value="${editing?.dwell_seconds ?? 8}" />
      </label>
      <div class="tour-stop-form__actions">
        <button id="btn-patrol-use-pose" class="btn btn--ghost btn--sm" type="button">Position robot</button>
        <button id="btn-patrol-cancel-edit" class="btn btn--ghost btn--sm" type="button">Annuler</button>
        <button class="btn btn--primary btn--sm" type="submit">Enregistrer</button>
      </div>
    </form>
  `;
}
