#!/usr/bin/env python3
"""Serve the built workspace and its persistent API with paid providers disabled."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.staticfiles import StaticFiles  # noqa: E402
import uvicorn  # noqa: E402
from backend.app.api import create_app  # noqa: E402
from backend.app.providers.config import ProviderSettings  # noqa: E402
from backend.app.service import WorkflowService  # noqa: E402


def demo_app(data_dir: Path):
    # Do not read provider credentials from the environment in the demo entrypoint.
    service = WorkflowService(data_dir, provider_settings=ProviderSettings(api_key="", m2_provider="disabled"))
    app = create_app(service=service)
    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="workspace")
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local-data" / "demo")
    parser.add_argument("--open", action="store_true", help="Open this machine's browser")
    args = parser.parse_args()
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        parser.error("Built frontend missing. Run npm --prefix frontend ci and npm --prefix frontend run build first.")
    address = f"http://127.0.0.1:{args.port}"
    print(f"Video Anatomy offline demo: {address}\nSaved tasks: {args.data_dir.resolve()}\nPaid providers are disabled.", flush=True)
    if args.open:
        threading.Timer(1.5, webbrowser.open, args=(address,)).start()
    uvicorn.run(demo_app(args.data_dir), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
