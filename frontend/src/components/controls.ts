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
        <button class="dpad__btn dpad__btn--up" data-move="forward" type="button" title="Avancer">▲</button>
        <button class="dpad__btn dpad__btn--left" data-move="left" type="button" title="Gauche">◀</button>
        <button class="dpad__btn dpad__btn--stop" data-move="stop" type="button" title="Stop">■</button>
        <button class="dpad__btn dpad__btn--right" data-move="right" type="button" title="Droite">▶</button>
        <button class="dpad__btn dpad__btn--down" data-move="backward" type="button" title="Reculer">▼</button>
      </div>

      <div class="controls-panel__actions">
        <button id="btn-stop" class="btn btn--secondary" type="button">Arrêt</button>
        ${
          softEstop
            ? '<button id="btn-release-estop" class="btn btn--warning" type="button">Relâcher E-Stop</button>'
            : '<button id="btn-estop" class="btn btn--danger" type="button">E-STOP</button>'
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
