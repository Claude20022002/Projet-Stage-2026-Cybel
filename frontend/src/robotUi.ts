import type { RobotStatus } from "./types";

/** Le robot accepte les commandes /cmd_vel si control_state ≠ 30 (mode auto). */
export function isTeleopEnabled(status: RobotStatus | null): boolean {
  if (!status?.connected) return false;
  return status.nav_mode === "manual" || status.control_state !== 30;
}

export function teleopHint(status: RobotStatus | null): string {
  if (!status?.connected) {
    return "Robot déconnecté — vérifiez le Wi‑Fi du robot.";
  }
  if (status.nav_status === 602 && status.nav_mode !== "manual") {
    return "Navigation en cours — activez le <strong>mode manuel</strong> (la navigation sera annulée).";
  }
  if (!isTeleopEnabled(status)) {
    return "Activez le <strong>mode manuel</strong> pour piloter le robot à la télécommande.";
  }
  return "Maintenez les flèches pour déplacer le robot.";
}
