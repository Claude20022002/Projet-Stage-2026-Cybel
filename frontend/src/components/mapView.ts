import type { LidarPoint, MapData, Point, Pose } from "../types";

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

const FALLBACK_BOUNDS = { minX: -5, maxX: 8, minY: -4, maxY: 6 };

interface Viewport {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

function getViewport(map: MapData | null): Viewport {
  if (!map) return FALLBACK_BOUNDS;
  const { metadata } = map;
  return {
    minX: metadata.origin_x,
    maxX: metadata.origin_x + metadata.width * metadata.resolution,
    minY: metadata.origin_y,
    maxY: metadata.origin_y + metadata.height * metadata.resolution,
  };
}

export function renderMapCanvas(map: MapData | null): string {
  const floor = map?.metadata.floor ?? "0";
  const name = map?.metadata.name ?? "—";
  const area = map?.metadata.area_sqm;

  return `
    <div class="map-panel">
      <div class="map-panel__header">
        <div>
          <h2>Carte</h2>
          <span class="map-panel__name">${name}</span>
        </div>
        <div class="map-panel__meta">
          <span class="map-panel__floor">Étage ${floor}</span>
          ${area ? `<span class="map-panel__area">${area} m²</span>` : ""}
        </div>
      </div>
      <div class="map-panel__canvas-wrap">
        <canvas id="map-canvas" width="640" height="480"></canvas>
        <div class="map-legend">
          <div class="map-legend__item"><span style="background:#ef4444"></span>LiDAR live</div>
          <div class="map-legend__item"><span style="background:#1e293b"></span>Obstacle carte</div>
          <div class="map-legend__item"><span style="background:#22c55e"></span>Pile</div>
          <div class="map-legend__item"><span style="background:#3b82f6"></span>Point</div>
          <div class="map-legend__item"><span style="background:#f97316"></span>Porte</div>
        </div>
      </div>
    </div>
  `;
}

function worldToCanvas(
  x: number,
  y: number,
  viewport: Viewport,
  width: number,
  height: number
): { cx: number; cy: number } {
  const padding = 24;
  const rangeX = viewport.maxX - viewport.minX || 1;
  const rangeY = viewport.maxY - viewport.minY || 1;
  const cx = padding + ((x - viewport.minX) / rangeX) * (width - padding * 2);
  const cy =
    height - padding - ((y - viewport.minY) / rangeY) * (height - padding * 2);
  return { cx, cy };
}

function cellColor(value: number): [number, number, number] {
  if (value < 0) return [226, 232, 240];
  if (value === 0) return [248, 250, 252];
  const intensity = Math.min(255, Math.round((value / 100) * 180));
  return [30, 41 + intensity * 0.3, 59 + intensity * 0.2];
}

function drawOccupancyGrid(
  ctx: CanvasRenderingContext2D,
  map: MapData,
  viewport: Viewport,
  canvasW: number,
  canvasH: number
): void {
  const { metadata, data } = map;
  const { width, height, resolution } = metadata;

  const padding = 24;
  const drawW = canvasW - padding * 2;
  const drawH = canvasH - padding * 2;

  const scaleX = drawW / (viewport.maxX - viewport.minX);
  const scaleY = drawH / (viewport.maxY - viewport.minY);
  const scale = Math.min(scaleX, scaleY);

  const mapPixelW = Math.round(width * resolution * scale);
  const mapPixelH = Math.round(height * resolution * scale);
  const offsetX = padding + (drawW - mapPixelW) / 2;
  const offsetY = padding + (drawH - mapPixelH) / 2;

  const step = Math.max(1, Math.floor(Math.max(width, height) / 400));
  const imageData = ctx.createImageData(mapPixelW, mapPixelH);

  for (let gy = 0; gy < height; gy += step) {
    for (let gx = 0; gx < width; gx += step) {
      const value = data[gy * width + gx] ?? 0;
      const [r, g, b] = cellColor(value);

      const px = Math.floor((gx / width) * mapPixelW);
      const py = Math.floor(((height - 1 - gy) / height) * mapPixelH);
      const blockW = Math.max(1, Math.ceil((step / width) * mapPixelW));
      const blockH = Math.max(1, Math.ceil((step / height) * mapPixelH));

      for (let dy = 0; dy < blockH && py + dy < mapPixelH; dy++) {
        for (let dx = 0; dx < blockW && px + dx < mapPixelW; dx++) {
          const idx = ((py + dy) * mapPixelW + (px + dx)) * 4;
          imageData.data[idx] = r;
          imageData.data[idx + 1] = g;
          imageData.data[idx + 2] = b;
          imageData.data[idx + 3] = 255;
        }
      }
    }
  }

  ctx.putImageData(imageData, offsetX, offsetY);
}

function drawFallbackGrid(ctx: CanvasRenderingContext2D, w: number, h: number): void {
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  const step = 40;
  for (let x = 0; x <= w; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
}

export function drawMap(
  canvas: HTMLCanvasElement,
  pose: Pose | null,
  points: Point[],
  selectedPoint: string | null,
  goal: Pose | null,
  map: MapData | null,
  lidar: LidarPoint[] = []
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const { width, height } = canvas;
  ctx.clearRect(0, 0, width, height);

  const viewport = getViewport(map);

  if (map) {
    drawOccupancyGrid(ctx, map, viewport, width, height);
  } else {
    drawFallbackGrid(ctx, width, height);
  }

  if (pose && goal) {
    const from = worldToCanvas(pose.x, pose.y, viewport, width, height);
    const to = worldToCanvas(goal.x, goal.y, viewport, width, height);
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(from.cx, from.cy);
    ctx.lineTo(to.cx, to.cy);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  if (lidar.length) {
    ctx.fillStyle = "rgba(239, 68, 68, 0.75)";
    for (const hit of lidar) {
      const { cx, cy } = worldToCanvas(hit.x, hit.y, viewport, width, height);
      ctx.beginPath();
      ctx.arc(cx, cy, 2, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  for (const point of points) {
    const { cx, cy } = worldToCanvas(point.x, point.y, viewport, width, height);
    const color = POINT_COLORS[point.type] ?? "#64748b";
    const selected = point.name === selectedPoint;

    ctx.beginPath();
    ctx.arc(cx, cy, selected ? 9 : 6, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();

    if (selected) {
      ctx.strokeStyle = "#0f172a";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, 11, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.fillStyle = "#0f172a";
    ctx.font = "600 10px 'DM Sans', sans-serif";
    ctx.fillText(point.name, cx + 10, cy + 3);
  }

  if (pose) {
    const { cx, cy } = worldToCanvas(pose.x, pose.y, viewport, width, height);
    const size = 12;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(-pose.theta + Math.PI / 2);

    ctx.fillStyle = "#1e40af";
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size * 0.65, size * 0.75);
    ctx.lineTo(-size * 0.65, size * 0.75);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.restore();
  }
}
