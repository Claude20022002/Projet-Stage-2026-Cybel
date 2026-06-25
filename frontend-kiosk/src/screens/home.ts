import { pointIcon, t } from "../i18n";
import type { KioskConfig, KioskDestination, Lang, LabTourInfo, ReceptionAction } from "../types";

export function renderStandby(lang: Lang, config: KioskConfig | null): string {
  const labels = t[lang];
  const org = config
    ? lang === "en"
      ? config.organization_name_en
      : config.organization_name_fr
    : "CYBEL";
  const logo = config?.logo_url || "/kiosk/logo.svg";

  return `
    <main class="screen screen--standby" id="screen-standby">
      <div class="standby__pulse" aria-hidden="true"></div>
      <img class="standby__logo" src="${logo}" alt="${org}" width="140" height="140" />
      <h1 class="standby__org">${org}</h1>
      <p class="standby__role">${labels.standbyWelcome}</p>
      <p class="standby__cta">${labels.standbyTap}</p>
    </main>
  `;
}

export function renderWelcome(
  lang: Lang,
  config: KioskConfig | null,
  tour: LabTourInfo | null,
  featured: KioskDestination[],
  receptionActions: ReceptionAction[],
  busy: boolean
): string {
  const labels = t[lang];
  const org = config
    ? lang === "en"
      ? config.organization_name_en
      : config.organization_name_fr
    : tourTitle(tour, lang);
  const welcome = config
    ? lang === "en"
      ? config.welcome_message_en
      : config.welcome_message_fr
    : tourSubtitle(tour, lang);
  const logo = config?.logo_url || "/kiosk/logo.svg";
  const stops = tour?.stops ?? [];

  return `
    <main class="screen screen--welcome">
      <section class="welcome-hero">
        <img class="welcome-hero__logo" src="${logo}" alt="${org}" width="96" height="96" />
        <p class="welcome-hero__org">${org}</p>
        <h1 class="welcome-hero__title">${welcome}</h1>
        <p class="welcome-hero__subtitle">${labels.chooseMode}</p>
      </section>

      ${
        featured.length
          ? `
        <section class="featured">
          <h2 class="featured__title">${labels.featuredTitle}</h2>
          <div class="featured__row">
            ${featured
              .map(
                (dest) => `
              <button class="featured-chip" type="button" data-dest="${dest.name}" ${busy ? "disabled" : ""}>
                <span aria-hidden="true">${pointIcon(dest.type)}</span>
                <span>${dest.name}</span>
              </button>
            `
              )
              .join("")}
          </div>
        </section>
      `
          : ""
      }

      ${
        receptionActions.length
          ? `
        <section class="reception-quick">
          <h2 class="reception-quick__title">${labels.receptionTitle}</h2>
          <div class="reception-quick__row">
            ${receptionActions
              .map(
                (action) => `
              <button class="reception-chip" type="button" data-action="${action.id}" ${busy ? "disabled" : ""}>
                <span>${lang === "en" ? action.label_en || action.label : action.label}</span>
              </button>
            `
              )
              .join("")}
          </div>
        </section>
      `
          : ""
      }

      <section class="action-grid">
        <button id="btn-mode-dest" class="action-card action-card--primary" type="button" ${busy ? "disabled" : ""}>
          <span class="action-card__icon" aria-hidden="true">📍</span>
          <strong class="action-card__title">${labels.modeDestinations}</strong>
          <span class="action-card__hint">${labels.modeDestinationsHint}</span>
        </button>
        <button id="btn-mode-tour" class="action-card" type="button" ${busy ? "disabled" : ""}>
          <span class="action-card__icon" aria-hidden="true">🗺️</span>
          <strong class="action-card__title">${labels.modeTour}</strong>
          <span class="action-card__hint">${labels.modeTourHint}</span>
        </button>
        <button id="btn-assistance" class="action-card action-card--ghost" type="button" ${busy ? "disabled" : ""}>
          <span class="action-card__icon" aria-hidden="true">🙋</span>
          <strong class="action-card__title">${labels.assistance}</strong>
          <span class="action-card__hint">${labels.assistanceHint}</span>
        </button>
      </section>

      ${
        stops.length
          ? `
        <section class="route-preview">
          <h2 class="route-preview__title">${labels.stopsPreview}</h2>
          <ol class="route-preview__list">
            ${stops
              .slice(0, 5)
              .map(
                (stop, index) => `
              <li class="route-preview__item">
                <span class="route-preview__num">${index + 1}</span>
                <div>
                  <strong>${lang === "en" ? stop.equipment_en : stop.equipment_fr}</strong>
                  <span>${lang === "en" ? stop.name_en : stop.name_fr}</span>
                </div>
              </li>
            `
              )
              .join("")}
            ${stops.length > 5 ? `<li class="route-preview__more">+${stops.length - 5}</li>` : ""}
          </ol>
        </section>
      `
          : ""
      }
    </main>
  `;
}

