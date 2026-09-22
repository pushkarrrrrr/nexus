"""Base interfaces and constants for Operating System Computer Control Adapters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from packages.shared.nexus_shared.policy.utils import normalize_resource_target

# Safeguard 2: Strict maximum output buffer cap (100 KB)
MAX_COMMAND_OUTPUT_BYTES = 100 * 1024

# Safeguard 1: Protected system directories that must NEVER be used as CWD
PROTECTED_SYSTEM_DIRS: tuple[str, ...] = (
    "/",
    "/etc",
    "/var",
    "/bin",
    "/sbin",
    "/usr",
    "/System",
    "/Library",
    "/private",
    "/dev",
    "/proc",
    "/sys",
)


def is_protected_directory(path_str: str) -> bool:
    """Check if resolved path targets a protected system directory or sensitive user root."""
    try:
        resolved = Path(normalize_resource_target(path_str)).resolve()
        resolved_str = resolved.as_posix()

        # Check root or direct system directory
        if resolved_str in PROTECTED_SYSTEM_DIRS:
            return True

        # Check system subdirectories
        for pdir in ("/etc", "/var", "/System", "/private", "/bin", "/sbin"):
            if resolved_str == pdir or resolved_str.startswith(f"{pdir}/"):
                return True

        # Sensitive user directories (e.g. ~/.ssh, ~/.gnupg)
        home = Path.home().resolve().as_posix()
        if resolved_str in (f"{home}/.ssh", f"{home}/.gnupg"):
            return True
        return resolved_str.startswith((f"{home}/.ssh/", f"{home}/.gnupg/"))
    except (ValueError, OSError, RuntimeError):
        return True


class ComputerControlAdapter(ABC):
    """Abstract Base Class for OS-level automation and controlled computer interaction."""

    @abstractmethod
    async def open_application(self, app_name: str) -> dict[str, Any]:
        """Launch an approved application on the host OS."""
        ...

    @abstractmethod
    async def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the user's default browser."""
        ...

    @abstractmethod
    async def read_file(self, path: str, max_bytes: int | None = None) -> str:
        """Safely read text content from a file."""
        ...

    @abstractmethod
    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Safely write or overwrite text content to a file."""
        ...

    @abstractmethod
    async def move_file(self, source_path: str, dest_path: str) -> dict[str, Any]:
        """Safely move or rename a file."""
        ...

    @abstractmethod
    async def delete_file(self, path: str) -> dict[str, Any]:
        """Safely remove a file from disk."""
        ...

    @abstractmethod
    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        """Safely list directory contents with file metadata."""
        ...

    @abstractmethod
    async def run_command(
        self,
        command: list[str],
        timeout_seconds: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Safely execute a controlled subprocess with strict timeouts and buffer caps."""
        ...
