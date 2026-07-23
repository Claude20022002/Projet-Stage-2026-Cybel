/** Icônes SVG inline (vendorisées, pas de webfont/CDN — kiosque offline, Chrome 49
 * WebView). Même convention que frontend/src/icons/index.ts (interface opérateur) :
 * lignes simples en `currentColor`, héritent des tokens de couleur de style.css. */

function svg(
  paths: string,
  className = "icon",
  size = 20,
  fill: "none" | "currentColor" = "none"
): string {
  const fillAttr = fill === "currentColor" ? ' fill="currentColor"' : ' fill="none"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24"${fillAttr} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="${className}" aria-hidden="true">${paths}</svg>`;
}

export const icons = {
  mic: (cls = "icon", size = 20) =>
    svg(
      '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>',
      cls,
      size
    ),

  mapPin: (cls = "icon", size = 20) =>
    svg(
      '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
      cls,
      size
    ),

  plug: (cls = "icon", size = 20) =>
    svg(
      '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a6 6 0 0 1-12 0V8z"/>',
      cls,
      size
    ),

  door: (cls = "icon", size = 20) =>
    svg(
      '<rect x="6" y="2" width="12" height="20" rx="1"/><circle cx="14" cy="12" r="1" fill="currentColor"/>',
      cls,
      size
    ),

  elevator: (cls = "icon", size = 20) =>
    svg(
      '<rect x="4" y="2" width="16" height="20" rx="2"/><polyline points="9 8 12 5 15 8"/><polyline points="9 16 12 19 15 16"/>',
      cls,
      size
    ),

  hourglass: (cls = "icon", size = 20) =>
    svg(
      '<line x1="5" y1="2" x2="19" y2="2"/><line x1="5" y1="22" x2="19" y2="22"/><path d="M17 22v-4.17a2 2 0 0 0-.59-1.42L12 12l-4.41 4.41a2 2 0 0 0-.59 1.42V22"/><path d="M7 2v4.17a2 2 0 0 0 .59 1.42L12 12l4.41-4.41A2 2 0 0 0 17 6.17V2"/>',
      cls,
      size
    ),

  octagon: (cls = "icon", size = 20) =>
    svg('<path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86L7.86 2z"/>', cls, size),

  tag: (cls = "icon", size = 20) =>
    svg(
      '<path d="M12.59 2.59A2 2 0 0 0 11.17 2H4a2 2 0 0 0-2 2v7.17a2 2 0 0 0 .59 1.41l8.7 8.71a2.43 2.43 0 0 0 3.42 0l6.3-6.3a2.43 2.43 0 0 0 0-3.42Z"/><circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/>',
      cls,
      size
    ),

  map: (cls = "icon", size = 20) =>
    svg(
      '<polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21 3 6"/><line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/>',
      cls,
      size
    ),

  helpCircle: (cls = "icon", size = 20) =>
    svg(
      '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
      cls,
      size
    ),

  robot: (cls = "icon", size = 20) =>
    svg(
      '<rect x="4" y="9" width="16" height="10" rx="2"/><circle cx="9" cy="14" r="1.5" fill="currentColor"/><circle cx="15" cy="14" r="1.5" fill="currentColor"/><line x1="12" y1="9" x2="12" y2="5"/><circle cx="12" cy="3.5" r="1.5"/><line x1="2" y1="13" x2="4" y2="13"/><line x1="20" y1="13" x2="22" y2="13"/>',
      cls,
      size
    ),

  search: (cls = "icon", size = 20) =>
    svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>', cls, size),

  alertTriangle: (cls = "icon", size = 20) =>
    svg(
      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
      cls,
      size
    ),

  checkCircle: (cls = "icon", size = 20) =>
    svg('<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>', cls, size),

  battery: (cls = "icon", size = 18) =>
    svg(
      '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M6 11v2"/><path d="M10 11v2"/>',
      cls,
      size
    ),
};

const POINT_ICON_KEYS: Record<string, keyof typeof icons> = {
  charging: "plug",
  gate: "door",
  access: "door",
  ride: "elevator",
  wait: "hourglass",
  stop: "octagon",
  label: "tag",
  common: "mapPin",
};

/** Icône SVG pour un type de point d'intérêt (remplace l'ancien lookup emoji). */
export function pointIconSvg(type: string, cls = "icon", size = 20): string {
  const key = POINT_ICON_KEYS[type] ?? POINT_ICON_KEYS.common;
  return icons[key](cls, size);
}
