import { api } from "../api";
import { icons } from "../icons";
import { pushEvent } from "../state";
import type { RobotSettings } from "../types";

const SPEED_LABELS = { low: "Lente (0.3 m/s)", medium: "Moyenne (0.5 m/s)", high: "Rapide (0.8 m/s)" };
const TRAVEL_LABELS = {
  safety: "Sécurité — évitement large",
  balance: "Équilibre — évitement modéré",
  efficiency: "Efficacité — couloirs étroits",
};

export function renderSettingsPage(settings: RobotSettings | null): string {
  const s = settings ?? {
    speed_gear: "medium" as const,
    travel_mode: "balance" as const,
    directional_mode: "joystick" as const,
    robot_host: "10.42.0.1",
    mock_mode: true,
  };

  return `
    <div class="settings-page">
      <header class="settings-page__header">
        <h1>Paramètres</h1>
        <p>Configuration du robot et de la navigation</p>
      </header>

      <section class="settings-card">
        <h2>${icons.settings("icon", 18)} Déplacement</h2>
        <div class="settings-field">
          <label for="speed-gear">Vitesse de navigation</label>
          <select id="speed-gear" class="settings-select">
            ${(["low", "medium", "high"] as const)
              .map(
                (v) =>
                  `<option value="${v}" ${s.speed_gear === v ? "selected" : ""}>${SPEED_LABELS[v]}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="settings-field">
          <label for="travel-mode">Mode de déplacement</label>
          <select id="travel-mode" class="settings-select">
            ${(["safety", "balance", "efficiency"] as const)
              .map(
                (v) =>
                  `<option value="${v}" ${s.travel_mode === v ? "selected" : ""}>${TRAVEL_LABELS[v]}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="settings-field">
          <label for="directional-mode">Contrôle directionnel</label>
          <select id="directional-mode" class="settings-select">
            <option value="arrows" ${s.directional_mode === "arrows" ? "selected" : ""}>Flèches directionnelles</option>
            <option value="joystick" ${s.directional_mode === "joystick" ? "selected" : ""}>Joystick virtuel</option>
          </select>
        </div>
        <button id="btn-save-settings" class="btn btn--primary btn--with-icon" type="button">
          ${icons.settings("icon", 16)}
          <span>Enregistrer</span>
        </button>
      </section>

      <section class="settings-card">
        <h2>${icons.wifi("icon", 18)} Connexion</h2>
        <dl class="settings-info">
          <div><dt>Hôte robot</dt><dd>${s.robot_host}</dd></div>
          <div><dt>Mode</dt><dd>${s.mock_mode ? "Simulation" : "Robot réel"}</dd></div>
          <div><dt>Interface usine</dt><dd><a href="http://${s.robot_host}:8082" target="_blank" rel="noopener">Déploiement :8082</a></dd></div>
        </dl>
      </section>
    </div>
  `;
}

export function bindSettingsEvents(onSaved: () => void): void {
  document.getElementById("btn-save-settings")?.addEventListener("click", async () => {
    const speed = (document.getElementById("speed-gear") as HTMLSelectElement).value;
    const travel = (document.getElementById("travel-mode") as HTMLSelectElement).value;
    const directional = (document.getElementById("directional-mode") as HTMLSelectElement).value;

    try {
      await api.updateSettings({
        speed_gear: speed as RobotSettings["speed_gear"],
        travel_mode: travel as RobotSettings["travel_mode"],
        directional_mode: directional as RobotSettings["directional_mode"],
        robot_host: "10.42.0.1",
        mock_mode: true,
      });
      pushEvent("Paramètres enregistrés");
      onSaved();
    } catch (err) {
      pushEvent(`Erreur paramètres : ${(err as Error).message}`);
    }
  });
}
