export type Lang = "fr" | "en";

export interface ReceptionAction {
  id: string;
  label: string;
  description: string;
  icon: string;
  category: "accueil" | "navigation" | "maintenance" | "sécurité";
  speech?: string | null;
  target_point?: string | null;
  route_name?: string | null;
  label_en?: string | null;
  description_en?: string | null;
  speech_en?: string | null;
}

export interface FaqEntry {
  id: string;
  question_fr: string;
  question_en: string;
  reponse_fr: string;
  reponse_en: string;
}
