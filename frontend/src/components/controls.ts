import { icons } from "../icons";

export function renderControls(manualMode: boolean, softEstop: boolean): string {
  return `
    <section class="controls-panel">
      <div class="controls-panel__section">
        <h3>Téléopération</h3>
        <label class="toggle">
          <input id="toggle-manual" type="checkbox" ${manualMode ? "checked" : ""} />
          <span class="toggle__track"></span>
          <span class="toggle__label">Mode manuel</span>
        </label>
        <p class="controls-panel__hint">
          Activez le mode manuel pour piloter le robot à la main.
        </p>
      </div>

      <div class="controls-panel__dpad ${manualMode ? "" : "controls-panel__dpad--disabled"}">
        <button class="dpad__btn dpad__btn--up" data-move="forward" type="button" title="Avancer">
          ${icons.arrowUp("icon", 20)}
        </button>
        <button class="dpad__btn dpad__btn--left" data-move="left" type="button" title="Gauche">
          ${icons.arrowLeft("icon", 20)}
        </button>
        <button class="dpad__btn dpad__btn--stop" data-move="stop" type="button" title="Stop">
          ${icons.square("icon", 16)}
        </button>
        <button class="dpad__btn dpad__btn--right" data-move="right" type="button" title="Droite">
          ${icons.arrowRight("icon", 20)}
        </button>
        <button class="dpad__btn dpad__btn--down" data-move="backward" type="button" title="Reculer">
          ${icons.arrowDown("icon", 20)}
        </button>
      </div>

      <div class="controls-panel__actions">
        <button id="btn-stop" class="btn btn--secondary btn--with-icon" type="button">
          ${icons.square("icon", 14)}
          <span>Arrêt</span>
        </button>
        ${
          softEstop
            ? `<button id="btn-release-estop" class="btn btn--warning btn--with-icon" type="button">
                ${icons.alertTriangle("icon", 16)}
                <span>Relâcher E-Stop</span>
              </button>`
            : `<button id="btn-estop" class="btn btn--danger btn--with-icon" type="button">
                ${icons.octagon("icon", 16)}
                <span>E-STOP</span>
              </button>`
        }
      </div>

      <div class="events-log" id="events-log"></div>
    </section>
  `;
}

export function renderEventsLog(events: string[]): string {
  if (!events.length) {
    return '<p class="events-log__empty">Aucun événement récent</p>';
  }
  return events.map((e) => `<p class="events-log__item">${e}</p>`).join("");
}
