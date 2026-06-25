#!/usr/bin/env python3
"""Déploie CYBEL sur Termux (tête Android) via SSH/SFTP."""
from __future__ import annotations

import argparse
import getpass
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE_HOME = os.environ.get("CYBEL_TERMUX_HOME", "~/cybel")

PACK_PATHS = [
    "backend",
    "sdk",
    "data",
    "frontend-kiosk/dist",
    "scripts/termux",
]

SKIP_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".env",
    "node_modules",
}

SKIP_SUFFIXES = {".log", ".pyc"}


def build_kiosk(skip: bool) -> None:
    if skip:
        dist = ROOT / "frontend-kiosk" / "dist"
        if not dist.is_dir():
            print("ERREUR: --skip-kiosk-build mais frontend-kiosk/dist absent")
            sys.exit(1)
        return
    print("== Build frontend-kiosk ==")
    subprocess.run(
        ["npm", "run", "build"],
        cwd=ROOT / "frontend-kiosk",
        check=True,
        shell=sys.platform == "win32",
    )


def should_skip(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def create_bundle() -> bytes:
    print("== Création de l'archive de déploiement ==")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in PACK_PATHS:
            src = ROOT / rel
            if not src.exists():
                print(f"AVERTISSEMENT: {rel} absent, ignoré")
                continue
            if src.is_file():
                tar.add(src, arcname=rel)
                continue
            for file in src.rglob("*"):
                if file.is_dir() or should_skip(file):
                    continue
                arcname = file.relative_to(ROOT).as_posix()
                tar.add(file, arcname=arcname)
                print(f"  + {arcname}")
    buf.seek(0)
    data = buf.read()
    print(f"Archive: {len(data) / 1024:.1f} KiB")
    return data


def sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def deploy_remote(
    host: str,
    port: int,
    user: str,
    password: str,
    bundle: bytes,
    bootstrap: bool,
    restart: bool,
    *,
    full: bool = False,
    lite_only: bool = False,
    target: str = "main",
) -> int:
    try:
        import paramiko
    except ImportError:
        print("Installez paramiko: pip install paramiko")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connexion {user}@{host}:{port} ...")
    try:
        client.connect(
            host,
            port=port,
            username=user,
            password=password,
            timeout=30,
            allow_agent=False,
            look_for_keys=False,
        )
    except Exception as exc:
        print(f"Échec connexion: {exc}")
        return 1

    stdin, stdout, stderr = client.exec_command("echo $HOME")
    home = stdout.read().decode("utf-8", errors="replace").strip() or "/data/data/com.termux/files/home"
    remote_dir = "cybel-test" if target == "test" else "cybel"
    remote_base = f"{home}/{remote_dir}"
    remote_tar = f"{home}/cybel-deploy-{target}.tar.gz"
    backend_port = 8001 if target == "test" else 8000
    start_script = "start_cybel_test.sh" if target == "test" else "start_cybel.sh"
    stop_script = "stop_cybel_test.sh" if target == "test" else "stop_cybel.sh"
    kiosk_config_src = "kiosk_config.poi.json" if target == "test" else "kiosk_config.coords.json"

    print("== Upload archive ==")
    sftp = client.open_sftp()
    with sftp.file(remote_tar, "wb") as remote_file:
        remote_file.write(bundle)
    sftp.close()

    remote_cmds = [
        f"mkdir -p {sh_quote(remote_base)}",
        f"tar -xzf {sh_quote(remote_tar)} -C {sh_quote(remote_base)}",
        f"chmod +x {sh_quote(remote_base)}/scripts/termux/*.sh",
        f"cp {sh_quote(remote_base)}/data/{kiosk_config_src} {sh_quote(remote_base)}/data/kiosk_config.json",
        f"bash {sh_quote(remote_base)}/scripts/termux/setup_termux_kiosk.sh || true",
        f"rm -f {sh_quote(remote_tar)}",
        f"bash {sh_quote(remote_base)}/scripts/termux/free_disk.sh || true",
    ]
    if bootstrap:
        if lite_only:
            remote_cmds.append(f"bash {sh_quote(remote_base)}/scripts/termux/bootstrap_lite.sh")
        elif full:
            remote_cmds.append(f"rm -f {sh_quote(remote_base)}/scripts/termux/.use_lite")
            remote_cmds.append(f"bash {sh_quote(remote_base)}/scripts/termux/bootstrap.sh")
        else:
            remote_cmds.append(
                f"bash {sh_quote(remote_base)}/scripts/termux/bootstrap_lite.sh || "
                f"bash {sh_quote(remote_base)}/scripts/termux/bootstrap.sh"
            )
    if restart:
        remote_cmds.append(f"bash {sh_quote(remote_base)}/scripts/termux/{stop_script} || true")
        remote_cmds.append(f"bash {sh_quote(remote_base)}/scripts/termux/{start_script}")

    print("== Exécution distante ==")
    for cmd in remote_cmds:
        print(f"$ {cmd}")
        _, stdout, stderr = client.exec_command(cmd, timeout=2400 if "bootstrap" in cmd else 300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out.rstrip())
        if err.strip():
            print(err.rstrip(), file=sys.stderr)
        if stdout.channel.recv_exit_status() != 0 and "stop_cybel" not in cmd:
            # start_cybel peut avoir démarré le backend malgré un avertissement SD
            if "start_cybel" in cmd and "OK — health check" in out:
                print("AVERTISSEMENT: start_cybel code non nul mais backend OK — poursuite")
                continue
            print(f"Commande échouée: {cmd}")
            client.close()
            return 1

    client.close()
    print("\nDéploiement terminé.")
    print(f"Cible: {target} → {remote_base}")
    print(f"Kiosque: http://127.0.0.1:{backend_port}/kiosk/ (sur la tablette)")
    if target == "test":
        print("App Android: CybelVisitorKioskTest.apk (com.cybel.visitorkiosk.test)")
        print(f"Logs:    ssh -p {port} {user}@{host} 'tail -f ~/cybel-test-uvicorn.log'")
    else:
        print(f"Logs:    ssh -p {port} {user}@{host} 'tail -f ~/cybel-uvicorn.log'")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Déploiement CYBEL sur Termux")
    parser.add_argument("--host", default=os.environ.get("CYBEL_TERMUX_HOST", "172.16.0.130"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYBEL_TERMUX_PORT", "8022")))
    parser.add_argument("--user", default=os.environ.get("CYBEL_TERMUX_USER", "u0_a92"))
    parser.add_argument("--password", default=os.environ.get("CYBEL_TERMUX_PASSWORD", ""))
    parser.add_argument("--skip-kiosk-build", action="store_true")
    parser.add_argument("--no-bootstrap", action="store_true", help="Ne pas réinstaller pip deps")
    parser.add_argument("--full", action="store_true", help="Forcer bootstrap complet (pas lite)")
    parser.add_argument("--lite-only", action="store_true", help="Bootstrap lite uniquement")
    parser.add_argument("--no-restart", action="store_true", help="Ne pas redémarrer uvicorn")
    parser.add_argument(
        "--target",
        choices=("main", "test"),
        default="main",
        help="main=~/cybel:8000 (coords) ; test=~/cybel-test:8001 (POI Sentrymove)",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass(f"Mot de passe SSH ({args.user}@{args.host}): ")

    build_kiosk(args.skip_kiosk_build)
    bundle = create_bundle()
    return deploy_remote(
        args.host,
        args.port,
        args.user,
        password,
        bundle,
        bootstrap=not args.no_bootstrap,
        restart=not args.no_restart,
        full=args.full,
        lite_only=args.lite_only,
        target=args.target,
    )


if __name__ == "__main__":
    sys.exit(main())
