"""NEXUS External Integrations & Connectors Package."""

from .base import BaseConnector
from .browser.session import (
    BrowserSessionManager,
    get_browser_session_manager,
)
from .browser.ssrf import SSRFSecurityViolation, validate_url_safe
from .browser.tools import (
    BrowserClickTool,
    BrowserGetSnapshotTool,
    BrowserNavigateTool,
    BrowserOpenLoginSessionTool,
    BrowserTypeTool,
)
from .browser_connector import BrowserConnector
from .crypto import decrypt_credentials, encrypt_credentials
from .github_connector import (
    GitHubConnector,
    GitHubCreateIssueTool,
    GitHubCreatePRTool,
    GitHubListIssuesTool,
    GitHubReadFileTool,
    get_user_github_token,
    set_user_github_token,
)
from .google_connector import (
    GoogleCreateCalendarEventTool,
    GoogleListCalendarEventsTool,
    GoogleSearchGmailTool,
    GoogleSendEmailTool,
    GoogleWorkspaceConnector,
    get_user_google_token,
    set_user_google_token,
)
from .macos import (
    MacOSCaptureWindowTool,
    MacOSClickElementTool,
    MacOSConnector,
    MacOSFocusAppTool,
    MacOSInspectUITool,
    MacOSListRunningAppsTool,
    MacOSSendShortcutTool,
    MacOSTypeTextTool,
    check_macos_permissions,
)

__all__ = [

    "BaseConnector",
    "BrowserClickTool",
    "BrowserConnector",
    "BrowserGetSnapshotTool",
    "BrowserNavigateTool",
    "BrowserOpenLoginSessionTool",
    "BrowserSessionManager",
    "BrowserTypeTool",
    "GitHubConnector",
    "GitHubCreateIssueTool",
    "GitHubCreatePRTool",
    "GitHubListIssuesTool",
    "GitHubReadFileTool",
    "GoogleCreateCalendarEventTool",
    "GoogleListCalendarEventsTool",
    "GoogleSearchGmailTool",
    "GoogleSendEmailTool",
    "GoogleWorkspaceConnector",
    "MacOSCaptureWindowTool",
    "MacOSClickElementTool",
    "MacOSConnector",
    "MacOSFocusAppTool",
    "MacOSInspectUITool",
    "MacOSListRunningAppsTool",
    "MacOSSendShortcutTool",
    "MacOSTypeTextTool",
    "SSRFSecurityViolation",
    "check_macos_permissions",
    "decrypt_credentials",
    "encrypt_credentials",
    "get_browser_session_manager",
    "get_user_github_token",
    "get_user_google_token",
    "set_user_github_token",
    "set_user_google_token",
    "validate_url_safe",
]
