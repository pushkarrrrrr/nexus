"""macOS Native Application Control Integration Package."""

from packages.shared.nexus_shared.integrations.macos.connector import MacOSConnector
from packages.shared.nexus_shared.integrations.macos.permissions import check_macos_permissions
from packages.shared.nexus_shared.integrations.macos.tools import (
    MacOSCaptureWindowTool,
    MacOSClickElementTool,
    MacOSFocusAppTool,
    MacOSInspectUITool,
    MacOSListRunningAppsTool,
    MacOSSendShortcutTool,
    MacOSTypeTextTool,
)

__all__ = [
    "MacOSCaptureWindowTool",
    "MacOSClickElementTool",
    "MacOSConnector",
    "MacOSFocusAppTool",
    "MacOSInspectUITool",
    "MacOSListRunningAppsTool",
    "MacOSSendShortcutTool",
    "MacOSTypeTextTool",
    "check_macos_permissions",
]
