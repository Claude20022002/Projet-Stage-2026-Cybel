"""Nettoyage disque + tentative bootstrap minimal sur Termux."""
import sys
import paramiko

HOST, PORT, USER, PW = "172.16.0.130", 8022, "u0_a92", "gasgas"

SCRIPT = r"""
set -e
bash ~/cybel/scripts/termux/free_disk.sh 2>/dev/null || true
rm -rf $PREFIX/var/cache/apt/archives/partial 2>/dev/null || true
df -h /data | tail -1
echo "--- pkg search pydantic ---"
pkg search pydantic 2>/dev/null | head -5 || echo none
echo "--- try pkg install python-pydantic ---"
pkg install -y python-pydantic 2>&1 | tail -5 || true
echo "--- pip prefer-binary fastapi stack ---"
python -m pip install --no-cache-dir --prefer-binary \
  'fastapi>=0.115' 'uvicorn[standard]>=0.32' 'websockets>=13' \
  'pydantic-settings>=2.6' 'httpx>=0.27' 2>&1 | tail -25
echo "--- health test ---"
python -c "import fastapi, pydantic, uvicorn; print('imports OK', pydantic.__version__)"
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PW, timeout=20, allow_agent=False, look_for_keys=False)
_, stdout, stderr = c.exec_command(SCRIPT, timeout=600)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
print("exit:", stdout.channel.recv_exit_status())
c.close()
