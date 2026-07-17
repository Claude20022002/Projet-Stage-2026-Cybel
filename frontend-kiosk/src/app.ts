import { api } from "./api";
import { renderStatusBar } from "./components/statusBar";
import { phaseLabel, t } from "./i18n";
import {
  renderCompleted,
  renderDestinations,
  renderStandby,
  renderTraveling,
  renderVoiceOverlay,
  renderWelcome,
} from "./screens/home";
import { connectKioskTelemetry } from "./telemetry";
import type {
  ActiveFlow,
  DetectedPerson,
  KioskConfig,
  KioskDestination,
  Lang,
  LabTourInfo,
  ReceptionAction,
  RobotStatus,
  SpeechStatus,
  TourScreen,
  TourStatus,
  VisitorPublic,
  VoiceState,
} from "./types";

/** Pont natif exposé par l'app Android hôte (CybelVisitorKioskTest) pour la
 * reconnaissance vocale — absent dans un navigateur classique. */
interface CybelVoiceBridge {
  startListening: (lang: string) => void;
  isAvailable?: () => boolean;
}
declare global {
  interface Window {
    CybelVoice?: CybelVoiceBridge;
    __cybelVoiceResult?: (transcript: string, ok: boolean) => void;
    __cybelWakeDetected?: () => void;
  }
}

let lang: Lang = "fr";
let screen: TourScreen = "welcome";
let activeFlow: ActiveFlow = null;
let tour: LabTourInfo | null = null;
let status: TourStatus | null = null;
let config: KioskConfig | null = null;
let destinations: KioskDestination[] = [];
let featuredDestinations: KioskDestination[] = [];
let receptionActions: ReceptionAction[] = [];
let selectedDestination: string | null = null;
let robotStatus: RobotStatus | null = null;
let speechStatus: SpeechStatus | null = null;
let searchQuery = "";
let busy = false;
let message = "";
let clockTimer: number | null = null;
let standbyTimer: number | null = null;
let toastTimer: number | null = null;
let sawNavigating = false;
let lastInteractionAt = Date.now();
let detectedPeople: DetectedPerson[] = [];
/** Cooldown partagé entre les deux déclencheurs d'accueil (reconnaissance
 * faciale caméra tablette, présence caméra châssis) — évite un double accueil
 * si les deux systèmes détectent la même personne à quelques instants d'écart. */
let lastGreetAt = 0;
let identifiedVisitor: { visitor: VisitorPublic; at: number } | null = null;
const VISITOR_GREETING_TTL_MS = 120_000;
/** Micro état de dialogue : la question en attente d'une réponse oui/non ou
 * d'un choix de visite, posée après l'accueil d'un visiteur reconnu. Éphémère
 * (perdu au rechargement) — un nouveau visiteur n'a pas besoin d'un état persistant. */
let pendingQuestion: "tour_offer" | "tour_type" | null = null;
const YES_WORDS = ["oui", "ouais", "d'accord", "daccord", "yes"];
const NO_WORDS = ["non", "no"];
const FULL_TOUR_WORDS = ["complet", "complete", "guidee", "guidée", "tout", "entiere", "entière"];
let voiceState: VoiceState = "idle";
let voiceTranscript = "";
let voiceReply = "";
let voiceTimer: number | null = null;

function tr() {
  return t[lang];
}

function resetStandbyTimer(): void {
  lastInteractionAt = Date.now();
  if (standbyTimer !== null) window.clearTimeout(standbyTimer);
  const timeout = (config?.standby_timeout_seconds ?? 90) * 1000;
  if (timeout <= 0 || screen === "running" || screen === "dest_running") return;
  standbyTimer = window.setTimeout(() => {
    if (Date.now() - lastInteractionAt >= timeout - 500) {
      screen = "standby";
      render();
    }
  }, timeout);
}

function showToast(text: string): void {
  message = text;
  if (toastTimer !== null) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    message = "";
    toastTimer = null;
    render();
  }, 4000);
}

function pickReceptionActions(
  all: ReceptionAction[],
  cfg: KioskConfig | null
): ReceptionAction[] {
  const ids = cfg?.reception_actions ?? [];
  const picked = ids
    .map((id) => all.find((a) => a.id === id))
    .filter((a): a is ReceptionAction => Boolean(a));
  if (picked.length) return picked.slice(0, 4);
  return all.filter((a) => a.category === "accueil" && a.id !== "guided_tour").slice(0, 3);
}

