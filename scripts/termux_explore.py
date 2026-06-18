#!/usr/bin/env python3
"""Exploration SSH de la tête Android (Termux) — inventaire réseau et capacités."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS = [
    ("termux-info", "termux-info 2>/dev/null || echo 'termux-info absent'"),
    ("uname", "uname -a"),
    ("pwd", "pwd && whoami && id"),
    ("python_pkg", "pkg list-installed 2>/dev/null | grep -E '^python/' || echo python non installé (pkg install python)"),
    ("pip", "python -m pip --version 2>&1 || echo pip absent"),
    ("disk", "df -h $HOME 2>/dev/null; du -sh $HOME/cybel 2>/dev/null || echo 'cybel non déployé'"),
    ("mem", "cat /proc/meminfo 2>/dev/null | head -5 || free -h 2>/dev/null || echo meminfo indisponible"),
    ("ip", "ip addr show 2>/dev/null || ifconfig 2>/dev/null || echo ip indisponible"),
    ("routes", "ip route 2>/dev/null || netstat -rn 2>/dev/null || echo routes indisponibles"),
    ("ping_chassis_wifi", "ping -c 2 -W 2 10.42.0.1 2>&1 || echo ping 10.42.0.1 échoué"),
    ("ping_chassis_eth", "ping -c 2 -W 2 192.168.20.22 2>&1 || echo ping 192.168.20.22 échoué"),
    ("rosbridge_wifi", "curl -sf -m 3 -o /dev/null -w 'HTTP %{http_code}\\n' http://10.42.0.1:9090 2>&1 || echo rosbridge 10.42.0.1 injoignable"),
    ("rosbridge_eth", "curl -sf -m 3 -o /dev/null -w 'HTTP %{http_code}\\n' http://192.168.20.22:9090 2>&1 || echo rosbridge 192.168.20.22 injoignable"),
    ("local_health", "curl -sf -m 2 http://127.0.0.1:8000/api/health 2>&1 || echo backend local absent"),
    ("am", "which am 2>/dev/null; am --version 2>/dev/null || echo am absent"),
    ("su", "which su 2>/dev/null; su -c id 2>&1 | head -1 || echo su indisponible"),
    ("tts_pkg", "pm list packages 2>/dev/null | grep -iE 'cybel|termux|tts' || echo pm indisponible"),
    ("cybel_proc", "pgrep -af uvicorn 2>/dev/null || ps aux 2>/dev/null | grep -i cybel | grep -v grep || echo pas de process cybel"),
]


def run_ssh(host: str, port: int, user: str, password: str) -> int:
    try:
        import paramiko
    except ImportError:
        print("Installez paramiko: pip install paramiko")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"Connexion SSH {user}@{host}:{port} ...")
    try:
        client.connect(
            host,
            port=port,
            username=user,
            password=password,
            timeout=15,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as exc:
        print(f"Échec connexion: {exc}")
        print("Vérifiez WiFi robot, IP, port 8022 et mot de passe.")
        return 1

    print("Connecté.\n" + "=" * 60)
    for title, cmd in COMMANDS:
        print(f"\n### {title}")
        print(f"$ {cmd}")
        _, stdout, stderr = client.exec_command(cmd, timeout=20)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err:
            print(f"[stderr] {err}")
        if not out and not err:
            print("(vide)")

    client.close()
    print("\n" + "=" * 60)
    print("Exploration terminée.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Exploration SSH Termux (tête Android)")
    parser.add_argument("--host", default=os.environ.get("CYBEL_TERMUX_HOST", "172.16.0.130"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBEL_TERMUX_PORT", "8022")))
    parser.add_argument("--user", default=os.environ.get("CYBEL_TERMUX_USER", "u0_a92"))
    parser.add_argument(
        "--password",
        default=os.environ.get("CYBEL_TERMUX_PASSWORD", ""),
        help="Ou variable CYBEL_TERMUX_PASSWORD (évitez de committer le mot de passe)",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass(f"Mot de passe SSH ({args.user}@{args.host}): ")
    return run_ssh(args.host, args.port, args.user, password)


if __name__ == "__main__":
    sys.exit(main())
