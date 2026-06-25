#!/usr/bin/env python3
"""Probe rapide API kiosque sur tablette Termux."""
import json
import sys

import paramiko

HOST = sys.argv[1] if len(sys.argv) > 1 else "172.16.0.132"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "gasgas"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=8022, username="u0_a92", password=PASSWORD, timeout=15)

cmds = [
    "curl -s http://127.0.0.1:8000/api/robot/status",
    "curl -s -X POST 'http://127.0.0.1:8000/api/tour/start?lang=fr'",
    (
        "curl -s -w '\\nHTTP:%{http_code}' -X POST http://127.0.0.1:8000/api/reception/go "
        "-H 'Content-Type: application/json' "
        "-d '{\"point_name\":\"Extraction et soufflage\",\"lang\":\"fr\"}'"
    ),
]

for cmd in cmds:
    print("===", cmd[:80], "===")
    _, stdout, stderr = client.exec_command(cmd, timeout=90)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace").strip()
    if err:
        print("ERR:", err)

client.close()
