import { api } from "./api";
import { t } from "./i18n";
import type { FaqEntry, Lang, ReceptionAction } from "./types";

const ICONS: Record<string, string> = {
  "hand-wave": "👋",
  "map-pin": "📍",
  navigation: "🧭",
  clock: "⏰",
  plug: "🔌",
  route: "🗺️",
  message: "💬",
  stop: "⏹️",
  circle: "●",
};

let lang: Lang = "fr";
let screen: "home" | "info" = "home";
let actions: ReceptionAction[] = [];
let faq: FaqEntry[] = [];
let openFaqId: string | null = null;
let busy = false;
let message = "";
let toastTimer: number | null = null;

function tr() {
  return t[lang];
}

function showToast(text: string): void {
  message = text;
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    message = "";
    toastTimer = null;
    render();
  }, 3000);
}

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="kiosk">
      <header class="kiosk__header">
        <div class="kiosk__brand">
          <span class="kiosk__logo">CYBEL</span>
          <span class="kiosk__title">${tr().title}</span>
        </div>
        <button id="btn-lang" class="kiosk__lang" type="button">${tr().langToggle}</button>
      </header>
      ${screen === "home" ? renderHome() : renderInfo()}
      ${message ? `<div class="kiosk__toast">${message}</div>` : ""}
    </div>
  `;

  bindEvents();
}

function renderHome(): string {
  const visitorActions = actions.filter((a) => a.category !== "maintenance");
  return `
    <main class="kiosk__main">
      <p class="kiosk__subtitle">${tr().subtitle}</p>
      <div class="kiosk__grid">
        ${visitorActions
          .map((a) => {
            const label = lang === "en" ? a.label_en ?? a.label : a.label;
            return `
              <button class="tile" data-action="${a.id}" type="button" ${busy ? "disabled" : ""}>
                <span class="tile__icon">${ICONS[a.icon] ?? ICONS.circle}</span>
                <span class="tile__label">${label}</span>
              </button>
            `;
          })
          .join("")}
        <button class="tile tile--info" data-screen="info" type="button">
          <span class="tile__icon">ℹ️</span>
          <span class="tile__label">${tr().info}</span>
        </button>
      </div>
    </main>
  `;
}

function renderInfo(): string {
  return `
    <main class="kiosk__main">
      <div class="kiosk__info-header">
        <button id="btn-back" class="btn-back" type="button">← ${tr().back}</button>
        <h2>${tr().faqTitle}</h2>
      </div>
      <p class="kiosk__hint">${tr().faqHint}</p>
      <div class="kiosk__faq">
        ${faq
          .map((f) => {
            const question = lang === "en" ? f.question_en : f.question_fr;
            const answer = lang === "en" ? f.reponse_en : f.reponse_fr;
            const open = openFaqId === f.id;
            return `
              <div class="faq-item ${open ? "faq-item--open" : ""}">
                <button class="faq-item__question" data-faq="${f.id}" type="button">${question}</button>
                ${open ? `<p class="faq-item__answer">${answer}</p>` : ""}
              </div>
            `;
          })
          .join("")}
      </div>
    </main>
  `;
}

function bindEvents(): void {
  document.getElementById("btn-lang")?.addEventListener("click", () => {
    lang = lang === "fr" ? "en" : "fr";
    render();
  });

  document.getElementById("btn-back")?.addEventListener("click", () => {
    screen = "home";
    openFaqId = null;
    render();
  });

  document.querySelectorAll<HTMLElement>("[data-screen]").forEach((el) => {
    el.addEventListener("click", () => {
      screen = el.dataset.screen as "home" | "info";
      render();
    });
  });

  document.querySelectorAll<HTMLElement>("[data-action]").forEach((el) => {
    el.addEventListener("click", async () => {
      const actionId = el.dataset.action;
      if (!actionId || busy) return;
      busy = true;
      render();
      try {
        await api.executeAction(actionId, lang);
        showToast(tr().actionDone);
      } catch {
        showToast(tr().actionError);
      } finally {
        busy = false;
        render();
      }
    });
  });

  document.querySelectorAll<HTMLElement>("[data-faq]").forEach((el) => {
    el.addEventListener("click", async () => {
      const faqId = el.dataset.faq;
      if (!faqId) return;
      const entry = faq.find((f) => f.id === faqId);
      if (!entry) return;

      if (openFaqId === faqId) {
        openFaqId = null;
        render();
        return;
      }

      openFaqId = faqId;
      render();

      const answer = lang === "en" ? entry.reponse_en : entry.reponse_fr;
      try {
        await api.speak(answer);
      } catch {
        showToast(tr().actionError);
      }
    });
  });
}

export async function initApp(): Promise<void> {
  render();
  try {
    [actions, faq] = await Promise.all([api.getActions(), api.getFaq()]);
  } catch {
    showToast(t.fr.actionError);
  }
  render();
}