function tourSpeechCaption(): string | undefined {
  if (!status || activeFlow !== "tour" || screen !== "running") return undefined;
  if (status.phase === "presenting" || status.phase === "intro" || status.phase === "outro") {
    if (status.message && status.message.length > 12) return status.message;
    if (speechStatus?.speaking && speechStatus.last_text) return speechStatus.last_text;
  }
  if (speechStatus?.speaking && speechStatus.last_text) return speechStatus.last_text;
  return undefined;
}

function pickFeatured(
  all: KioskDestination[],
  cfg: KioskConfig | null
): KioskDestination[] {
  const names = cfg?.featured_destinations ?? [];
  const picked = names
    .map((name) => all.find((d) => d.name === name))
    .filter((d): d is KioskDestination => Boolean(d));
  if (picked.length >= 4) return picked.slice(0, 4);
  const rest = all.filter((d) => !picked.some((p) => p.name === d.name));
  return [...picked, ...rest].slice(0, 4);
}

function syncScreenFromTourStatus(): void {
  if (!status || activeFlow !== "tour") return;
  if (status.state === "running") {
    screen = "running";
    return;
  }
  if (status.state === "completed" || status.state === "stopped" || status.state === "error") {
    if (screen === "running") screen = "completed";
  }
}

function syncScreenFromRobotStatus(): void {
  if (!robotStatus || activeFlow !== "destination" || screen !== "dest_running") return;
  if (robotStatus.nav_status === 602) sawNavigating = true;
  if (robotStatus.nav_status === 604) {
    screen = "completed";
    return;
  }
  if (sawNavigating && robotStatus.nav_status === 603) {
    screen = "completed";
  }
}

function personalizedGreeting(): string | null {
  if (!config?.face_recognition_enabled || !identifiedVisitor) return null;
  if (Date.now() - identifiedVisitor.at > VISITOR_GREETING_TTL_MS) return null;
  const { name, civility } = identifiedVisitor.visitor;
  if (lang === "en") return `Welcome back, ${name}!`;
  return `Bonjour ${civility ? civility + " " : ""}${name} !`;
}

/** Accueille et propose une visite — déclenché soit par la reconnaissance
 * faciale (caméra tablette, visiteur identifié par son nom), soit par la
 * détection de présence châssis (caméra robot, visiteur anonyme) : les deux
 * systèmes sont indépendants et appellent ce même point d'entrée, avec un
 * cooldown partagé pour ne saluer qu'une fois si les deux se déclenchent
 * à quelques instants d'écart. */
function tryGreetAndOfferTour(): void {
  if (!config) return;
  if (busy || activeFlow) return;
  if (pendingQuestion) return; // dialogue déjà en cours, ne pas l'interrompre
  if (screen !== "standby" && screen !== "welcome") return;
  const cooldownMs = (config.presence_cooldown_seconds ?? 90) * 1000;
  const now = Date.now();
  if (now - lastGreetAt < cooldownMs) return;
  const greeting =
    personalizedGreeting() ??
    (lang === "fr"
      ? config.welcome_message_fr || tr().presenceWelcome
      : config.welcome_message_en || tr().presenceWelcome);
  lastGreetAt = now;
  if (screen === "standby") {
    screen = "welcome";
  }
  showToast(personalizedGreeting() ?? tr().presenceDetected);
  pendingQuestion = "tour_offer";
  // Une seule phrase (pas deux appels api.say() séparés) pour éviter tout
  // risque de la seconde qui coupe/écrase la première dans la queue TTS.
  speakAndListen(`${greeting} ${tr().tourOfferQuestion}`);
}

function matchesAny(text: string, words: string[]): boolean {
  const normalized = text.toLowerCase();
  return words.some((w) => normalized.includes(w));
}

/** Estimation grossière du temps de parole (débit oral FR modéré, ~2,5 mots/s)
 * + marge fixe pour le démarrage du moteur TTS natif (broadcast shell, pas
 * instantané) — sert à ne relancer l'écoute qu'une fois la question terminée,
 * pour un dialogue enchaîné sans que le micro capte la voix du robot lui-même. */
