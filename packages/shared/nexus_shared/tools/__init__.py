"""NEXUS Tool System Package."""

from .base import BaseTool, ToolResult
from .registry import ToolRegistry, get_tool_registry
from .standard.application_tools import (
    ApplicationCloseTool,
    ApplicationOpenTool,
    BrowserOpenUrlTool,
    BrowserSearchTool,
    MediaControlTool,
    YouTubePlayTool,
)
from .standard.filesystem_tools import (
    FilesystemDeleteTool,
    FilesystemListDirTool,
    FilesystemMoveTool,
    FilesystemReadTool,
    FilesystemWriteTool,
)
from .standard.terminal_tool import TerminalExecuteTool

__all__ = [
    "ApplicationCloseTool",
    "ApplicationOpenTool",
    "BaseTool",
    "BrowserOpenUrlTool",
    "BrowserSearchTool",
    "FilesystemDeleteTool",
    "FilesystemListDirTool",
    "FilesystemMoveTool",
    "FilesystemReadTool",
    "FilesystemWriteTool",
    "MediaControlTool",
    "TerminalExecuteTool",
    "ToolRegistry",
    "ToolResult",
    "YouTubePlayTool",
    "get_tool_registry",
]
