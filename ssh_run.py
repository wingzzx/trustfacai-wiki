import os, sys, time, paramiko

HOST = "43.155.136.177"
PORT = 22
USER = "ubuntu"
KEY = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")

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
    cmd = sys.argv[1] if len(sys.argv) > 1 else "echo connected"
    c = connect()
    rc, o, e = run(c, cmd)
    if o: print(o)
    if e: print("[stderr]", e, file=sys.stderr)
    c.close()
    sys.exit(rc if rc is not None else 0)