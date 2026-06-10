import { icons } from "../icons";
import type { ReceptionAction, SpeechStatus } from "../types";

const ICON_MAP: Record<string, (cls?: string, size?: number) => string> = {
  "hand-wave": icons.users,
  "map-pin": icons.mapPin,
  navigation: icons.navigation,
  clock: icons.circleDot,
  plug: icons.plug,
  route: icons.route,
  message: icons.message,
  stop: icons.square,
};

function actionIcon(name: string): string {
  const fn = ICON_MAP[name] ?? icons.circleDot;
  return fn("icon", 16);
}

export function renderReceptionPanel(
  actions: ReceptionAction[],
  voiceListening: boolean,
  speech: SpeechStatus | null
): string {
  const speaking = speech?.speaking ?? false;
  const accueil = actions.filter((a) => a.category === "accueil");
  const nav = actions.filter((a) => a.category === "navigation");
  const other = actions.filter(
    (a) => !["accueil", "navigation"].includes(a.category)
  );

  const renderGroup = (title: string, items: ReceptionAction[]) =>
    items.length
      ? `
      <div class="reception-group">
        <h3 class="reception-group__title">${title}</h3>
        <div class="reception-group__list">
          ${items
            .map(
              (a) => `
            <button class="reception-action" data-action="${a.id}" type="button" title="${a.description}">
              <span class="reception-action__icon">${actionIcon(a.icon)}</span>
              <span class="reception-action__label">${a.label}</span>
            </button>
          `
            )
            .join("")}
        </div>
      </div>
    `
      : "";

  return `
    <section class="reception-panel">
      <div class="reception-panel__header">
        <h2>Accueil</h2>
        <button
          id="btn-voice"
          class="btn btn--voice ${voiceListening ? "btn--voice-active" : ""}"
          type="button"
          title="Commande vocale"
        >
          ${voiceListening ? icons.micOff("icon", 18) : icons.mic("icon", 18)}
          <span>${voiceListening ? "Écoute…" : "Vocal"}</span>
        </button>
      </div>
      <p class="reception-panel__hint">
        Actions prédéfinies ou commandes : « va à l'accueil », « accueillir », « retour pile »
      </p>
      ${renderGroup("Réception", accueil)}
      ${renderGroup("Navigation", nav)}
      ${renderGroup("Autres", other)}

      <div class="speech-box">
        <h3 class="reception-group__title">Synthèse vocale</h3>
        <textarea
          id="speech-text"
          class="speech-box__input"
          rows="2"
          placeholder="Message à faire dire au robot…"
        >Bienvenue ! Comment puis-je vous aider ?</textarea>
        <div class="speech-box__actions">
          <button id="btn-speak" class="btn btn--primary btn--with-icon btn--block" type="button" ${speaking ? "disabled" : ""}>
            ${icons.volume("icon", 16)}
            <span>${speaking ? "En cours…" : "Faire parler"}</span>
          </button>
          <button id="btn-stop-speech" class="btn btn--ghost btn--with-icon" type="button">
            ${icons.square("icon", 14)}
            <span>Stop parole</span>
          </button>
        </div>
        ${
          speech?.last_text
            ? `<p class="speech-box__status">Dernier : « ${speech.last_text} »${speech.last_method ? ` · ${speech.last_method}` : ""}</p>`
            : ""
        }
      </div>
    </section>
  `;
}
