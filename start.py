#!/usr/bin/env python3
"""The one file you run.

    python start.py

It installs missing Python packages, starts the local web server, and
opens the UI in your browser. Everything else (Ollama server, model
downloads, model warm-up) is verified and auto-fixed from inside the
UI — if a check fails, the UI tells you what's needed and gives you a
Retry button.

Low on space on your default drive? Set OLLAMA_MODELS to a path on a
drive with more room before running this, e.g. on Windows:
    setx OLLAMA_MODELS "D:\\ollama-models"
Ollama's own default (no env var needed) works fine for most people.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8765


def ensure_python_deps() -> None:
    needed = {"aiohttp": "aiohttp>=3.9", "httpx": "httpx>=0.27", "yaml": "pyyaml>=6.0"}
    missing = [pkg for mod, pkg in needed.items() if importlib.util.find_spec(mod) is None]
    if missing:
        print(f"Installing Python packages: {', '.join(missing)} …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser_when_ready() -> None:
    import time
    for _ in range(50):
        if port_in_use(PORT):
            webbrowser.open(f"http://127.0.0.1:{PORT}")
            return
        time.sleep(0.2)


def main() -> None:
    if sys.version_info < (3, 10):
        print(f"Python 3.10+ required (you have {sys.version.split()[0]}).")
        sys.exit(1)

    # Respect OLLAMA_MODELS if the user already set it (e.g. to store models
    # on a bigger/faster drive); otherwise leave it unset and let Ollama use
    # its own default location.
    if os.environ.get("OLLAMA_MODELS"):
        Path(os.environ["OLLAMA_MODELS"]).mkdir(parents=True, exist_ok=True)

    ensure_python_deps()

    if port_in_use(PORT):
        print(f"HotHeads already running — opening http://127.0.0.1:{PORT}")
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        return

    sys.path.insert(0, str(ROOT))
    from webui.server import run

    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    print(f"HotHeads → http://127.0.0.1:{PORT}   (Ctrl+C to stop)")
    run(PORT)


if __name__ == "__main__":
    main()
