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
    errorHint: "Vérifiez que le robot est prêt et que les points de navigation existent sur la carte.",
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
