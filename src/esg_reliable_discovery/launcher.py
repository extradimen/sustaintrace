from __future__ import annotations

import argparse
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from .release_runtime import initialize_workspace
from .workbench_api import serve


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _open_when_ready(url: str) -> None:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"{url}/api/v1/health", timeout=0.5) as response:  # noqa: S310
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the complete local SustainTrace workbench")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()
    initialized = initialize_workspace(workspace)
    if not _port_available(args.host, args.port):
        raise SystemExit(
            f"Port {args.port} is already in use. Stop that process or pass --port PORT."
        )
    url = f"http://{args.host}:{args.port}"
    print(
        f"SustainTrace workspace: {workspace}\n"
        f"Trusted seed: {initialized['counts']['trusted_facts']} Tier B facts\n"
        f"Open: {url}",
        flush=True,
    )
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    try:
        serve(workspace, args.host, args.port)
    except KeyboardInterrupt:
        print("\nSustainTrace stopped.", flush=True)


if __name__ == "__main__":
    main()
