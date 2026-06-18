"""Probe rapide du châssis via le lien eth0 interne."""
import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    "172.16.0.130", 8022, "u0_a92", "gasgas",
    timeout=15, allow_agent=False, look_for_keys=False,
)
cmds = [
    "ping -c 2 -W 2 192.168.20.22",
    "curl -sf -m 3 -o /dev/null -w 'HTTP %{http_code}\\n' http://192.168.20.22:9090 || echo rosbridge_fail",
    "pkg list-installed | grep -E '^python/' || echo python_not_installed",
]
for cmd in cmds:
    print(f"=== {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=20)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print(err)
client.close()
