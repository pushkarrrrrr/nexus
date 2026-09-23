"""Central Tool Registry for NEXUS."""

from typing import Any

from packages.shared.nexus_shared.integrations.browser.tools import (
    BrowserClickTool,
    BrowserGetSnapshotTool,
    BrowserNavigateTool,
    BrowserOpenLoginSessionTool,
    BrowserTypeTool,
)
from packages.shared.nexus_shared.integrations.github_connector import (
    GitHubCreateIssueTool,
    GitHubCreatePRTool,
    GitHubListIssuesTool,
    GitHubReadFileTool,
)
from packages.shared.nexus_shared.integrations.google_connector import (
    GoogleCreateCalendarEventTool,
    GoogleListCalendarEventsTool,
    GoogleSearchGmailTool,
    GoogleSendEmailTool,
)
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
from packages.shared.nexus_shared.tools.standard.application_tools import (
    ApplicationOpenTool,
    BrowserOpenUrlTool,
)
from packages.shared.nexus_shared.tools.standard.filesystem_tools import (
    FilesystemDeleteTool,
    FilesystemListDirTool,
    FilesystemMoveTool,
    FilesystemReadTool,
    FilesystemWriteTool,
)
from packages.shared.nexus_shared.tools.standard.proactive_tools import (
    RemediationExecuteFixTool,
    RemediationTriggerRecoveryTool,
    TriggerCreateRuleTool,
    TriggerListRulesTool,
    WatcherGetSystemMetricsTool,
    WatcherInspectEventsTool,
)
from packages.shared.nexus_shared.tools.standard.terminal_tool import TerminalExecuteTool

logger = get_logger("nexus.tools.registry")


class ToolRegistry:
    """Singleton registry managing all system capability tools and schema reflection."""

    def __init__(self, load_defaults: bool = True) -> None:
        self._tools: dict[str, BaseTool] = {}
        if load_defaults:
            self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the baseline standard tool library and external integrations."""
        default_tools: list[BaseTool] = [
            FilesystemReadTool(),
            FilesystemWriteTool(),
            FilesystemMoveTool(),
            FilesystemDeleteTool(),
            FilesystemListDirTool(),
            TerminalExecuteTool(),
            ApplicationOpenTool(),
            BrowserOpenUrlTool(),
            # Phase 13: Browser Automation Tools
            BrowserOpenLoginSessionTool(),
            BrowserNavigateTool(),
            BrowserGetSnapshotTool(),
            BrowserClickTool(),
            BrowserTypeTool(),
            # Phase 13: GitHub Tools
            GitHubListIssuesTool(),
            GitHubReadFileTool(),
            GitHubCreateIssueTool(),
            GitHubCreatePRTool(),
            # Phase 13: Google Workspace Tools
            GoogleListCalendarEventsTool(),
            GoogleCreateCalendarEventTool(),
            GoogleSearchGmailTool(),
            GoogleSendEmailTool(),
            # Native macOS Application Control Tools
            MacOSListRunningAppsTool(),
            MacOSFocusAppTool(),
            MacOSInspectUITool(),
            MacOSCaptureWindowTool(),
            MacOSClickElementTool(),
            MacOSTypeTextTool(),
            MacOSSendShortcutTool(),
            # Phase 14: Proactive Watchers, Triggers & Self-Healing Tools
            WatcherGetSystemMetricsTool(),
            WatcherInspectEventsTool(),
            TriggerCreateRuleTool(),
            TriggerListRulesTool(),
            RemediationExecuteFixTool(),
            RemediationTriggerRecoveryTool(),
        ]
        for tool in default_tools:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        self._tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name, capability=tool.required_capability)

    def get(self, name: str) -> BaseTool | None:
        """Retrieve a registered tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_schemas_for_llm(self) -> list[dict[str, Any]]:
        """Return OpenAI / JSON schema tool definitions for agent prompt injection."""
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema.model_json_schema(),
                    },
                }
            )
        return schemas


_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the global ToolRegistry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry(load_defaults=True)
    return _global_registry
