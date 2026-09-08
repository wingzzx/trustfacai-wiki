import os, sys, time, paramiko

HOST = "43.155.136.177"
PORT = 22
USER = "ubuntu"
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
REMOTE_ROOT = "/var/www/trustfacai"

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

def run(c, cmd, timeout=120):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode("utf-8", "replace")
    e = err.read().decode("utf-8", "replace")
    rc = out.channel.recv_exit_status()
    return rc, o, e

def upload_dir(c, local_dir, remote_dir):
    sftp = c.open_sftp()
    for root, dirs, files in os.walk(local_dir):
        rel = os.path.relpath(root, local_dir)
        target = remote_dir if rel == "." else remote_dir + "/" + rel.replace("\\", "/")
        try:
            sftp.stat(target)
        except IOError:
            sftp.mkdir(target)
        for f in files:
            local = os.path.join(root, f)
            remote = target + "/" + f
            sftp.put(local, remote)
            print("uploaded:", remote)
    sftp.close()

c = connect()

# 1. clear old site content (keep .git if present)
rc, o, e = run(c, "sudo find %s -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} + 2>/dev/null; echo CLEARED" % REMOTE_ROOT)
print(o.strip(), e.strip())

# 2. upload dist to temp dir (owned by ubuntu)
TMP = "/tmp/trustfacai-dist"
rc, o, e = run(c, "rm -rf %s && mkdir -p %s && echo TMP_OK" % (TMP, TMP))
print(o.strip(), e.strip())
upload_dir(c, DIST, TMP)

# 3. copy temp -> web root with sudo
rc, o, e = run(c, "sudo cp -r %s/. %s/ && sudo rm -rf %s && echo COPIED" % (TMP, REMOTE_ROOT, TMP))
print(o.strip(), e.strip())

# 4. perms
rc, o, e = run(c, "sudo chown -R www-data:www-data %s && sudo find %s -type d -exec chmod 755 {} + && sudo find %s -type f -exec chmod 644 {} + && echo PERMS_OK" % (REMOTE_ROOT, REMOTE_ROOT, REMOTE_ROOT))
print(o.strip(), e.strip())

# 4. verify
rc, o, e = run(c, "ls %s && echo '---' && curl -sk -o /dev/null -w 'index=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/ && curl -sk -o /dev/null -w 'sitemap=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/sitemap.xml && curl -sk -o /dev/null -w 'llms=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/llms.txt && curl -sk -o /dev/null -w 'robots=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/robots.txt && curl -sk -o /dev/null -w 'family=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/family-trust/ && curl -sk -o /dev/null -w 'article=%{http_code}\n' -H 'Host: trustfacai.com' https://127.0.0.1/family-trust/what-is-standard-family-trust.html" % REMOTE_ROOT)
print(o.strip(), e.strip())

c.close()
print("DEPLOY_DONE")
