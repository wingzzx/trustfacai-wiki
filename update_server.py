import os, sys, time, paramiko

HOST = "43.155.136.177"
PORT = 22
USER = "ubuntu"
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")

CMD = r"""
cd /var/www/trustfacai && sudo git pull origin main 2>&1 | tail -1
sudo python3 build.py 2>&1 | tail -1
sudo chown -R www-data:www-data /var/www/trustfacai
echo '---STATUS---'
for u in / /family-trust/ /debt-isolation/ /marriage-protection/ /wealth-allocation/ /family-trust/what-is-standard-family-trust.html /images/wechat-qr.jpg /sitemap.xml /llms.txt /robots.txt; do
  code=$(curl -sk -o /dev/null -w "%{http_code}" -H "Host: trustfacai.com" "https://127.0.0.1$u")
  echo "$u => $code"
done
"""

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

def run(c, cmd, timeout=180):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    rc = out.channel.recv_exit_status()
    return rc, o, e

if __name__ == "__main__":
    c = connect()
    rc, o, e = run(c, CMD)
    print(o)
    if e: print("[stderr]", e, file=sys.stderr)
    c.close()
