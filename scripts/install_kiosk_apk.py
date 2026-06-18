"""Pousse et installe CybelVisitorKiosk.apk sur la tablette via SSH."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APK = ROOT / "android" / "CybelVisitorKiosk" / "out" / "CybelVisitorKiosk.apk"
REMOTE_APK = "/sdcard/Download/CybelVisitorKiosk.apk"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("CYBEL_TERMUX_HOST", "172.16.0.130"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBEL_TERMUX_PORT", "8022")))
    parser.add_argument("--user", default=os.environ.get("CYBEL_TERMUX_USER", "u0_a92"))
    parser.add_argument("--password", default=os.environ.get("CYBEL_TERMUX_PASSWORD", ""))
    args = parser.parse_args()

    if not APK.is_file():
        print(f"APK introuvable: {APK} — lancez le build d'abord.")
        return 1

    try:
        import paramiko
    except ImportError:
        print("pip install paramiko")
        return 1

    password = args.password or __import__("getpass").getpass("Mot de passe SSH: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        args.host, args.port, args.user, password,
        timeout=20, allow_agent=False, look_for_keys=False,
    )

    print(f"Upload {APK.name} ({APK.stat().st_size // 1024} KiB)...")
    sftp = client.open_sftp()
    sftp.put(str(APK), REMOTE_APK)
    sftp.close()

    install_cmd = f"su -c 'pm install -r {REMOTE_APK}'"
    print(f"$ {install_cmd}")
    _, stdout, stderr = client.exec_command(install_cmd, timeout=120)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)

    code = stdout.channel.recv_exit_status()
    if code != 0:
        # fallback termux pm if su path differs
        alt = f"pm install -r {REMOTE_APK} 2>&1 || cmd package install -r -i com.android.vending {REMOTE_APK}"
        print("Retry:", alt)
        _, stdout2, _ = client.exec_command(alt, timeout=120)
        print(stdout2.read().decode())

    launch = "su -c 'am start -n com.cybel.visitorkiosk/.MainActivity'"
    client.exec_command(launch, timeout=30)
    print("App relancée — URL: http://127.0.0.1:8000/kiosk/")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
