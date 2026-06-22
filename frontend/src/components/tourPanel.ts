import { icons } from "../icons";
import type { LabTourData, TourStatus, TourStopData } from "../types";

export function renderTourPanel(
  tour: LabTourData | null,
  tourStatus: TourStatus | null,
  editingStopId: string | null
): string {
  const running = tourStatus?.state === "running";
  const stops = tour?.stops ?? [];
  const editing = editingStopId
    ? stops.find((s) => s.id === editingStopId) ?? null
    : null;

  return `
    <section class="tour-panel card">
      <div class="tour-panel__header">
        <h2>Visite guidée</h2>
        <span class="tour-panel__badge tour-panel__badge--${tourStatus?.state ?? "idle"}">
          ${tourStatusLabel(tourStatus)}
        </span>
      </div>

      ${
        running
          ? `<p class="tour-panel__live">
              Étape ${Math.max((tourStatus?.current_index ?? 0) + 1, 1)} / ${tourStatus?.total_stops ?? stops.length}
              — ${tourStatus?.current_equipment ?? "…"}
            </p>`
          : `<p class="tour-panel__hint">${stops.length} arrêt(s) configuré(s) sur le parcours.</p>`
      }

      <div class="tour-panel__halt">
        <button id="btn-tour-halt" class="btn btn--danger btn--block btn--with-icon" type="button">
          ${icons.octagon("icon", 16)}
          <span>ARRÊT TOTAL (visite + robot)</span>
        </button>
        <button id="btn-tour-stop" class="btn btn--secondary btn--block" type="button" ${running ? "" : "disabled"}>
          Arrêter la visite
        </button>
      </div>

      <div class="tour-panel__stops">
        <div class="tour-panel__stops-header">
          <h3>Arrêts du parcours</h3>
          <button id="btn-tour-add" class="btn btn--secondary btn--sm" type="button">+ Ajouter</button>
        </div>
        <ul class="tour-stop-list">
          ${stops
            .map(
              (stop, index) => `
            <li class="tour-stop-item ${editingStopId === stop.id ? "tour-stop-item--active" : ""}">
              <div class="tour-stop-item__main">
                <span class="tour-stop-item__num">${index + 1}</span>
                <div>
                  <strong>${stop.equipment_fr}</strong>
                  <span>${stop.name_fr}</span>
                  <span class="tour-stop-item__coords">${formatCoords(stop)}</span>
                </div>
              </div>
              <div class="tour-stop-item__actions">
                <button class="btn btn--ghost btn--sm" data-tour-edit="${stop.id}" type="button">Modifier</button>
                <button class="btn btn--ghost btn--sm btn--danger-text" data-tour-delete="${stop.id}" type="button">Suppr.</button>
              </div>
            </li>
          `
            )
            .join("")}
        </ul>
      </div>

      <div class="tour-panel__editor">
        <h3>${editing ? `Modifier : ${editing.equipment_fr}` : "Nouvel arrêt"}</h3>
        ${renderStopForm(editing)}
      </div>
    </section>
  `;
}

function tourStatusLabel(status: TourStatus | null): string {
  switch (status?.state) {
    case "running":
      return "En cours";
    case "completed":
      return "Terminée";
    case "stopped":
      return "Interrompue";
    case "error":
      return "Erreur";
    default:
      return "Au repos";
  }
}

function formatCoords(stop: TourStopData): string {
  if (stop.x != null && stop.y != null) {
    return `(${stop.x.toFixed(2)}, ${stop.y.toFixed(2)})`;
  }
  if (stop.target_point) return `POI: ${stop.target_point}`;
  return "Sans position";
}

function renderStopForm(stop: TourStopData | null): string {
  const v = (key: keyof TourStopData, fallback = "") =>
    stop?.[key] != null ? String(stop[key]) : fallback;

  return `
    <form id="tour-stop-form" class="tour-form">
      <input type="hidden" id="tour-stop-id" value="${v("id")}" />
      <label class="tour-form__field">
        <span>Équipement (FR)</span>
        <input id="tour-equipment-fr" type="text" required value="${v("equipment_fr")}" />
      </label>
      <label class="tour-form__field">
        <span>Zone / nom (FR)</span>
        <input id="tour-name-fr" type="text" value="${v("name_fr")}" />
      </label>
      <label class="tour-form__field">
        <span>Présentation vocale (FR)</span>
        <textarea id="tour-speech-fr" rows="3">${v("speech_fr")}</textarea>
      </label>
      <div class="tour-form__row">
        <label class="tour-form__field">
          <span>X</span>
          <input id="tour-x" type="number" step="0.01" value="${v("x")}" />
        </label>
        <label class="tour-form__field">
          <span>Y</span>
          <input id="tour-y" type="number" step="0.01" value="${v("y")}" />
        </label>
        <label class="tour-form__field">
          <span>θ</span>
          <input id="tour-theta" type="number" step="0.01" value="${v("theta", "0")}" />
        </label>
      </div>
      <label class="tour-form__field">
        <span>Pause sur place (s)</span>
        <input id="tour-dwell" type="number" min="0" step="1" value="${v("dwell_seconds", "12")}" />
      </label>
      <div class="tour-form__actions">
        <button id="btn-tour-use-pose" class="btn btn--secondary" type="button">Position robot</button>
        <button id="btn-tour-save-stop" class="btn btn--primary" type="submit">
          ${stop ? "Enregistrer" : "Créer l'arrêt"}
        </button>
        ${
          stop
            ? `<button id="btn-tour-cancel-edit" class="btn btn--ghost" type="button">Annuler</button>`
            : ""
        }
      </div>
    </form>
  `;
}
