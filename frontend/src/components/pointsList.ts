import { icons } from "../icons";
import type { Point } from "../types";

const TYPE_LABELS: Record<string, string> = {
  charging: "Pile",
  common: "Point",
  gate: "Porte",
  access: "Accès",
  ride: "Ascenseur",
  wait: "Attente",
  label: "Étiquette",
  stop: "Stop",
};

function isDeletablePoint(point: Point): boolean {
  return point.id.startsWith("local-");
}

export function renderPointsList(
  points: Point[],
  selectedPoint: string | null
): string {
  const items = points
    .map(
      (point) => `
      <div class="point-item-row ${point.name === selectedPoint ? "point-item-row--selected" : ""}">
        <button
          class="point-item ${point.name === selectedPoint ? "point-item--selected" : ""}"
          data-point="${point.name}"
          type="button"
        >
          <span class="point-item__dot point-item__dot--${point.type}"></span>
          <span class="point-item__info">
            <span class="point-item__name">${point.name}</span>
            <span class="point-item__meta">${TYPE_LABELS[point.type] ?? point.type} · (${point.x.toFixed(1)}, ${point.y.toFixed(1)})</span>
          </span>
          ${point.name === selectedPoint ? icons.mapPin("icon icon--point-selected", 14) : ""}
        </button>
        ${
          isDeletablePoint(point)
            ? `<button class="point-item__delete icon-btn" data-delete-point="${point.name}" type="button" title="Supprimer ce point">
                ${icons.trash("icon", 14)}
              </button>`
            : ""
        }
      </div>
    `
    )
    .join("");

  return `
    <aside class="points-panel">
      <div class="points-panel__header">
        <h2>Points</h2>
        <div class="points-panel__header-actions">
          <span class="points-panel__count">${points.length}</span>
          <button class="icon-btn" id="btn-add-point" type="button" title="Ajouter un point à la position actuelle du robot">
            ${icons.plus("icon", 16)}
          </button>
          <button class="icon-btn" id="btn-refresh-points" type="button" title="Actualiser la liste depuis le robot">
            ${icons.refresh("icon", 16)}
          </button>
        </div>
      </div>
      <div class="points-panel__list">
        ${items || '<p class="points-panel__empty">Aucun point disponible</p>'}
      </div>
      <button id="btn-navigate" class="btn btn--primary btn--block btn--with-icon" type="button" ${
        selectedPoint ? "" : "disabled"
      }>
        ${icons.navigation("icon", 16)}
        <span>Aller vers ${selectedPoint ?? "…"}</span>
      </button>
      <button id="btn-cancel-nav" class="btn btn--ghost btn--block btn--with-icon" type="button">
        ${icons.x("icon", 16)}
        <span>Annuler navigation</span>
      </button>
    </aside>
  `;
}
