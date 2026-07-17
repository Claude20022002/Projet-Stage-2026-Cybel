import { icons } from "../icons";
import type { AppPage } from "../types";

export function renderLayout(
  activePage: AppPage,
  content: string,
  options?: { tourActive?: boolean }
): string {
  const tourActive = options?.tourActive ?? false;
  return `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="sidebar__brand">
          <span class="sidebar__logo">${icons.home("icon icon--brand", 22)}</span>
          <span class="sidebar__title">CYBEL</span>
        </div>
        <nav class="sidebar__nav">
          <button
            class="sidebar__link ${activePage === "dashboard" ? "sidebar__link--active" : ""}"
            data-page="dashboard"
            type="button"
          >
            ${icons.map("icon", 18)}
            <span>Contrôle</span>
          </button>
          <button
            class="sidebar__link ${activePage === "tour" ? "sidebar__link--active" : ""}"
            data-page="tour"
            type="button"
          >
            ${icons.route("icon", 18)}
            <span>Visite</span>
            ${tourActive ? '<span class="sidebar__link-dot" aria-hidden="true"></span>' : ""}
          </button>
          <button
            class="sidebar__link ${activePage === "patrol" ? "sidebar__link--active" : ""}"
            data-page="patrol"
            type="button"
          >
            ${icons.patrol("icon", 18)}
            <span>Patrouille</span>
          </button>
          <button
            class="sidebar__link ${activePage === "visitors" ? "sidebar__link--active" : ""}"
            data-page="visitors"
            type="button"
          >
            ${icons.users("icon", 18)}
            <span>Visiteurs</span>
          </button>
          <button
            class="sidebar__link ${activePage === "settings" ? "sidebar__link--active" : ""}"
            data-page="settings"
            type="button"
          >
            ${icons.settings("icon", 18)}
            <span>Paramètres</span>
          </button>
        </nav>
        <div class="sidebar__footer">
          <span class="sidebar__version">v0.2</span>
        </div>
      </aside>
      <div class="app-shell__content">
        ${content}
      </div>
    </div>
  `;
}
