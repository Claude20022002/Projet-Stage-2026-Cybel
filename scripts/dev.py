"""Lance le backend FastAPI et le frontend Vite en une seule commande."""
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
KIOSK_DIR = ROOT / "frontend-kiosk"
BACKEND_HEALTH_URL = "http://127.0.0.1:8000/api/health"


def wait_for_backend(timeout: float = 90.0) -> bool:
    """Attend que l'API réponde avant de lancer les proxies Vite."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BACKEND_HEALTH_URL, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def stream_output(process: subprocess.Popen, prefix: str) -> None:
    for line in iter(process.stdout.readline, b""):
        sys.stdout.write(f"[{prefix}] {line.decode(errors='replace')}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # --reload ouvre plusieurs connexions rosbridge et sature le robot.
    use_reload = os.environ.get("CYBEL_DEV_RELOAD", "").strip().lower() in ("1", "true", "yes")
    backend_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000"]
    if use_reload:
        backend_cmd.extend(
            ["--reload", "--reload-dir", str(BACKEND_DIR), "--reload-dir", str(ROOT / "sdk")]
        )
    else:
        print("[dev] Backend sans --reload (connexion rosbridge stable).")
        print("[dev] CYBEL_DEV_RELOAD=1 pour activer le rechargement auto.\n")

    backend = subprocess.Popen(
        backend_cmd,
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    print("[dev] Démarrage backend…")
    if wait_for_backend():
        print("[dev] Backend prêt sur http://127.0.0.1:8000\n")
    else:
        print("[dev] Attention : backend non joignable — les frontends peuvent afficher ECONNREFUSED.\n")

    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=sys.platform == "win32",
    )
    kiosk = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=KIOSK_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=sys.platform == "win32",
    )

    threading.Thread(target=stream_output, args=(backend, "backend"), daemon=True).start()
    threading.Thread(target=stream_output, args=(frontend, "frontend"), daemon=True).start()
    threading.Thread(target=stream_output, args=(kiosk, "kiosk"), daemon=True).start()

    processes = (backend, frontend, kiosk)
    try:
        while all(proc.poll() is None for proc in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
