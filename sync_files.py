import os, sys, time, paramiko

HOST = "43.155.136.177"
PORT = 22
USER = "ubuntu"
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")
ROOT = os.path.dirname(os.path.abspath(__file__))

FILES = [
    ("src/templates/contact.html", "/var/www/trustfacai/src/templates/contact.html"),
    ("src/templates/footer.html", "/var/www/trustfacai/src/templates/footer.html"),
    ("build.py", "/var/www/trustfacai/build.py"),
]

def connect(retries=8, delay=6):
    last = None
    for i in range(retries):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(HOST, port=PORT, username=USER, key_filename=KEY,
                      timeout=25, banner_timeout=25, auth_timeout=25)
            return c
        except Exception as e:
            last = e
            print("[retry %d/%d] %s" % (i + 1, retries, e), file=sys.stderr)
            time.sleep(delay)
    raise last

c = connect()
# 先把待覆盖文件归还给 ubuntu（update_server.py 会 chown 成 www-data）
_, out, err = c.exec_command(
    "sudo chown -R ubuntu:ubuntu /var/www/trustfacai/src /var/www/trustfacai/build.py && echo CHOWN_OK", timeout=30)
print(out.read().decode("utf-8", "replace").strip())
sftp = c.open_sftp()
for local_rel, remote in FILES:
    sftp.put(os.path.join(ROOT, local_rel), remote)
    print("uploaded:", remote)
sftp.close()

cmd = ("cd /var/www/trustfacai && sudo chown -R ubuntu:ubuntu src build.py 2>/dev/null; "
       "sudo python3 build.py 2>&1 | tail -1 && "
       "sudo chown -R www-data:www-data /var/www/trustfacai && echo SYNC_OK")
_, out, err = c.exec_command(cmd, timeout=120)
print(out.read().decode("utf-8", "replace"))
e = err.read().decode("utf-8", "replace")
if e: print("[stderr]", e, file=sys.stderr)
c.close()
