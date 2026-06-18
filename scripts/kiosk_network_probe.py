"""Diagnostique accès kiosk depuis contexte Android (pas Termux)."""
import paramiko
import sys

SCRIPT = r"""
echo "=== Termux curl ==="
curl -sf -o /dev/null -w 'health %{http_code}\n' http://127.0.0.1:8000/api/health
curl -sf -o /dev/null -w 'kiosk %{http_code}\n' http://127.0.0.1:8000/kiosk/
curl -sf -o /dev/null -w 'js %{http_code}\n' http://127.0.0.1:8000/kiosk/assets/index-DKJA9-5T.js
echo "=== su curl (contexte systeme / autre app) ==="
su -c 'curl -sf -o /dev/null -w "health %{http_code}\n" http://127.0.0.1:8000/api/health' 2>&1 || echo su_curl_fail
su -c 'curl -sf -o /dev/null -w "kiosk %{http_code}\n" http://127.0.0.1:8000/kiosk/' 2>&1
IP=$(ip -4 addr show wlan0 | awk '/inet /{print $2}' | cut -d/ -f1 | head -1)
echo "wlan IP=$IP"
su -c "curl -sf -o /dev/null -w 'kiosk_lan %{http_code}\n' http://$IP:8000/kiosk/" 2>&1
curl -sf -o /dev/null -w 'kiosk_lan termux %{http_code}\n' http://$IP:8000/kiosk/
echo "=== webview package ==="
su -c 'dumpsys package com.google.android.webview 2>/dev/null | grep versionName' | head -1
pm list packages | grep webview
"""

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("172.16.0.130", 8022, "u0_a92", "gasgas", timeout=15, allow_agent=False, look_for_keys=False)
_, o, e = c.exec_command(SCRIPT, timeout=60)
sys.stdout.buffer.write(o.read())
sys.stdout.buffer.write(e.read())
c.close()
