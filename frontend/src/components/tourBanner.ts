import { icons } from "../icons";
import type { LabTourData, TourStatus } from "../types";

export function renderTourBanner(
  tour: LabTourData | null,
  tourStatus: TourStatus | null
): string {
  const running = tourStatus?.state === "running";
  const stops = tour?.stops ?? [];
  const state = tourStatus?.state ?? "idle";

  const liveLine = running
    ? `Étape ${Math.max((tourStatus?.current_index ?? 0) + 1, 1)} / ${tourStatus?.total_stops ?? stops.length} — ${tourStatus?.current_equipment ?? "…"}`
    : `${stops.length} arrêt(s) sur le parcours`;

  return `
    <section class="tour-banner card">
      <div class="tour-banner__icon">${icons.route("icon", 20)}</div>
      <div class="tour-banner__body">
        <div class="tour-banner__title-row">
          <strong>Visite guidée</strong>
          <span class="tour-banner__badge tour-banner__badge--${state}">
            ${statusLabel(tourStatus)}
          </span>
        </div>
        <p class="tour-banner__hint">${liveLine}</p>
      </div>
      <div class="tour-banner__actions">
        ${
          running
            ? `<button class="btn btn--danger btn--sm" id="btn-tour-banner-halt" type="button">Arrêt total</button>`
            : ""
        }
        <button class="btn btn--secondary btn--sm" data-page="tour" type="button">
          ${running ? "Détails" : "Gérer le parcours"}
        </button>
      </div>
    </section>
  `;
}

function statusLabel(status: TourStatus | null): string {
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
