"""Libère de l'espace sur /data via su + réinstalle Rust."""
import sys
import paramiko

HOST, PORT, USER, PW = "172.16.0.130", 8022, "u0_a92", "gasgas"

SCRIPT = r"""
set -x
df -h /data
# Caches Android courants (root)
su -c 'rm -rf /data/dalvik-cache/* 2>/dev/null; rm -rf /data/system/dropbox/* 2>/dev/null; sync' || true
# Apt termux
rm -rf $PREFIX/var/cache/apt/archives/* 2>/dev/null || true
pkg clean -y 2>/dev/null || true
rm -rf $HOME/.cache/pip 2>/dev/null || true
df -h /data
AVAIL=$(df /data | tail -1 | awk '{print $4}')
echo "AVAIL_KB=$AVAIL"
if [ "$AVAIL" -gt 800000 ]; then
  echo "Espace suffisant — installation Rust..."
  pkg install -y rust binutils 2>&1 | tail -15
else
  echo "Toujours insuffisant pour Rust ($AVAIL Ko). Top dossiers /data:"
  su -c 'du -x -h -d 2 /data 2>/dev/null | sort -h | tail -15' || true
fi
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PW, timeout=20, allow_agent=False, look_for_keys=False)
_, stdout, stderr = c.exec_command(SCRIPT, timeout=600)
sys.stdout.buffer.write(stdout.read())
sys.stdout.buffer.write(stderr.read())
print("exit:", stdout.channel.recv_exit_status())
c.close()
