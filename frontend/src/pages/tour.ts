import { icons } from "../icons";
import { renderTourPanel } from "../components/tourPanel";
import type { LabTourData, TourStatus } from "../types";

export function renderTourPage(
  tour: LabTourData | null,
  tourStatus: TourStatus | null,
  editingStopId: string | null
): string {
  const stops = tour?.stops?.length ?? 0;

  return `
    <div class="tour-page">
      <header class="tour-page__header">
        <div>
          <h1>${icons.route("icon", 22)} Visite guidée</h1>
          <p>Parcours, arrêts et lancement de la visite du laboratoire</p>
        </div>
        <span class="tour-page__meta">${stops} arrêt(s)</span>
      </header>
      <div id="tour-panel-container">
        ${renderTourPanel(tour, tourStatus, editingStopId, { pageMode: true })}
      </div>
    </div>
  `;
}
