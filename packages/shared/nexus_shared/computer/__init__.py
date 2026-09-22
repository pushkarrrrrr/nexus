"""Computer Control Adapter package for OS-level controlled actions."""

import sys

from .base import (
    MAX_COMMAND_OUTPUT_BYTES,
    PROTECTED_SYSTEM_DIRS,
    ComputerControlAdapter,
    is_protected_directory,
)
from .linux import LinuxAdapter
from .macos import MacOSAdapter
from .windows import WindowsAdapter

_adapter_instance: ComputerControlAdapter | None = None


def get_computer_adapter() -> ComputerControlAdapter:
    """Return the singleton computer control adapter for the host operating system."""
    global _adapter_instance
    if _adapter_instance is None:
        if sys.platform == "darwin":
            _adapter_instance = MacOSAdapter()
        elif sys.platform.startswith("win"):
            _adapter_instance = WindowsAdapter()
        else:
            _adapter_instance = LinuxAdapter()
    return _adapter_instance


__all__ = [
    "MAX_COMMAND_OUTPUT_BYTES",
    "PROTECTED_SYSTEM_DIRS",
    "ComputerControlAdapter",
    "LinuxAdapter",
    "MacOSAdapter",
    "WindowsAdapter",
    "get_computer_adapter",
    "is_protected_directory",
]
