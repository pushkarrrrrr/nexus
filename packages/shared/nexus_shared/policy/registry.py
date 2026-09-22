"""NEXUS Capability Registry

Standardized capabilities, categories, and baseline risk tiers.
"""

from dataclasses import dataclass
from typing import Literal

ActionCategory = Literal[
    "READ",
    "WRITE",
    "MODIFY",
    "DELETE",
    "EXECUTE",
    "EXTERNAL_ACTION",
    "SYSTEM_CONTROL",
]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    category: ActionCategory
    default_risk_level: RiskLevel
    description: str
    is_active: bool = True


DEFAULT_CAPABILITIES: list[CapabilityDefinition] = [
    CapabilityDefinition(
        name="filesystem.read",
        category="READ",
        default_risk_level="LOW",
        description="Read file contents and directory listings from local workspace",
    ),
    CapabilityDefinition(
        name="filesystem.write",
        category="WRITE",
        default_risk_level="MEDIUM",
        description="Create new files and directories within workspace",
    ),
    CapabilityDefinition(
        name="filesystem.modify",
        category="MODIFY",
        default_risk_level="MEDIUM",
        description="Modify existing files with rollback snapshotting",
    ),
    CapabilityDefinition(
        name="filesystem.delete",
        category="DELETE",
        default_risk_level="HIGH",
        description="Delete files and directories permanently",
    ),
    CapabilityDefinition(
        name="terminal.execute",
        category="EXECUTE",
        default_risk_level="HIGH",
        description="Execute shell/terminal commands in controlled sandbox",
    ),
    CapabilityDefinition(
        name="browser.open",
        category="EXTERNAL_ACTION",
        default_risk_level="MEDIUM",
        description="Open and navigate URLs in web browser",
    ),
    CapabilityDefinition(
        name="browser.interact",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Interact with DOM, type, and click on web pages",
    ),
    CapabilityDefinition(
        name="system.configure",
        category="MODIFY",
        default_risk_level="CRITICAL",
        description="Alter system configuration, security policies, and environment variables",
    ),
    CapabilityDefinition(
        name="network.request",
        category="EXTERNAL_ACTION",
        default_risk_level="MEDIUM",
        description="Send outbound HTTP requests to external endpoints",
    ),
    CapabilityDefinition(
        name="database.raw_query",
        category="EXECUTE",
        default_risk_level="HIGH",
        description="Execute arbitrary raw SQL queries against databases",
    ),
    # Phase 13: Browser Automation Capabilities
    CapabilityDefinition(
        name="browser.open_login_session",
        category="EXTERNAL_ACTION",
        default_risk_level="LOW",
        description="Launch visible persistent browser window for manual authentication",
    ),
    CapabilityDefinition(
        name="browser.navigate",
        category="EXTERNAL_ACTION",
        default_risk_level="LOW",
        description="Navigate to web URL within persistent profile",
    ),
    CapabilityDefinition(
        name="browser.get_snapshot",
        category="READ",
        default_risk_level="LOW",
        description="Read web page title, text, and DOM snapshot",
    ),
    CapabilityDefinition(
        name="browser.click",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Click DOM element within browser page (requires user approval)",
    ),
    CapabilityDefinition(
        name="browser.type",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Type text into form inputs within browser page (requires user approval)",
    ),
    # Phase 13: GitHub Integration Capabilities
    CapabilityDefinition(
        name="github.list_issues",
        category="READ",
        default_risk_level="LOW",
        description="List issues in a GitHub repository",
    ),
    CapabilityDefinition(
        name="github.read_file",
        category="READ",
        default_risk_level="LOW",
        description="Read file contents from a GitHub repository",
    ),
    CapabilityDefinition(
        name="github.create_issue",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Create issue in a GitHub repository (requires user approval)",
    ),
    CapabilityDefinition(
        name="github.create_pr",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Create pull request in a GitHub repository (requires user approval)",
    ),
    # Phase 13: Google Workspace Integration Capabilities
    CapabilityDefinition(
        name="google.list_calendar_events",
        category="READ",
        default_risk_level="LOW",
        description="List Google Calendar events in time window",
    ),
    CapabilityDefinition(
        name="google.create_calendar_event",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Create event in Google Calendar (requires user approval)",
    ),
    CapabilityDefinition(
        name="google.search_gmail",
        category="READ",
        default_risk_level="LOW",
        description="Search messages in Gmail",
    ),
    CapabilityDefinition(
        name="google.send_email",
        category="EXTERNAL_ACTION",
        default_risk_level="HIGH",
        description="Send email via Gmail (requires user approval)",
    ),
    # Native macOS Application Control Capabilities
    CapabilityDefinition(
        name="macos.list_running_apps",
        category="READ",
        default_risk_level="LOW",
        description="List active desktop applications on macOS",
    ),
    CapabilityDefinition(
        name="macos.focus_app",
        category="SYSTEM_CONTROL",
        default_risk_level="LOW",
        description="Bring macOS application window to the foreground",
    ),
    CapabilityDefinition(
        name="macos.inspect_ui",
        category="READ",
        default_risk_level="LOW",
        description="Inspect structured accessibility (AXUIElement) tree of target macOS application",
    ),
    CapabilityDefinition(
        name="macos.capture_window",
        category="READ",
        default_risk_level="LOW",
        description="Capture screenshot of macOS application window for visual grounding",
    ),
    CapabilityDefinition(
        name="macos.click_element",
        category="SYSTEM_CONTROL",
        default_risk_level="HIGH",
        description="Click element in target macOS application (requires user approval)",
    ),
    CapabilityDefinition(
        name="macos.type_text",
        category="SYSTEM_CONTROL",
        default_risk_level="HIGH",
        description="Type text or send keystrokes to macOS application (requires user approval)",
    ),
    CapabilityDefinition(
        name="macos.send_shortcut",
        category="SYSTEM_CONTROL",
        default_risk_level="HIGH",
        description="Send global shortcut keys to macOS application (requires user approval)",
    ),
]


class CapabilityRegistry:
    """Registry maintaining active system capabilities and base risk profiles."""

    def __init__(self, populate_defaults: bool = True) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        if populate_defaults:
            for cap in DEFAULT_CAPABILITIES:
                self.register(cap)

    def register(self, capability: CapabilityDefinition) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> CapabilityDefinition | None:
        return self._capabilities.get(name)

    def is_valid(self, name: str) -> bool:
        cap = self.get(name)
        return cap is not None and cap.is_active

    def get_risk_level(self, name: str) -> RiskLevel:
        cap = self.get(name)
        if cap is None:
            return "CRITICAL"
        return cap.default_risk_level

    def list_all(self) -> list[CapabilityDefinition]:
        return list(self._capabilities.values())


_global_registry: CapabilityRegistry | None = None


def get_capability_registry() -> CapabilityRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = CapabilityRegistry(populate_defaults=True)
    return _global_registry
