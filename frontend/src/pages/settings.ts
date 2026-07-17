import { api } from "../api";
import { icons } from "../icons";
import { pushEvent } from "../state";
import type { DiagnosticsSnapshot, RobotSettings } from "../types";

const GITHUB_REPO = "https://github.com/Claude20022002/Projet-Stage-2026-Cybel";
const GITHUB_DOCS_BRANCH = "main";

interface HelpLink {
  label: string;
  path: string;
  hint: string;
}

const HELP_LINKS: HelpLink[] = [
  {
    label: "Guide contrôleur — POI & visite",
    path: "docs/labo/GUIDE_CONTROLEUR_POI.md",
    hint: "Créer/synchroniser les POI, maintenir le parcours guidé",
  },
  {
    label: "Démarrage & dépannage",
    path: "docs/labo/DEMARRAGE_ET_DEPANNAGE.md",
    hint: "L'application ne démarre pas, backend en erreur…",
  },
  {
    label: "Guide terrain",
    path: "docs/labo/TERRAIN.md",
    hint: "Procédures sur site avec le robot",
  },
  {
    label: "Chatbot vocal",
    path: "docs/VOICE_CHATBOT.md",
    hint: "Commandes vocales, mot d'éveil, dialogue de visite",
  },
  {
    label: "Reconnaissance faciale",
    path: "docs/FACE_PRESENCE.md",
    hint: "Enrôlement, identification, détection de présence",
  },
  {
    label: "Synchronisation POI Sentrymove",
    path: "docs/SENTRYMOVE_POI_SYNC.md",
    hint: "Format des noms, procédure Deployment Tool → kiosque",
  },
];

function githubDocUrl(path: string): string {
  return `${GITHUB_REPO}/blob/${GITHUB_DOCS_BRANCH}/${path}`;
}

function renderHelpLinks(): string {
  return `
    <ul class="help-links">
      ${HELP_LINKS.map(
        (link) => `
        <li>
          <a href="${githubDocUrl(link.path)}" target="_blank" rel="noopener">${link.label}</a>
          <span class="settings-hint">${link.hint}</span>
        </li>
      `
      ).join("")}
    </ul>
  `;
}

const SPEED_LABELS = { low: "Lente (0.3 m/s)", medium: "Moyenne (0.5 m/s)", high: "Rapide (0.8 m/s)" };
const TRAVEL_LABELS = {
  safety: "Sécurité — évitement large",
  balance: "Équilibre — évitement modéré",
  efficiency: "Efficacité — couloirs étroits",
};

function diagBadge(ok: boolean): string {
  return `<span class="diag-badge ${ok ? "diag-badge--ok" : "diag-badge--fail"}">${ok ? "OK" : "KO"}</span>`;
}

function renderDiagnostics(diag: DiagnosticsSnapshot | null): string {
  if (!diag) {
    return `<p class="settings-hint">Diagnostic indisponible.</p>`;
  }
  const rosAge =
    diag.rosbridge.last_message_age_s != null
      ? `${diag.rosbridge.last_message_age_s}s`
      : "—";
  return `
    <dl class="settings-info settings-info--diag">
      <div>${diagBadge(diag.overall_ok)}<dt>État global</dt><dd>${diag.overall_ok ? "Opérationnel" : "Problème détecté"}</dd></div>
      <div>${diagBadge(!!diag.rosbridge.ok)}<dt>ROSBridge</dt><dd>${diag.rosbridge.host ?? "—"} · dernier msg ${rosAge}</dd></div>
      <div>${diagBadge(!!diag.mqtt.ok)}<dt>MQTT</dt><dd>${diag.mqtt.active ? "Connecté" : diag.mqtt.enabled ? "Inactif" : "Désactivé"}</dd></div>
      <div>${diagBadge(!!diag.adb_tts.ok)}<dt>ADB TTS</dt><dd>${diag.adb_tts.configured_serial || "—"}</dd></div>
      <div>${diagBadge(!!diag.persistence.ok)}<dt>Persistance</dt><dd>${diag.persistence.backend} · ${diag.persistence.data_dir}</dd></div>
    </dl>
    <button id="btn-refresh-diagnostics" class="btn btn--secondary btn--sm" type="button">Actualiser</button>
  `;
}

export function renderSettingsPage(
  settings: RobotSettings | null,
  diagnostics: DiagnosticsSnapshot | null = null,
  kioskConfig: Record<string, unknown> | null = null
): string {
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

      <section class="settings-card">
        <h2>${icons.settings("icon", 18)} Kiosque visiteur</h2>
        <div class="settings-field">
          <label for="kiosk-org-fr">Nom organisation (FR)</label>
          <input id="kiosk-org-fr" class="settings-input" type="text" value="${String(kioskConfig?.organization_name_fr ?? "")}" />
        </div>
        <div class="settings-field">
          <label for="kiosk-welcome-fr">Message d'accueil (FR)</label>
          <textarea id="kiosk-welcome-fr" class="settings-textarea" rows="3">${String(kioskConfig?.welcome_message_fr ?? "")}</textarea>
        </div>
        <div class="settings-field">
          <label for="kiosk-logo">URL logo</label>
          <input id="kiosk-logo" class="settings-input" type="text" value="${String(kioskConfig?.logo_url ?? "/kiosk/logo.svg")}" />
        </div>
        <button id="btn-save-kiosk" class="btn btn--secondary btn--with-icon" type="button">
          ${icons.settings("icon", 16)}
          <span>Enregistrer le kiosque</span>
        </button>
      </section>

      <section class="settings-card" id="settings-diagnostics">
        <h2>${icons.alertTriangle("icon", 18)} Diagnostic</h2>
        ${renderDiagnostics(diagnostics)}
      </section>

      <section class="settings-card">
        <h2>${icons.message("icon", 18)} Aide contrôleur</h2>
        <p class="settings-hint">Documentation du projet sur GitHub — ouvre dans un nouvel onglet.</p>
        ${renderHelpLinks()}
      </section>
    </div>
  `;
}

export function bindSettingsEvents(onSaved: () => void, onRefreshDiagnostics?: () => void): void {
  document.getElementById("btn-refresh-diagnostics")?.addEventListener("click", () => {
    onRefreshDiagnostics?.();
  });

  document.getElementById("btn-save-kiosk")?.addEventListener("click", async () => {
    const orgFr = (document.getElementById("kiosk-org-fr") as HTMLInputElement).value.trim();
    const welcomeFr = (document.getElementById("kiosk-welcome-fr") as HTMLTextAreaElement).value.trim();
    const logoUrl = (document.getElementById("kiosk-logo") as HTMLInputElement).value.trim();
    try {
      await api.updateKioskConfig({
        organization_name_fr: orgFr,
        welcome_message_fr: welcomeFr,
        logo_url: logoUrl || "/kiosk/logo.svg",
      });
      pushEvent("Configuration kiosque enregistrée");
      onSaved();
    } catch (err) {
      pushEvent(`Erreur kiosque : ${(err as Error).message}`);
    }
  });

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