function estimateSpeechDurationMs(text: string): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const speakMs = (words / 2.5) * 1000;
  return Math.max(1200, Math.min(8000, speakMs + 600));
}

/** Prononce une question puis relance automatiquement l'écoute du micro pour
 * la réponse — enchaîne le dialogue sans que le visiteur ait à retoucher
 * l'écran entre chaque tour de parole. */
function speakAndListen(text: string): void {
  voiceTranscript = "";
  voiceReply = text;
  voiceState = "listening";
  render();
  if (config?.presence_speak_welcome !== false) {
    void api.say(text).catch(() => undefined);
  }
  if (voiceTimer !== null) window.clearTimeout(voiceTimer);
  const delay = estimateSpeechDurationMs(text);
  voiceTimer = window.setTimeout(() => {
    if (voiceState !== "listening") return; // annulé/fermé entre-temps
    try {
      window.CybelVoice?.startListening(lang);
    } catch {
      voiceState = "idle";
      pendingQuestion = null;
      render();
      return;
    }
    // Garde-fou : si l'app native ne rappelle jamais, on ferme après 12 s
    // (même filet que startVoice()).
    if (voiceTimer !== null) window.clearTimeout(voiceTimer);
    voiceTimer = window.setTimeout(() => {
      if (voiceState === "listening") {
        voiceReply = tr().voiceError;
        voiceState = "answer";
        pendingQuestion = null;
        render();
      }
    }, 12000);
  }, delay);
}

/** Envoie un texte au NLU backend (commande/POI/FAQ) et applique le résultat
 * à l'écran — logique commune au flux vocal normal et au repli du dialogue
 * de proposition de visite (ex. si la réponse ne matche ni oui ni non, on la
 * traite comme une commande normale : elle contient peut-être déjà le nom
 * du point ou « visite guidée »). */
async function routeVoiceText(text: string): Promise<void> {
  voiceTranscript = text;
  voiceState = "processing";
  render();
  try {
    const result = await api.voice(text, lang);
    voiceReply = result.reply || tr().voiceError;
    voiceState = "answer";
    if (result.ok && result.kind === "navigation" && result.point) {
      activeFlow = "destination";
      selectedDestination = result.point;
      sawNavigating = false;
      screen = "dest_running";
      robotStatus = await api.getRobotStatus().catch(() => robotStatus);
      voiceState = "idle";
    } else if (result.ok && result.action === "guided_tour") {
      voiceState = "idle";
      activeFlow = "tour";
      screen = "running";
      status = await api.getTourStatus().catch(() => status);
    }
    render();
  } catch (err) {
    voiceReply = err instanceof Error ? err.message : tr().voiceError;
    voiceState = "answer";
    render();
  }
}

/** Interprète une réponse dans le mini-dialogue « proposition de visite »
 * déclenché par tryGreetAndOfferTour(). */
async function handlePendingAnswer(text: string): Promise<void> {
  const question = pendingQuestion;
  pendingQuestion = null;

  if (question === "tour_offer") {
    if (matchesAny(text, YES_WORDS)) {
      pendingQuestion = "tour_type";
      speakAndListen(tr().tourTypeQuestion);
      return;
    }
    if (matchesAny(text, NO_WORDS)) {
      const ack = tr().tourDeclined;
      voiceTranscript = text;
      voiceReply = ack;
      voiceState = "idle";
      if (config?.presence_speak_welcome !== false) void api.say(ack).catch(() => undefined);
      render();
      return;
    }
    // Ni oui ni non reconnu : peut-être une autre demande directe, on la
    // traite normalement plutôt que de bloquer sur une réponse incomprise.
    await routeVoiceText(text);
    return;
  }

  if (question === "tour_type") {
    if (matchesAny(text, FULL_TOUR_WORDS)) {
      await routeVoiceText("visite guidée");
      return;
    }
    // Une réponse à « quel point précis ? » est un nom de destination seul,
    // sans verbe de déplacement (« CNC routeur », pas « va au CNC routeur ») —
    // le NLU de navigation exige un verbe/« jusqu' », donc on résout plutôt
    // directement contre la liste des destinations connues (même mécanisme
    // que le clic sur une tuile de destination : nom exact, pas de texte libre).
    const resolved = await resolveDestinationByVoice(text);
    if (resolved) {
      await goToDestination(resolved);
      return;
    }
    // Aucun point reconnu : on retente via le NLU normal (action/FAQ possibles).
    await routeVoiceText(text);
    return;
  }
}

