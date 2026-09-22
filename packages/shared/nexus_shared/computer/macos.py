"""Concrete macOS Computer Control Adapter for NEXUS."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from packages.shared.nexus_shared.computer.base import (
    MAX_COMMAND_OUTPUT_BYTES,
    ComputerControlAdapter,
    is_protected_directory,
)
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.policy.utils import normalize_resource_target

logger = get_logger("nexus.computer.macos")


class MacOSAdapter(ComputerControlAdapter):
    """Concrete macOS automation adapter using native tools and Python standard library."""

    async def open_application(self, app_name: str) -> dict[str, Any]:
        """Launch an approved application on macOS via /usr/bin/open -a."""
        app_clean = app_name.strip()
        if not app_clean or any(c in app_clean for c in ";|&$`\n"):
            raise ValueError(f"Invalid application name: '{app_name}'")

        cmd = ["/usr/bin/open", "-a", app_clean]
        logger.info("macos_open_app", app=app_clean)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Failed to open application '{app_clean}': {err_msg}")

        return {
            "status": "success",
            "application": app_clean,
            "message": f"Successfully launched {app_clean}",
        }

    async def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the user's default browser on macOS via /usr/bin/open."""
        url_clean = url.strip()
        parsed = urlparse(url_clean)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http and https URLs are allowed: '{url}'")

        cmd = ["/usr/bin/open", url_clean]
        logger.info("macos_open_url", url=url_clean)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Failed to open URL '{url_clean}': {err_msg}")

        return {
            "status": "success",
            "url": url_clean,
            "message": f"Opened {url_clean} in default browser",
        }

    async def read_file(self, path: str, max_bytes: int | None = None) -> str:
        """Safely read text content from a file."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: '{resolved}'")
        if not resolved.is_file():
            raise IsADirectoryError(f"Target is a directory, not a file: '{resolved}'")

        raw_bytes = resolved.read_bytes()
        if max_bytes is not None and len(raw_bytes) > max_bytes:
            raw_bytes = raw_bytes[:max_bytes]

        return raw_bytes.decode("utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Safely write or overwrite text content to a file."""
        resolved = Path(normalize_resource_target(path)).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "status": "success",
            "path": resolved.as_posix(),
            "bytes_written": len(content.encode("utf-8")),
        }

    async def move_file(self, source_path: str, dest_path: str) -> dict[str, Any]:
        """Safely move or rename a file."""
        src = Path(normalize_resource_target(source_path)).resolve()
        dst = Path(normalize_resource_target(dest_path)).resolve()

        if not src.exists():
            raise FileNotFoundError(f"Source file not found: '{src}'")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src.as_posix(), dst.as_posix())

        return {
            "status": "success",
            "source": src.as_posix(),
            "destination": dst.as_posix(),
        }

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Safely remove a file from disk."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: '{resolved}'")

        if resolved.is_dir():
            shutil.rmtree(resolved.as_posix())
        else:
            resolved.unlink()

        return {
            "status": "success",
            "deleted_path": resolved.as_posix(),
        }

    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        """Safely list directory contents with file metadata."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Directory not found: '{resolved}'")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Target is not a directory: '{resolved}'")

        items: list[dict[str, Any]] = []
        for entry in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            try:
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "path": entry.as_posix(),
                        "is_dir": entry.is_dir(),
                        "size_bytes": stat.st_size if entry.is_file() else 0,
                    }
                )
            except OSError:
                continue

        return items

    async def run_command(
        self,
        command: list[str],
        timeout_seconds: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Safely execute a controlled subprocess with strict timeouts and buffer caps."""
        if not command:
            raise ValueError("Command cannot be empty.")

        # Safeguard 1: Workspace / CWD Path Validation
        effective_cwd: str | None = None
        if cwd:
            resolved_cwd = Path(normalize_resource_target(cwd)).resolve()
            if not resolved_cwd.exists() or not resolved_cwd.is_dir():
                raise NotADirectoryError(f"Working directory does not exist: '{resolved_cwd}'")
            if is_protected_directory(resolved_cwd.as_posix()):
                raise ValueError(
                    f"Execution denied in protected system directory: '{resolved_cwd.as_posix()}'"
                )
            effective_cwd = resolved_cwd.as_posix()

        # Build clean environment
        clean_env = os.environ.copy()
        if env:
            clean_env.update(env)

        logger.info("macos_run_command_started", binary=command[0], cwd=effective_cwd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_cwd,
                env=clean_env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            exit_code = proc.returncode or 0

        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Command '{command[0]}' timed out after {timeout_seconds} seconds.")

        # Safeguard 2: Stdout/Stderr Buffer Caps (100 KB)
        stdout_truncated = False
        if len(stdout_bytes) > MAX_COMMAND_OUTPUT_BYTES:
            stdout_bytes = stdout_bytes[:MAX_COMMAND_OUTPUT_BYTES]
            stdout_truncated = True

        stderr_truncated = False
        if len(stderr_bytes) > MAX_COMMAND_OUTPUT_BYTES:
            stderr_bytes = stderr_bytes[:MAX_COMMAND_OUTPUT_BYTES]
            stderr_truncated = True

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        if stdout_truncated:
            stdout_str += f"\n[Output truncated at {MAX_COMMAND_OUTPUT_BYTES // 1024} KB]"

        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        if stderr_truncated:
            stderr_str += f"\n[Output truncated at {MAX_COMMAND_OUTPUT_BYTES // 1024} KB]"

        return {
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "cwd": effective_cwd,
            "truncated": stdout_truncated or stderr_truncated,
        }
