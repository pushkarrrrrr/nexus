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

    async def close_application(self, app_name: str) -> dict[str, Any]:
        """Close or quit an application on the host OS."""
        raise NotImplementedError("close_application is not implemented on this adapter")

    async def search_web(self, query: str) -> dict[str, Any]:
        """Search the web for a query in the default browser."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query.strip())
        return await self.open_url(f"https://www.google.com/search?q={encoded}")

    async def search_youtube(self, query: str) -> dict[str, Any]:
        """Search and play a video on YouTube in the default browser."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query.strip())
        return await self.open_url(f"https://www.youtube.com/results?search_query={encoded}")

    async def control_media(self, action: str) -> dict[str, Any]:
        """Perform a media or playback control action (play_pause, next, previous, etc.)."""
        raise NotImplementedError("control_media is not implemented on this adapter")

    async def spotify_play(self, query: str = "") -> dict[str, Any]:
        """Play a specific track/artist on Spotify or resume playback."""
        raise NotImplementedError("spotify_play is not implemented on this adapter")

    async def spotify_control(self, action: str) -> dict[str, Any]:
        """Control Spotify playback (next, previous, play_pause, pause, play)."""
        raise NotImplementedError("spotify_control is not implemented on this adapter")

    async def create_note(self, title: str, body: str) -> dict[str, Any]:
        """Create a new note in the native Notes application."""
        raise NotImplementedError("create_note is not implemented on this adapter")

    async def whatsapp_draft_message(self, contact: str, message: str) -> dict[str, Any]:
        """Stage a message in WhatsApp for a specific contact without sending it."""
        raise NotImplementedError("whatsapp_draft_message is not implemented on this adapter")

    async def whatsapp_confirm_send(self) -> dict[str, Any]:
        """Confirm and send the staged WhatsApp message."""
        raise NotImplementedError("whatsapp_confirm_send is not implemented on this adapter")

    async def whatsapp_cancel_send(self) -> dict[str, Any]:
        """Cancel the staged WhatsApp message."""
        raise NotImplementedError("whatsapp_cancel_send is not implemented on this adapter")

    async def scroll(self, direction: str = "down", amount: int = 5, delta_x: int = 0) -> dict[str, Any]:
        """Perform scrolling in the active window."""
        raise NotImplementedError("scroll is not implemented on this adapter")

    async def click_coords(self, x: int, y: int, button: str = "left", click_count: int = 1) -> dict[str, Any]:
        """Click at specific screen coordinates."""
        raise NotImplementedError("click_coords is not implemented on this adapter")

    async def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 15) -> dict[str, Any]:
        """Drag mouse between two screen coordinates."""
        raise NotImplementedError("mouse_drag is not implemented on this adapter")

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a keyboard key."""
        raise NotImplementedError("press_key is not implemented on this adapter")

    async def list_windows(self, on_screen_only: bool = True, filter_app: str | None = None) -> list[dict[str, Any]]:
        """List open application windows."""
        raise NotImplementedError("list_windows is not implemented on this adapter")

    async def read_window_content(self, app_name: str | None = None, window_index: int = 1, max_depth: int = 4) -> dict[str, Any]:
        """Read UI elements and text content from a window."""
        raise NotImplementedError("read_window_content is not implemented on this adapter")

    async def get_frontmost_app(self) -> str:
        """Get the name of the currently active frontmost application."""
        raise NotImplementedError("get_frontmost_app is not implemented on this adapter")

