"""Browser Automation Connector implementing BaseConnector lifecycle."""

from typing import Any

from packages.shared.nexus_shared.integrations.base import BaseConnector
from packages.shared.nexus_shared.integrations.browser.session import (
    BrowserSessionManager,
    get_browser_session_manager,
)
from packages.shared.nexus_shared.integrations.browser.tools import (
    BrowserClickTool,
    BrowserGetSnapshotTool,
    BrowserNavigateTool,
    BrowserOpenLoginSessionTool,
    BrowserTypeTool,
)
from packages.shared.nexus_shared.tools.base import BaseTool


class BrowserConnector(BaseConnector):
    """Browser Automation Connector managing user profile sessions and Playwright tools."""

    provider = "browser"

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        self.session_manager = session_manager or get_browser_session_manager()

    async def connect(
        self,
        user_id: str,
        credentials: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        # Browser profile directory created and verified
        profile_dir = self.session_manager.get_user_profile_dir(user_id)
        return profile_dir.exists()

    async def disconnect(self, user_id: str) -> bool:
        # Close running context
        await self.session_manager.close_session(user_id)
        return True

    async def health_check(self, user_id: str) -> dict[str, Any]:
        profile_dir = self.session_manager.get_user_profile_dir(user_id)
        return {
            "provider": self.provider,
            "status": "healthy",
            "profile_dir": str(profile_dir),
            "engine": "playwright.chromium",
        }

    def register_tools(self) -> list[BaseTool]:
        return [
            BrowserOpenLoginSessionTool(self.session_manager),
            BrowserNavigateTool(self.session_manager),
            BrowserGetSnapshotTool(self.session_manager),
            BrowserClickTool(self.session_manager),
            BrowserTypeTool(self.session_manager),
        ]
