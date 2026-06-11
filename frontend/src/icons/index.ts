function svg(
  paths: string,
  className = "icon",
  size = 18,
  fill: "none" | "currentColor" = "none"
): string {
  const fillAttr = fill === "currentColor" ? ' fill="currentColor"' : ' fill="none"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24"${fillAttr} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="${className}" aria-hidden="true">${paths}</svg>`;
}

export const icons = {
  battery: (cls = "icon", size = 18) =>
    svg(
      '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M6 11v2"/><path d="M10 11v2"/>',
      cls,
      size
    ),

  wifi: (cls = "icon", size = 16) =>
    svg(
      '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><path d="M12 20h.01"/>',
      cls,
      size
    ),

  wifiOff: (cls = "icon", size = 16) =>
    svg(
      '<path d="M12 20h.01"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><path d="M5 12.55a11 11 0 0 1 5.17-2.39"/><path d="M19 12.55a11 11 0 0 0-2.3-1.58"/><line x1="2" y1="2" x2="22" y2="22"/>',
      cls,
      size
    ),

  plug: (cls = "icon", size = 14) =>
    svg(
      '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a6 6 0 0 1-12 0V8z"/>',
      cls,
      size
    ),

  alertTriangle: (cls = "icon", size = 16) =>
    svg(
      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
      cls,
      size
    ),

  arrowUp: (cls = "icon", size = 20) =>
    svg('<path d="m18 15-6-6-6 6"/>', cls, size),

  arrowDown: (cls = "icon", size = 20) =>
    svg('<path d="m6 9 6 6 6-6"/>', cls, size),

  arrowLeft: (cls = "icon", size = 20) =>
    svg('<path d="m15 18-6-6 6-6"/>', cls, size),

  arrowRight: (cls = "icon", size = 20) =>
    svg('<path d="m9 18 6-6-6-6"/>', cls, size),

  square: (cls = "icon", size = 18) =>
    svg('<rect x="6" y="6" width="12" height="12" rx="1"/>', cls, size, "currentColor"),

  mapPin: (cls = "icon", size = 16) =>
    svg(
      '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
      cls,
      size
    ),

  navigation: (cls = "icon", size = 16) =>
    svg(
      '<polygon points="3 11 22 2 13 21 11 13 3 11"/>',
      cls,
      size,
      "currentColor"
    ),

  x: (cls = "icon", size = 16) =>
    svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', cls, size),

  home: (cls = "icon", size = 20) =>
    svg(
      '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
      cls,
      size
    ),

  settings: (cls = "icon", size = 20) =>
    svg(
      '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
      cls,
      size
    ),

  map: (cls = "icon", size = 20) =>
    svg(
      '<polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21 3 6"/><line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/>',
      cls,
      size
    ),

  octagon: (cls = "icon", size = 18) =>
    svg(
      '<path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86L7.86 2z"/>',
      cls,
      size
    ),

  circleDot: (cls = "icon", size = 10) =>
    svg('<circle cx="12" cy="12" r="4"/>', cls, size, "currentColor"),

  mic: (cls = "icon", size = 18) =>
    svg(
      '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>',
      cls,
      size
    ),

  micOff: (cls = "icon", size = 18) =>
    svg(
      '<line x1="2" y1="2" x2="22" y2="22"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V5a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="22"/>',
      cls,
      size
    ),

  users: (cls = "icon", size = 18) =>
    svg(
      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
      cls,
      size
    ),

  route: (cls = "icon", size = 18) =>
    svg(
      '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
      cls,
      size
    ),

  message: (cls = "icon", size = 18) =>
    svg(
      '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
      cls,
      size
    ),

  volume: (cls = "icon", size = 18) =>
    svg(
      '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>',
      cls,
      size
    ),

  crosshair: (cls = "icon", size = 18) =>
    svg(
      '<circle cx="12" cy="12" r="8"/><line x1="22" y1="12" x2="18" y2="12"/><line x1="6" y1="12" x2="2" y2="12"/><line x1="12" y1="6" x2="12" y2="2"/><line x1="12" y1="22" x2="12" y2="18"/>',
      cls,
      size
    ),

  moreVertical: (cls = "icon", size = 16) =>
    svg(
      '<circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="19" r="1.5"/>',
      cls,
      size,
      "currentColor"
    ),

  hash: (cls = "icon", size = 16) =>
    svg(
      '<line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/>',
      cls,
      size
    ),
};
