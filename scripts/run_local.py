"""Run the local Ollama, API and UI services; Ctrl+C stops services we started."""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / ".runtime"
STOP = threading.Event()


def reachable(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except (URLError, OSError):
        return False


def main() -> int:
    os.chdir(ROOT)
    # The launcher's explicit profile must win over stale exports in a terminal.
    load_dotenv(ROOT / ".env", override=True)
    os.environ.setdefault("HF_HOME", str(ROOT / ".hf"))
    os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
    os.environ.setdefault("OLLAMA_MODELS", str(ROOT / ".local" / "ollama" / "models"))
    # Keep the context bounded so the 8B model leaves room for its KV cache on a 6 GB GPU.
    os.environ.setdefault("OLLAMA_CONTEXT_LENGTH", "4096")
    os.environ.setdefault("OLLAMA_NUM_PARALLEL", "1")
    os.environ.setdefault("OLLAMA_FLASH_ATTENTION", "1")
    os.environ.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    os.environ.setdefault("OLLAMA_NO_CLOUD", "1")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
    local_ocr = ROOT / ".local" / "ocr" / "usr"
    if (local_ocr / "bin" / "tesseract").is_file():
        os.environ["PATH"] = str(local_ocr / "bin") + os.pathsep + os.environ.get("PATH", "")
        os.environ["LD_LIBRARY_PATH"] = str(local_ocr / "lib" / "x86_64-linux-gnu") + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
        os.environ.setdefault("TESSDATA_PREFIX", str(local_ocr / "share" / "tesseract-ocr" / "5" / "tessdata"))
    api_port = int(os.environ.get("API_PORT", "8000"))
    ui_port = int(os.environ.get("UI_PORT", "8501"))
    os.environ["API_BASE_URL"] = f"http://127.0.0.1:{api_port}"
    RUNTIME.mkdir(exist_ok=True)
    pid_file = RUNTIME / "launcher.pid"
    try:
        running_pid = int(pid_file.read_text())
        os.kill(running_pid, 0)
        if (reachable(f"http://127.0.0.1:{api_port}/health") and
                reachable(f"http://127.0.0.1:{ui_port}/_stcore/health")):
            print(f"The local demo is already running (launcher PID {running_pid}).\n"
                  f"UI: http://localhost:{ui_port}\nAPI docs: http://localhost:{api_port}/docs",
                  flush=True)
            return 0
    except (OSError, ValueError):
        pass
    for port in (api_port, ui_port):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise RuntimeError(f"Port {port} is already in use. Stop the existing service first.")

    children: list[tuple[str, subprocess.Popen]] = []

    def start(name: str, command: list[str]) -> None:
        with (RUNTIME / f"{name}.log").open("a") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
        children.append((name, process))
        print(f"Started {name} (PID {process.pid}); log: .runtime/{name}.log", flush=True)

    def wait_ready(url: str, seconds: int = 120) -> None:
        deadline = time.monotonic() + seconds
        while not STOP.is_set() and time.monotonic() < deadline:
            for name, process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited; see .runtime/{name}.log")
            if reachable(url):
                return
            STOP.wait(1)
        if not STOP.is_set():
            raise RuntimeError(f"Service did not become ready: {url}")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())

    pid_file.write_text(str(os.getpid()))
    try:
        ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        use_mock = os.environ.get("MOCK_LLM", "false").lower() in ("true", "1", "yes")
        if not use_mock and not reachable(f"{ollama_url}/api/tags"):
            target = urlparse(ollama_url)
            if target.hostname not in ("localhost", "127.0.0.1"):
                raise RuntimeError(f"Configured Ollama server is unreachable: {ollama_url}")
            binary = shutil.which("ollama") or str(ROOT / ".local" / "ollama" / "bin" / "ollama")
            if not Path(binary).is_file():
                raise RuntimeError("Ollama is missing. See docs/local_setup.md.")
            os.environ.setdefault("OLLAMA_HOST", f"127.0.0.1:{target.port or 11434}")
            start("ollama", [binary, "serve"])
            wait_ready(f"{ollama_url}/api/tags")
        if STOP.is_set():
            return 0
        start("api", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                      "--port", str(api_port)])
        wait_ready(f"http://127.0.0.1:{api_port}/health")
        if STOP.is_set():
            return 0
        start("ui", [sys.executable, "-m", "streamlit", "run", "ui/streamlit_app.py",
                     "--server.address", "127.0.0.1", "--server.port", str(ui_port),
                     "--server.headless", "true", "--theme.base", "light"])
        wait_ready(f"http://127.0.0.1:{ui_port}/_stcore/health")
        print(f"UI: http://localhost:{ui_port}\nAPI docs: http://localhost:{api_port}/docs\n"
              "Press Ctrl+C to stop.", flush=True)
        while not STOP.wait(1):
            for name, process in children:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited; see .runtime/{name}.log")
        return 0
    finally:
        for _, process in reversed(children):
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for _, process in reversed(children):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, OSError) as exc:
        print(f"Local startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
