import type { Point, Pose } from "../types";

const POINT_COLORS: Record<string, string> = {
  charging: "#22c55e",
  common: "#3b82f6",
  gate: "#f97316",
  access: "#a855f7",
  ride: "#ec4899",
  wait: "#06b6d4",
  label: "#eab308",
  stop: "#facc15",
};

const MAP_BOUNDS = { minX: -5, maxX: 8, minY: -4, maxY: 6 };

export function renderMapCanvas(): string {
  return `
    <div class="map-panel">
      <div class="map-panel__header">
        <h2>Carte</h2>
        <span class="map-panel__floor">Étage 0</span>
      </div>
      <div class="map-panel__canvas-wrap">
        <canvas id="map-canvas" width="640" height="480"></canvas>
        <div class="map-legend">
          <div class="map-legend__item"><span style="background:#22c55e"></span>Pile</div>
          <div class="map-legend__item"><span style="background:#3b82f6"></span>Point</div>
          <div class="map-legend__item"><span style="background:#f97316"></span>Porte</div>
          <div class="map-legend__item"><span style="background:#06b6d4"></span>Attente</div>
        </div>
      </div>
    </div>
  `;
}

function worldToCanvas(
  x: number,
  y: number,
  width: number,
  height: number
): { cx: number; cy: number } {
  const padding = 40;
  const rangeX = MAP_BOUNDS.maxX - MAP_BOUNDS.minX;
  const rangeY = MAP_BOUNDS.maxY - MAP_BOUNDS.minY;
  const cx =
    padding + ((x - MAP_BOUNDS.minX) / rangeX) * (width - padding * 2);
  const cy =
    height -
    padding -
    ((y - MAP_BOUNDS.minY) / rangeY) * (height - padding * 2);
  return { cx, cy };
}

export function drawMap(
  canvas: HTMLCanvasElement,
  pose: Pose | null,
  points: Point[],
  selectedPoint: string | null,
  goal: Pose | null
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);

  // Fond
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, width, height);

  // Grille
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  const gridStep = 40;
  for (let x = 0; x <= width; x += gridStep) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let y = 0; y <= height; y += gridStep) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  // Trajectoire vers objectif
  if (pose && goal) {
    const from = worldToCanvas(pose.x, pose.y, width, height);
    const to = worldToCanvas(goal.x, goal.y, width, height);
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(from.cx, from.cy);
    ctx.lineTo(to.cx, to.cy);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Points
  for (const point of points) {
    const { cx, cy } = worldToCanvas(point.x, point.y, width, height);
    const color = POINT_COLORS[point.type] ?? "#64748b";
    const selected = point.name === selectedPoint;

    ctx.beginPath();
    ctx.arc(cx, cy, selected ? 10 : 7, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    if (selected) {
      ctx.strokeStyle = "#0f172a";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.fillStyle = "#334155";
    ctx.font = "11px 'DM Sans', sans-serif";
    ctx.fillText(point.name, cx + 12, cy + 4);
  }

  // Robot
  if (pose) {
    const { cx, cy } = worldToCanvas(pose.x, pose.y, width, height);
    const size = 14;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-pose.theta + Math.PI / 2);

    ctx.fillStyle = "#1e40af";
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.7, size * 0.8);
    ctx.lineTo(-size * 0.7, size * 0.8);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
  }
}
