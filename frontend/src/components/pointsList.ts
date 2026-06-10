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

export function renderPointsList(
  points: Point[],
  selectedPoint: string | null
): string {
  const items = points
    .map(
      (point) => `
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
      </button>
    `
    )
    .join("");

  return `
    <aside class="points-panel">
      <div class="points-panel__header">
        <h2>Points</h2>
        <span class="points-panel__count">${points.length}</span>
      </div>
      <div class="points-panel__list">
        ${items || '<p class="points-panel__empty">Aucun point disponible</p>'}
      </div>
      <button id="btn-navigate" class="btn btn--primary btn--block" type="button" ${
        selectedPoint ? "" : "disabled"
      }>
        Aller vers ${selectedPoint ?? "…"}
      </button>
      <button id="btn-cancel-nav" class="btn btn--ghost btn--block" type="button">
        Annuler navigation
      </button>
    </aside>
  `;
}
