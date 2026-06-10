import { api } from "./api";
import { pushEvent, setVoiceListening } from "./state";

interface SpeechRecognitionResult {
  [index: number]: { transcript: string };
  length: number;
}

interface SpeechRecognitionEvent {
  results: SpeechRecognitionResult[];
}

interface SpeechRecognitionInstance extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

let recognition: SpeechRecognitionInstance | null = null;

export function isVoiceSupported(): boolean {
  return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function toggleVoiceListening(): void {
  if (!isVoiceSupported()) {
    pushEvent("Commande vocale non supportée par ce navigateur");
    return;
  }

  if (recognition) {
    recognition.stop();
    recognition = null;
    setVoiceListening(false);
    return;
  }

  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Ctor) return;

  recognition = new Ctor();
  recognition.lang = "fr-FR";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = async (event) => {
    const text = event.results[0]?.[0]?.transcript?.trim();
    if (!text) return;
    pushEvent(`Vocal : « ${text} »`);
    try {
      const result = await api.voiceCommand(text);
      result.events?.forEach((e) => pushEvent(e));
    } catch (err) {
      pushEvent(`Commande non reconnue : ${(err as Error).message}`);
    }
  };

  recognition.onerror = () => {
    pushEvent("Erreur microphone ou permission refusée");
    setVoiceListening(false);
    recognition = null;
  };

  recognition.onend = () => {
    setVoiceListening(false);
    recognition = null;
  };

  recognition.start();
  setVoiceListening(true);
  pushEvent("Écoute vocale activée");
}
