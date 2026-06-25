import { icons } from "../icons";
import { renderPatrolPanel } from "../components/patrolPanel";
import type { PatrolStatus, PatrolTaskData } from "../types";

export function renderPatrolPage(
  tasks: PatrolTaskData[],
  selectedTaskId: string | null,
  patrolStatus: PatrolStatus | null,
  editingStopId: string | null
): string {
  const task = tasks.find((t) => t.id === selectedTaskId) ?? tasks[0];
  const stops = task?.stops?.length ?? 0;

  return `
    <div class="patrol-page">
      <header class="patrol-page__header">
        <div>
          <h1>${icons.patrol("icon", 22)} Patrouille</h1>
          <p>Tâches cycliques, points de contrôle et annonces vocales</p>
        </div>
        <span class="patrol-page__meta">${stops} point(s)</span>
      </header>
      <div id="patrol-panel-container">
        ${renderPatrolPanel(tasks, selectedTaskId, patrolStatus, editingStopId, { pageMode: true })}
      </div>
    </div>
  `;
}
