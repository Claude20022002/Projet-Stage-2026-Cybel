"""Bootstrap Termux alternatif — pip sans Rust si possible."""
import paramiko

HOST, PORT, USER, PW = "172.16.0.130", 8022, "u0_a92", "gasgas"

cmds = [
    "df -h /data",
    "du -sh $HOME/cybel $HOME/.cache 2>/dev/null; du -sh $PREFIX/var/cache/apt 2>/dev/null",
    "pkg clean -y 2>/dev/null; apt clean 2>/dev/null; echo cache_cleaned",
    "python --version 2>&1",
    "python -m pip install --no-cache-dir 'pydantic==2.9.2' 'pydantic-core==2.23.4' 2>&1 | tail -20",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, PORT, USER, PW, timeout=20, allow_agent=False, look_for_keys=False)
for cmd in cmds:
    print("===", cmd)
    _, o, e = c.exec_command(cmd, timeout=300)
    print(o.read().decode())
    err = e.read().decode()
    if err:
        print(err)
c.close()
