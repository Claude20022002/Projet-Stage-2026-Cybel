#!/usr/bin/env python3
"""Build kiosk + déploiement Termux + instructions ADB USB."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIOSK = ROOT / "frontend-kiosk"
APK = ROOT / "android" / "CybelVisitorKiosk" / "out" / "CybelVisitorKiosk.apk"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--host", default=os.environ.get("CYBEL_TERMUX_HOST", "172.16.0.130"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBEL_TERMUX_PORT", "8022")))
    parser.add_argument("--user", default=os.environ.get("CYBEL_TERMUX_USER", "u0_a92"))
    parser.add_argument("--password", default=os.environ.get("CYBEL_TERMUX_PASSWORD", ""))
    args = parser.parse_args()

    if not args.skip_build:
        print("== 1/3 Build frontend-kiosk (IIFE chrome49) ==")
        run(["npm", "run", "build"], cwd=KIOSK)
        index = KIOSK / "dist" / "index.html"
        html = index.read_text(encoding="utf-8")
        if "type=\"module\"" in html:
            print("ERREUR: dist contient encore type=module")
            return 1
        if "System.import" in html:
            print("ERREUR: dist contient encore System.import")
            return 1
        print("OK — index.html:", index.read_text(encoding="utf-8")[:200])

    if not args.skip_deploy:
        print("\n== 2/3 Déploiement Termux ==")
        deploy = ROOT / "scripts" / "deploy_termux.py"
        cmd = [sys.executable, str(deploy), "--skip-kiosk-build", "--lite-only"]
        if args.password:
            cmd.extend(["--password", args.password])
        cmd.extend(["--host", args.host, "--port", str(args.port), "--user", args.user])
        run(cmd)

    print("\n== 3/3 APK + ADB USB (à exécuter avec câble branché) ==")
    print("Rebuild APK si MainActivity modifié:")
    print("  cd android/CybelVisitorKiosk && build.sh  (ou script PowerShell du README)")
    print(f"  adb install -r {APK}")
    print("  adb shell pm clear com.cybel.visitorkiosk")
    print("  adb shell am start -n com.cybel.visitorkiosk/.MainActivity")
    print("\nDiagnostic USB:")
    print("  adb logcat -s CybelKiosk:V chromium:V")
    print("\nTest réseau dans l'app (après deploy):")
    print("  echo 'http://<IP_WLAN>:8000/kiosk/test.html' > /sdcard/Download/cybel_kiosk_url.txt")
    print("  (via SSH Termux, remplacer <IP_WLAN> par ip addr show wlan0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