function normalizeForMatch(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Résout un texte prononcé vers un nom de destination connu (correspondance
 * approximative sur sous-chaîne, comme sdk/voice_commands.match_point_navigation
 * côté backend, mais ici contre la liste réellement affichable au kiosque). */
async function resolveDestinationByVoice(text: string): Promise<string | null> {
  const normalizedText = normalizeForMatch(text);
  if (!normalizedText) return null;
  try {
    const list = destinations.length ? destinations : await api.getDestinations();
    for (const dest of list) {
      const normalizedName = normalizeForMatch(dest.name);
      if (normalizedName && (normalizedText.includes(normalizedName) || normalizedName.includes(normalizedText))) {
        return dest.name;
      }
    }
  } catch {
    // ignore — repli sur le NLU normal dans l'appelant
  }
  return null;
}

function handlePresenceWelcome(): void {
  if (!config?.presence_welcome_enabled) return;
  const maxDist = config.presence_max_distance_m ?? 3.0;
  const nearby = detectedPeople.filter((p) => p.distance <= maxDist);
  if (!nearby.length) return;
  tryGreetAndOfferTour();
}

function startTelemetry(): void {
  connectKioskTelemetry({
    onRobotStatus: (robot) => {
      robotStatus = robot;
      if (activeFlow === "destination") syncScreenFromRobotStatus();
      if (
        screen === "running" ||
        screen === "dest_running" ||
        screen === "welcome" ||
        screen === "standby"
      ) {
        render();
      }
    },
    onSpeech: (speech) => {
      speechStatus = speech;
      if (screen === "running" || screen === "dest_running") render();
    },
    onTourStatus: (tourStatus) => {
      status = tourStatus;
      if (activeFlow === "tour") {
        syncScreenFromTourStatus();
        if (screen === "running" || screen === "completed") render();
      }
    },
    onPeople: (people) => {
      detectedPeople = people;
      handlePresenceWelcome();
    },
    onVisitorIdentified: (visitor) => {
      identifiedVisitor = { visitor, at: Date.now() };
      if (config?.face_recognition_enabled) tryGreetAndOfferTour();
    },
    onVoice: (event) => {
      // Diffusion serveur : utile si un autre client (ex. opérateur) parle au robot.
      // Le flux local (bouton micro) est déjà géré par onVoiceTranscript ; on ne
      // ré-affiche que si l'overlay n'est pas déjà actif localement.
      if (voiceState === "idle" && event.transcript) {
        voiceTranscript = event.transcript;
        voiceReply = event.reply;
        voiceState = "answer";
        render();
      }
    },
  });
}

function startClock(): void {
  if (clockTimer !== null) return;
  clockTimer = window.setInterval(() => {
    const el = document.getElementById("kiosk-clock");
    if (el) {
      el.textContent = new Date().toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-GB", {
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }, 30000);
}

function renderBody(): string {
  switch (screen) {
    case "standby":
      return renderStandby(lang, config);
    case "welcome":
      return renderWelcome(lang, config, tour, featuredDestinations, receptionActions, busy, voiceAvailable());
    case "destinations":
      return renderDestinations(lang, destinations, searchQuery, busy);
    case "dest_running":
      return renderTraveling(
        lang,
        selectedDestination || tr().destRunning,
        robotStatus?.nav_status_label || tr().destRunning,
        "destination"
      );
    case "running": {
      const current = status?.current_index ?? -1;
      const total = status?.total_stops ?? tour?.stops.length ?? 0;
      const equipment = status?.current_equipment || "…";
      const phase = status?.phase ? phaseLabel(status.phase, lang) : "";
      return renderTraveling(lang, equipment, status?.message || tr().tourRunning, "tour", {
        current,
        total,
        phase,
      }, tourSpeechCaption());
    }
    case "completed":
      if (activeFlow === "destination") {
        return renderCompleted(lang, "destination", robotStatus?.nav_status === 604);
      }
      return renderCompleted(lang, "tour", false, status?.state, status?.error);
    default:
      return renderWelcome(lang, config, tour, featuredDestinations, receptionActions, busy, voiceAvailable());
  }
}

function kioskVariantLabel(): string | undefined {
  if (!config) return undefined;
  const label =
    lang === "en"
      ? config.kiosk_variant_label_en
      : config.kiosk_variant_label_fr;
  return label?.trim() || undefined;
}

function render(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="kiosk" data-screen="${screen}">
      ${screen === "standby" ? "" : renderStatusBar(lang, robotStatus, speechStatus, busy, kioskVariantLabel())}
      ${renderBody()}
      ${renderVoiceOverlay(lang, voiceState, voiceTranscript, voiceReply)}
      ${message ? `<div class="kiosk-toast" role="status">${message}</div>` : ""}
    </div>
  `;

  bindEvents();
  resetStandbyTimer();
}

function voiceAvailable(): boolean {
  return typeof window.CybelVoice?.startListening === "function";
}

function bindEvents(): void {
  document.getElementById("btn-lang")?.addEventListener("click", () => {
    if (busy) return;
    touch();
    lang = lang === "fr" ? "en" : "fr";
    render();
  });

  document.getElementById("screen-standby")?.addEventListener("click", () => {
    touch();
    screen = "welcome";
    render();
  });

  document.getElementById("btn-mode-tour")?.addEventListener("click", () => void startTour());
  document.getElementById("btn-mode-dest")?.addEventListener("click", () => void openDestinations());
  document.getElementById("btn-assistance")?.addEventListener("click", () => void runAssistance());
  document.getElementById("btn-voice")?.addEventListener("click", () => startVoice());
  document.getElementById("btn-voice-close")?.addEventListener("click", () => closeVoice());

  document.getElementById("btn-back-welcome")?.addEventListener("click", () => {
    touch();
    screen = "welcome";
    activeFlow = null;
    searchQuery = "";
    render();
  });

  document.getElementById("dest-search")?.addEventListener("input", (event) => {
    touch();
    searchQuery = (event.target as HTMLInputElement).value;
    render();
    const input = document.getElementById("dest-search") as HTMLInputElement | null;
    if (input) {
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const actionId = button.dataset.action;
      if (actionId) void runReceptionAction(actionId);
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-dest]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.dest;
      if (name) void goToDestination(name);
    });
  });

  document.getElementById("btn-restart")?.addEventListener("click", () => {
    touch();
    if (activeFlow === "destination") {
      screen = "destinations";
      selectedDestination = null;
      robotStatus = null;
      sawNavigating = false;
    } else {
      screen = "welcome";
      status = null;
      activeFlow = null;
    }
    render();
  });

  document.getElementById("btn-stop")?.addEventListener("click", () => void stopTour());
}

function touch(): void {
  lastInteractionAt = Date.now();
}

async function openDestinations(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    destinations = await api.getDestinations();
    featuredDestinations = pickFeatured(destinations, config);
    screen = "destinations";
    activeFlow = null;
    searchQuery = "";
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function goToDestination(pointName: string): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  selectedDestination = pointName;
  sawNavigating = false;
  render();
  try {
    await api.goDestination(pointName, lang);
    activeFlow = "destination";
    screen = "dest_running";
    robotStatus = await api.getRobotStatus();
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
    screen = "destinations";
    selectedDestination = null;
  } finally {
    busy = false;
    render();
  }
}

async function startTour(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    const result = await api.startTour(lang);
    status = result.status ?? (await api.getTourStatus());
    activeFlow = "tour";
    screen = "running";
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
  } finally {
    busy = false;
    render();
  }
}

async function stopTour(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    if (activeFlow === "destination") {
      await api.haltAll();
      screen = "destinations";
      selectedDestination = null;
      sawNavigating = false;
      showToast(tr().destStopped);
    } else {
      const result = await api.stopTour();
      status = result.status ?? (await api.getTourStatus());
      screen = "completed";
    }
  } catch {
    showToast(tr().actionError);
  } finally {
    busy = false;
    render();
  }
}

async function runAssistance(): Promise<void> {
  if (busy) return;
  touch();
  busy = true;
  render();
  try {
    await api.runAction("inform_waiting", lang);
    showToast(tr().assistanceHint);
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
  } finally {
    busy = false;
    render();
  }
}

/** Bascule l'UI en état d'écoute + garde-fou 12 s si l'app native ne rappelle jamais. */
function enterListeningState(): void {
  touch();
  voiceTranscript = "";
  voiceReply = "";
  voiceState = "listening";
  render();
  if (voiceTimer !== null) window.clearTimeout(voiceTimer);
  voiceTimer = window.setTimeout(() => {
    if (voiceState === "listening") {
      voiceReply = tr().voiceError;
      voiceState = "answer";
      render();
    }
  }, 12000);
}

function startVoice(): void {
  if (busy || voiceState !== "idle") return;
  if (!voiceAvailable()) {
    showToast(tr().voiceUnavailable);
    return;
  }
  enterListeningState();
  try {
    window.CybelVoice?.startListening(lang);
  } catch {
    voiceReply = tr().voiceUnavailable;
    voiceState = "answer";
    render();
  }
}

/** Appelé par l'app native quand « Hé Cybel » est détecté ; la capture de la
 * commande a déjà démarré côté natif, on bascule juste l'UI en écoute. */
function onWakeDetected(): void {
  if (busy || voiceState !== "idle") return;
  enterListeningState();
}

function closeVoice(): void {
  if (voiceTimer !== null) {
    window.clearTimeout(voiceTimer);
    voiceTimer = null;
  }
  voiceState = "idle";
  voiceTranscript = "";
  voiceReply = "";
  pendingQuestion = null;
  touch();
  render();
}

/** Appelé par l'app native (evaluateJavascript) avec le transcript STT. */
async function onVoiceTranscript(transcript: string, ok: boolean): Promise<void> {
  if (voiceTimer !== null) {
    window.clearTimeout(voiceTimer);
    voiceTimer = null;
  }
  const text = (transcript || "").trim();
  if (!ok || !text) {
    voiceReply = tr().voiceError;
    voiceState = "answer";
    render();
    return;
  }
  if (pendingQuestion) {
    await handlePendingAnswer(text);
    return;
  }
  await routeVoiceText(text);
}

async function runReceptionAction(actionId: string): Promise<void> {
  if (busy) return;
  touch();
  if (actionId === "guided_tour") {
    await startTour();
    return;
  }
  if (actionId === "return_charge") {
    busy = true;
    render();
    try {
      await api.goHome();
      showToast(lang === "fr" ? "Retour à la borne lancé" : "Returning to charger");
    } catch (err) {
      const text = err instanceof Error ? err.message : tr().actionError;
      showToast(text);
    } finally {
      busy = false;
      render();
    }
    return;
  }
  busy = true;
  render();
  try {
    const result = await api.runAction(actionId, lang);
    if (result.events?.some((e) => e.includes("Navigation"))) {
      activeFlow = "destination";
      screen = "dest_running";
      selectedDestination = result.events.find((e) => e.includes("vers"))?.split("vers ").pop() ?? null;
      sawNavigating = false;
      robotStatus = await api.getRobotStatus();
    } else {
      showToast(tr().assistanceHint);
    }
  } catch (err) {
    const text = err instanceof Error ? err.message : tr().actionError;
    showToast(text);
  } finally {
    busy = false;
    render();
  }
}

export async function initApp(): Promise<void> {
  // Callback global invoqué par l'app native (CybelVisitorKioskTest) après STT Vosk.
  window.__cybelVoiceResult = (transcript: string, ok: boolean) => {
    void onVoiceTranscript(transcript, ok);
  };
  // Callback global invoqué par l'app native quand « Hé Cybel » est détecté.
  window.__cybelWakeDetected = () => {
    onWakeDetected();
  };
  render();
  startClock();
  startTelemetry();
  try {
    const [tourInfo, tourStatus, dests, actions, kioskConfig, robot, speech] = await Promise.all([
      api.getTour(),
      api.getTourStatus(),
      api.getDestinations(),
      api.getActions(),
      api.getConfig(),
      api.getRobotStatus().catch(() => null),
      api.getSpeechStatus().catch(() => null),
    ]);
    tour = tourInfo;
    status = tourStatus;
    destinations = dests;
    config = kioskConfig;
    featuredDestinations = pickFeatured(destinations, config);
    receptionActions = pickReceptionActions(actions, config);
    robotStatus = robot;
    speechStatus = speech;
    syncScreenFromTourStatus();
    if (status?.state === "running") {
      activeFlow = "tour";
      screen = "running";
    }
  } catch {
    showToast(t.fr.actionError);
  }
  render();
}
