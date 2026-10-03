import sys
import os
import subprocess
import time

log_file = os.path.join(os.path.dirname(__file__), "deploy_result.log")

def log(msg):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%X')}] {msg}\n")
    print(msg)

if os.path.exists(log_file):
    os.remove(log_file)

log("Starting server deployment via SSH...")

try:
    import paramiko
    log("paramiko is already installed.")
except ImportError:
    log("Installing paramiko...")
    res = subprocess.run([sys.executable, "-m", "pip", "install", "paramiko"], capture_output=True, text=True)
    log(f"pip install stdout: {res.stdout[:200]}")
    if res.stderr:
        log(f"pip install stderr: {res.stderr[:200]}")
    import paramiko
    log("paramiko installed successfully.")

HOST = "100.93.95.78"
USER = "root"
PASS = "123456"

log(f"Connecting to {USER}@{HOST}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    log("SSH connection established successfully!")
except Exception as e:
    log(f"SSH connection failed: {e}")
    sys.exit(1)

commands = [
    ("Installing git and python tools if missing", "apt update && apt install -y git python3 python3-pip"),
    ("Cloning or pulling latest code from GitHub", "cd /root && (git clone https://github.com/Duong11uy/Downloads-tool.git || (cd Downloads-tool && git pull origin main))"),
    ("Installing python requirements", "cd /root/Downloads-tool && pip install -r requirements.txt curl_cffi --break-system-packages"),
    ("Stopping old running instances", "pkill -f 'src/app.py' || true"),
    ("Starting app in background with nohup", "cd /root/Downloads-tool && nohup python3 src/app.py > app.log 2>&1 &"),
    ("Verifying server is running on port 8000", "sleep 3 && curl -I http://localhost:8000")
]

for desc, cmd in commands:
    log(f"\n--- {desc} ---")
    log(f"Executing: {cmd}")
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            log(f"STDOUT:\n{out}")
        if err:
            log(f"STDERR:\n{err}")
    except Exception as cmd_e:
        log(f"Error executing command: {cmd_e}")

client.close()
log("\nDeployment completed!")
