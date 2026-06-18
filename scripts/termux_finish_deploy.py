"""pip install + démarrage backend CYBEL sur Termux."""
import sys
import paramiko

HOST, PORT, USER, PW = "172.16.0.130", 8022, "u0_a92", "gasgas"

SCRIPT = r"""
set -e
export CYBEL_HOME=$HOME/cybel
bash $CYBEL_HOME/scripts/termux/bootstrap.sh
bash $CYBEL_HOME/scripts/termux/stop_cybel.sh || true
bash $CYBEL_HOME/scripts/termux/start_cybel.sh
echo "--- kiosk ---"
curl -sf -m 3 -o /dev/null -w 'kiosk HTTP %{http_code}\n' http://127.0.0.1:8000/kiosk/ || echo kiosk_fail
curl -sf -m 3 http://127.0.0.1:8000/api/health || echo health_fail
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PW, timeout=20, allow_agent=False, look_for_keys=False)
print("Bootstrap + start (peut prendre 10-20 min)...", flush=True)
_, stdout, stderr = c.exec_command(SCRIPT, timeout=1800)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
code = stdout.channel.recv_exit_status()
print("exit:", code)
c.close()
sys.exit(code)
