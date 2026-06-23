"""Lance le backend FastAPI et le frontend Vite en une seule commande."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
KIOSK_DIR = ROOT / "frontend-kiosk"


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
