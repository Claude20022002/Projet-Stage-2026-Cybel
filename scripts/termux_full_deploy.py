"""Tentative déploiement backend complet (FastAPI) sur Termux."""
import sys
import paramiko

HOST, PORT, USER, PW = "172.16.0.130", 8022, "u0_a92", "gasgas"

SCRIPT = r"""
set -e
export CYBEL_HOME=$HOME/cybel
echo "=== Espace disque ==="
df -h /data | tail -1
echo "=== Rust ==="
rustc --version 2>/dev/null || echo rust_absent
echo "=== Nettoyage ==="
bash $CYBEL_HOME/scripts/termux/free_disk.sh || true
rm -rf $HOME/tmp $PREFIX/tmp/pip-* 2>/dev/null || true
rm -f $CYBEL_HOME/scripts/termux/.use_lite
echo "=== Bootstrap complet ==="
bash $CYBEL_HOME/scripts/termux/bootstrap.sh
echo "=== Redémarrage ==="
bash $CYBEL_HOME/scripts/termux/stop_cybel.sh || true
bash $CYBEL_HOME/scripts/termux/start_cybel.sh
echo "=== Vérification ==="
python -c "import fastapi, pydantic; print('fastapi', fastapi.__version__, 'pydantic', pydantic.__version__)"
curl -sf http://127.0.0.1:8000/api/health
echo ""
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PW, timeout=20, allow_agent=False, look_for_keys=False)
print("Déploiement complet en cours (10-30 min possible)...", flush=True)
_, stdout, stderr = c.exec_command(SCRIPT, timeout=2400)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
code = stdout.channel.recv_exit_status()
print("exit:", code)
c.close()
sys.exit(code)
