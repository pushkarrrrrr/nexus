#!/usr/bin/env python3
"""
NEXUS Standalone Engine CLI Entrypoint.
Designed for compilation with PyInstaller as an embedded sidecar for Tauri.
"""

import argparse
import os
import signal
import sys
from pathlib import Path


def main() -> None:
    # Ensure current directory and workspace packages are in sys.path
    if getattr(sys, "frozen", False):
        base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    parser = argparse.ArgumentParser(
        prog="nexus-engine",
        description="NEXUS Autonomous Agentic Operating System — Core Engine Sidecar",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("API_HOST", "127.0.0.1"),
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("API_PORT", "8000")),
        help="Port to bind (default: 8000)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.environ.get("NEXUS_DATA_DIR", ""),
        help="Custom user data directory (defaults to ~/Library/Application Support/NEXUS on macOS)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="NEXUS Engine v0.1.0 (aarch64-apple-darwin standalone sidecar)",
    )

    args = parser.parse_args()

    # Propagate configuration to environment variables
    os.environ["API_HOST"] = args.host
    os.environ["API_PORT"] = str(args.port)
    os.environ["LOG_LEVEL"] = args.log_level.upper()
    os.environ["NEXUS_STANDALONE"] = "1"
    if args.data_dir:
        abs_data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
        os.environ["NEXUS_DATA_DIR"] = abs_data_dir
        os.environ["SQLITE_FALLBACK_URL"] = f"sqlite+aiosqlite:///{os.path.join(abs_data_dir, 'nexus.db')}"

    # In standalone production mode, default NEXUS_ENV to production unless specified
    if "NEXUS_ENV" not in os.environ:
        os.environ["NEXUS_ENV"] = "production"

    import uvicorn

    from services.api.nexus_api.main import app

    # Register clean signal handlers
    def _shutdown_handler(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        access_log=(args.log_level.upper() == "DEBUG"),
    )


if __name__ == "__main__":
    main()
