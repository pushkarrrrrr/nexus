"""MacOSConnector implementing BaseConnector lifecycle for Native macOS Application Control."""

import platform
from typing import Any

from packages.shared.nexus_shared.integrations.base import BaseConnector
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
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.tools.base import BaseTool

logger = get_logger("nexus.integrations.macos.connector")


class MacOSConnector(BaseConnector):
    """Connector for native macOS application automation, accessibility inspection, and input injection."""

    provider = "macos"

    async def connect(
        self,
        user_id: str,
        credentials: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Initialize and verify macOS native control capability for the user."""
        is_darwin = platform.system() == "Darwin"
        perms = check_macos_permissions()
        logger.info(
            "macos_connector_connect",
            user_id=user_id,
            is_darwin=is_darwin,
            accessibility=perms.get("accessibility_trusted", False),
            screen_capture=perms.get("screen_capture_allowed", False),
        )
        return is_darwin

    async def disconnect(self, user_id: str) -> bool:
        """Clean up or disable native macOS control integration for the user."""
        logger.info("macos_connector_disconnect", user_id=user_id)
        return True

    async def health_check(self, user_id: str) -> dict[str, Any]:
        """Inspect macOS platform health, TCC status, and tool availability."""
        perms = check_macos_permissions()
        is_darwin = platform.system() == "Darwin"
        status = (
            "healthy" if (is_darwin and perms.get("accessibility_trusted", False)) else "degraded"
        )
        if not is_darwin:
            status = "unsupported"

        return {
            "provider": self.provider,
            "status": status,
            "is_darwin": is_darwin,
            "permissions": perms,
            "tool_count": 7,
        }

    def register_tools(self) -> list[BaseTool]:
        """Return the 7 native macOS application control tools."""
        return [
            MacOSListRunningAppsTool(),
            MacOSFocusAppTool(),
            MacOSInspectUITool(),
            MacOSCaptureWindowTool(),
            MacOSClickElementTool(),
            MacOSTypeTextTool(),
            MacOSSendShortcutTool(),
        ]
