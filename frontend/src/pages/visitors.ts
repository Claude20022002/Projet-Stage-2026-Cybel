import { api } from "../api";
import { icons } from "../icons";
import { pushEvent } from "../state";
import type { FaceStatusEvent, VisitorPublic } from "../types";

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

export function renderFaceStatus(status: FaceStatusEvent | null, at: number | null, wsConnected: boolean): string {
  if (!wsConnected) {
    return `<p class="settings-hint">${icons.wifiOff("icon", 14)} Non connecté au kiosque — vérifiez <code>kiosk_backend_url</code> dans la config backend.</p>`;
  }
  const staleMs = at != null ? Date.now() - at : Infinity;
  if (!status || staleMs > 4000) {
    return `<p class="settings-hint">${icons.circleDot("icon", 10)} Aucun visage détecté actuellement.</p>`;
  }
  const confidencePct = Math.round(status.confidence * 100);
  if (status.matched && status.visitor) {
    return `<p class="settings-hint settings-hint--ok">${icons.users("icon", 14)} Visage détecté — reconnu : <strong>${escapeHtml(status.visitor.name)}</strong> (confiance ${confidencePct}%)</p>`;
  }
  return `<p class="settings-hint">${icons.alertTriangle("icon", 14)} Visage détecté — inconnu (confiance ${confidencePct}%)</p>`;
}

function renderVisitorRow(visitor: VisitorPublic): string {
  return `
    <div class="settings-info__row" data-visitor-row="${visitor.id}">
      <div>
        <dt>${escapeHtml(visitor.civility ? visitor.civility + " " + visitor.name : visitor.name)}</dt>
        <dd>Enrôlé le ${formatDate(visitor.enrolled_at)} · Dernière reconnaissance : ${formatDate(visitor.last_identified_at)}</dd>
      </div>
      <button class="btn btn--secondary btn--sm" type="button" data-delete-visitor="${visitor.id}">
        ${icons.trash("icon", 14)}
      </button>
    </div>
  `;
}

export function renderVisitorsPage(
  visitors: VisitorPublic[],
  faceStatus: FaceStatusEvent | null,
  faceStatusAt: number | null,
  wsConnected: boolean
): string {
  return `
    <div class="settings-page">
      <header class="settings-page__header">
        <h1>Visiteurs</h1>
        <p>Enrôlement et reconnaissance faciale (Phase 2 — jamais d'image transmise, uniquement des vecteurs)</p>
      </header>

      <section class="settings-card">
        <h2>${icons.users("icon", 18)} Nouvel enrôlement</h2>
        <div class="settings-field">
          <label for="visitor-name">Nom</label>
          <input id="visitor-name" class="settings-input" type="text" placeholder="Nom du visiteur" />
        </div>
        <div class="settings-field">
          <label for="visitor-civility">Civilité</label>
          <select id="visitor-civility" class="settings-select">
            <option value="">—</option>
            <option value="M.">M.</option>
            <option value="Mme">Mme</option>
          </select>
        </div>
        <button id="btn-trigger-enroll" class="btn btn--primary btn--with-icon" type="button">
          ${icons.users("icon", 16)}
          <span>Lancer l'enrôlement (15 s)</span>
        </button>
        <p class="settings-hint">Placez la personne face à la caméra (sommet de la tête du robot), à 2-3 m, pendant la fenêtre de 15 secondes.</p>
      </section>

      <section class="settings-card" id="visitors-live-status">
        <h2>${icons.crosshair("icon", 18)} Détection en direct</h2>
        <div id="visitors-live-status-body">${renderFaceStatus(faceStatus, faceStatusAt, wsConnected)}</div>
        <p class="settings-hint">Utile pour vérifier que le robot voit bien la personne, et qu'il la distingue correctement des autres visiteurs enrôlés.</p>
      </section>

      <section class="settings-card">
        <h2>${icons.hash("icon", 18)} Visiteurs enrôlés (${visitors.length})</h2>
        ${
          visitors.length
            ? `<dl class="settings-info">${visitors.map(renderVisitorRow).join("")}</dl>`
            : `<p class="settings-hint">Aucun visiteur enrôlé.</p>`
        }
      </section>
    </div>
  `;
}

export function bindVisitorsEvents(onRefresh: () => void): void {
  document.getElementById("btn-trigger-enroll")?.addEventListener("click", async () => {
    const nameInput = document.getElementById("visitor-name") as HTMLInputElement;
    const civilitySelect = document.getElementById("visitor-civility") as HTMLSelectElement;
    const name = nameInput.value.trim();
    if (!name) {
      pushEvent("Nom requis pour l'enrôlement");
      return;
    }
    try {
      const result = await api.triggerEnrollment(name, civilitySelect.value);
      if (result.ok) {
        pushEvent(`Enrôlement lancé pour « ${name} » — 15 s`);
        nameInput.value = "";
        window.setTimeout(onRefresh, 16000);
      } else {
        pushEvent(`Échec du déclenchement : ${result.error ?? "inconnu"}`);
      }
    } catch (err) {
      pushEvent(`Erreur enrôlement : ${(err as Error).message}`);
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-delete-visitor]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.deleteVisitor;
      if (!id) return;
      try {
        await api.deleteVisitor(id);
        pushEvent("Visiteur supprimé");
        onRefresh();
      } catch (err) {
        pushEvent(`Erreur suppression : ${(err as Error).message}`);
      }
    });
  });
}