export function renderDestinations(
  lang: Lang,
  destinations: KioskDestination[],
  searchQuery: string,
  busy: boolean
): string {
  const labels = t[lang];
  const filtered = filterDestinations(destinations, searchQuery);

  if (!destinations.length) {
    return `
      <main class="screen screen--destinations">
        <section class="empty-state">
          <p>${labels.actionError}</p>
          <button id="btn-back-welcome" class="btn-secondary" type="button">${labels.back}</button>
        </section>
      </main>
    `;
  }

  return `
    <main class="screen screen--destinations">
      <div class="destinations-head">
        <h1 class="destinations-head__title">${labels.destinationsTitle}</h1>
        <p class="destinations-head__hint">${labels.destinationsHint}</p>
        <label class="search">
          <span class="search__icon" aria-hidden="true">🔍</span>
          <input
            id="dest-search"
            class="search__input"
            type="search"
            inputmode="search"
            autocomplete="off"
            placeholder="${labels.searchPlaceholder}"
            value="${escapeHtml(searchQuery)}"
            ${busy ? "disabled" : ""}
          />
        </label>
      </div>

      <div class="destinations-grid" role="list">
        ${
          filtered.length
            ? filtered
                .map(
                  (dest) => `
            <button
              class="dest-card"
              type="button"
              role="listitem"
              data-dest="${dest.name}"
              ${busy ? "disabled" : ""}
            >
              <span class="dest-card__icon" aria-hidden="true">${pointIcon(dest.type)}</span>
              <span class="dest-card__name">${dest.name}</span>
            </button>
          `
                )
                .join("")
            : `<p class="destinations-empty">${labels.searchEmpty}</p>`
        }
      </div>

      <footer class="screen-footer">
        <button id="btn-back-welcome" class="btn-secondary" type="button" ${busy ? "disabled" : ""}>
          ${labels.homeBack}
        </button>
      </footer>
    </main>
  `;
}

export function renderTraveling(
  lang: Lang,
  label: string,
  statusLabel: string,
  mode: "destination" | "tour",
  tourProgress?: { current: number; total: number; phase: string },
  speechCaption?: string
): string {
  const labels = t[lang];
  const progress =
    mode === "tour" && tourProgress && tourProgress.total > 0
      ? Math.max(0, ((tourProgress.current + 1) / tourProgress.total) * 100)
      : null;

  return `
    <main class="screen screen--traveling">
      <div class="traveling__anim" aria-hidden="true">
        <div class="traveling__robot">🤖</div>
        <div class="traveling__path"></div>
      </div>

      <div class="traveling__badge">${mode === "tour" ? labels.tourRunning : labels.destRunning}</div>

      ${
        progress !== null
          ? `
        <p class="traveling__step">
          ${labels.step} <strong>${Math.max(tourProgress!.current + 1, 1)}</strong>
          ${labels.of} <strong>${tourProgress!.total}</strong>
        </p>
        <div class="progress" aria-hidden="true">
          <div class="progress__bar" style="width: ${progress}%"></div>
        </div>
      `
          : `<p class="traveling__status">${statusLabel}</p>`
      }

      <section class="traveling__focus">
        ${tourProgress?.phase ? `<span class="traveling__phase">${tourProgress.phase}</span>` : ""}
        <p class="traveling__label">${labels.travelingTo}</p>
        <h2 class="traveling__destination">${label}</h2>
        ${
          speechCaption
            ? `<blockquote class="traveling__speech" aria-live="polite">${escapeHtml(speechCaption)}</blockquote>`
            : ""
        }
        <p class="traveling__follow">${mode === "tour" ? labels.followRobot : labels.destFollow}</p>
      </section>

      ${mode === "tour"
        ? `<button id="btn-stop" class="btn-danger" type="button">${labels.stopTour}</button>`
        : `<button id="btn-stop" class="btn-danger" type="button">${labels.stopTour}</button>`}
    </main>
  `;
}

export function renderCompleted(
  lang: Lang,
  mode: "destination" | "tour",
  failed: boolean,
  tourState?: string,
  error?: string | null
): string {
  const labels = t[lang];

  if (mode === "destination") {
    return `
      <main class="screen screen--arrival">
        <div class="arrival__icon" aria-hidden="true">${failed ? "⚠️" : "✅"}</div>
        <h1 class="arrival__title">${failed ? labels.destError : labels.destCompleted}</h1>
        <p class="arrival__hint">${failed ? labels.destErrorHint : labels.destCompletedHint}</p>
        <button id="btn-restart" class="btn-primary" type="button">${labels.newDestination}</button>
      </main>
    `;
  }

  let title: string = labels.tourCompleted;
  let hint: string = labels.completedHint;
  if (tourState === "stopped") {
    title = labels.tourStopped;
    hint = labels.stoppedHint;
  } else if (tourState === "error") {
    title = labels.tourError;
    hint = error || labels.errorHint;
  }

  return `
    <main class="screen screen--arrival">
      <div class="arrival__icon" aria-hidden="true">${tourState === "error" ? "⚠️" : "✅"}</div>
      <h1 class="arrival__title">${title}</h1>
      <p class="arrival__hint">${hint}</p>
      <button id="btn-restart" class="btn-primary" type="button">${labels.newTour}</button>
    </main>
  `;
}

function tourTitle(tour: LabTourInfo | null, lang: Lang): string {
  if (!tour) return t[lang].title;
  return lang === "en" ? tour.title_en : tour.title_fr;
}

function tourSubtitle(tour: LabTourInfo | null, lang: Lang): string {
  if (!tour) return t[lang].subtitle;
  return lang === "en" ? tour.subtitle_en : tour.subtitle_fr;
}

export function filterDestinations(
  destinations: KioskDestination[],
  query: string
): KioskDestination[] {
  const q = query.trim().toLowerCase();
  if (!q) return destinations;
  return destinations.filter((d) => d.name.toLowerCase().includes(q));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
