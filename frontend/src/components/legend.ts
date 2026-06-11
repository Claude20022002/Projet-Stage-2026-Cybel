import { icons } from "../icons";
import type { MapData } from "../types";

const POINT_LEGEND: { type: string; color: string; label: string }[] = [
  { type: "charging", color: "#22c55e", label: "Pile de charge" },
  { type: "common", color: "#3b82f6", label: "Point commun" },
  { type: "gate", color: "#f97316", label: "Porte" },
  { type: "access", color: "#a855f7", label: "Point d'accès" },
  { type: "ride", color: "#ec4899", label: "Ascenseur (intérieur)" },
  { type: "wait", color: "#06b6d4", label: "Ascenseur (extérieur)" },
];

const MAP_LEGEND: { color: string; label: string }[] = [
  { color: "#ef4444", label: "LiDAR (temps réel)" },
  { color: "#1e293b", label: "Obstacle cartographié" },
  { color: "#8b5cf6", label: "Visiteur détecté" },
];

function renderItems(items: { color: string; label: string }[]): string {
  return items
    .map(
      (item) => `
      <div class="legend__item">
        <span class="legend__dot" style="background:${item.color}"></span>
        <span>${item.label}</span>
      </div>
    `
    )
    .join("");
}

export function renderMapInfoCard(map: MapData | null): string {
  const name = map?.metadata.name ?? "—";
  const floor = map?.metadata.floor ?? "0";
  const area = map?.metadata.area_sqm;

  return `
    <section class="legend-card">
      <div class="legend-card__header">
        <div class="legend-card__title">
          ${icons.map("icon", 16)}
          <span>${name} · Étage ${floor}</span>
        </div>
        <button class="icon-btn" type="button" title="Options">
          ${icons.moreVertical("icon", 16)}
        </button>
      </div>
      <div class="legend__group">${renderItems(POINT_LEGEND)}</div>
      <div class="legend__group legend__group--map">${renderItems(MAP_LEGEND)}</div>
      ${area ? `<div class="legend-card__area">Surface cartographiée : <strong>${area} m²</strong></div>` : ""}
    </section>
  `;
}
