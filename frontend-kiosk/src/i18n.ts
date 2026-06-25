export const t = {
  fr: {
    title: "Visite du laboratoire",
    subtitle: "Découvrez nos équipements en suivant le robot",
    startTour: "Démarrer la visite",
    stopTour: "Arrêter la visite",
    newTour: "Nouvelle visite",
    langToggle: "EN",
    loading: "Chargement…",
    actionError: "Une erreur est survenue.",
    tourRunning: "Visite en cours",
    tourCompleted: "Visite terminée",
    tourStopped: "Visite interrompue",
    tourError: "Problème pendant la visite",
    followRobot: "Suivez le robot",
    step: "Étape",
    of: "sur",
    phaseIntro: "Introduction",
    phaseNavigating: "Déplacement",
    phasePresenting: "Présentation",
    phaseDwell: "Observation",
    phaseOutro: "Conclusion",
    stopsPreview: "Parcours",
    idleHint: "Appuyez pour lancer une visite guidée autonome avec présentation vocale des équipements.",
    completedHint: "Merci d'avoir visité le laboratoire. Le robot reste disponible.",
    stoppedHint: "La visite a été interrompue. Vous pouvez en relancer une nouvelle.",
    errorHint:
      "Échec de navigation possible (code 604) : obstacle sur le chemin, destination hors carte, ou robot mal localisé. Dégagez le passage, relocalisez depuis le contrôleur PC, puis relancez.",
    chooseMode: "Que souhaitez-vous faire ?",
    modeTour: "Visite guidée",
    modeTourHint: "Parcours complet avec présentation des équipements",
    modeDestinations: "Choisir une destination",
    modeDestinationsHint: "Le robot vous accompagne vers un point du laboratoire",
    destinationsTitle: "Où souhaitez-vous aller ?",
    destinationsHint: "Touchez une destination pour que le robot vous y conduise.",
    back: "Retour",
    destRunning: "En route",
    destCompleted: "Destination atteinte",
    destCompletedHint: "Vous êtes arrivé. Le robot reste à votre disposition.",
    destError: "Navigation impossible",
    destErrorHint: "Un obstacle ou un problème de localisation a empêché le déplacement.",
    destFollow: "Suivez le robot jusqu'à votre destination",
    newDestination: "Autre destination",
  },
  en: {
    title: "Laboratory tour",
    subtitle: "Discover our equipment by following the robot",
    startTour: "Start the tour",
    stopTour: "Stop tour",
    newTour: "New tour",
    langToggle: "FR",
    loading: "Loading…",
    actionError: "Something went wrong.",
    tourRunning: "Tour in progress",
    tourCompleted: "Tour complete",
    tourStopped: "Tour stopped",
    tourError: "Problem during the tour",
    followRobot: "Follow the robot",
    step: "Step",
    of: "of",
    phaseIntro: "Introduction",
    phaseNavigating: "Moving",
    phasePresenting: "Presentation",
    phaseDwell: "Observation",
    phaseOutro: "Conclusion",
    stopsPreview: "Route",
    idleHint: "Tap to start an autonomous guided tour with spoken presentations of the equipment.",
    completedHint: "Thank you for visiting the laboratory. The robot remains available.",
    stoppedHint: "The tour was interrupted. You can start a new one.",
    errorHint: "Check that the robot is ready and navigation points exist on the map.",
    chooseMode: "What would you like to do?",
    modeTour: "Guided tour",
    modeTourHint: "Full route with equipment presentations",
    modeDestinations: "Pick a destination",
    modeDestinationsHint: "The robot will take you to a lab location",
    destinationsTitle: "Where would you like to go?",
    destinationsHint: "Tap a destination and the robot will guide you there.",
    back: "Back",
    destRunning: "On the way",
    destCompleted: "Destination reached",
    destCompletedHint: "You have arrived. The robot remains available.",
    destError: "Navigation failed",
    destErrorHint: "An obstacle or localization issue prevented the trip.",
    destFollow: "Follow the robot to your destination",
    newDestination: "Another destination",
  },
} as const;

export function phaseLabel(phase: string, lang: keyof typeof t): string {
  const labels = t[lang];
  switch (phase) {
    case "intro":
      return labels.phaseIntro;
    case "navigating":
      return labels.phaseNavigating;
    case "presenting":
      return labels.phasePresenting;
    case "dwell":
      return labels.phaseDwell;
    case "outro":
      return labels.phaseOutro;
    default:
      return "";
  }
}

const POINT_ICONS: Record<string, string> = {
  charging: "🔌",
  gate: "🚪",
  access: "🚪",
  ride: "🛗",
  wait: "⏳",
  stop: "🛑",
  label: "🏷️",
  common: "📍",
};

export function pointIcon(type: string): string {
  return POINT_ICONS[type] ?? POINT_ICONS.common;
}
