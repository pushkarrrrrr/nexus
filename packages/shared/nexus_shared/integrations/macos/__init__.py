"""macOS Native Application Control Integration Package."""

from packages.shared.nexus_shared.integrations.macos.connector import MacOSConnector
from packages.shared.nexus_shared.integrations.macos.permissions import check_macos_permissions
from packages.shared.nexus_shared.integrations.macos.tools import (
    MacOSCaptureWindowTool,
    MacOSClickCoordsTool,
    MacOSClickElementTool,
    MacOSFocusAppTool,
    MacOSInspectUITool,
    MacOSListRunningAppsTool,
    MacOSListWindowsTool,
    MacOSMouseDragTool,
    MacOSPressKeyTool,
    MacOSReadWindowContentTool,
    MacOSScrollTool,
    MacOSSendShortcutTool,
    MacOSTypeTextTool,
)

__all__ = [
    "MacOSCaptureWindowTool",
    "MacOSClickCoordsTool",
    "MacOSClickElementTool",
    "MacOSConnector",
    "MacOSFocusAppTool",
    "MacOSInspectUITool",
    "MacOSListRunningAppsTool",
    "MacOSListWindowsTool",
    "MacOSMouseDragTool",
    "MacOSPressKeyTool",
    "MacOSReadWindowContentTool",
    "MacOSScrollTool",
    "MacOSSendShortcutTool",
    "MacOSTypeTextTool",
    "check_macos_permissions",
]
