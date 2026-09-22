"""Windows Computer Control Adapter stub."""

from typing import Any

from packages.shared.nexus_shared.computer.base import ComputerControlAdapter


class WindowsAdapter(ComputerControlAdapter):
    """Stub adapter for Windows automation; supported on macOS in Phase 11."""

    async def open_application(self, app_name: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def open_url(self, url: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def read_file(self, path: str, max_bytes: int | None = None) -> str:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def move_file(self, source_path: str, dest_path: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def delete_file(self, path: str) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )

    async def run_command(
        self,
        command: list[str],
        timeout_seconds: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "WindowsAdapter is not implemented; supported on macOS in Phase 11."
        )
