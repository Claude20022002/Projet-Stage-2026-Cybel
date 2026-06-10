import { icons } from "../icons";

export type AppPage = "dashboard" | "settings";

export function renderLayout(activePage: AppPage, content: string): string {
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
