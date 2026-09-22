"""Playwright-powered Browser Automation Tools for NEXUS."""

import asyncio
import base64
from typing import Any

from pydantic import BaseModel, Field

from packages.shared.nexus_shared.integrations.browser.session import (
    BrowserSessionManager,
    get_browser_session_manager,
)
from packages.shared.nexus_shared.integrations.browser.ssrf import validate_url_safe
from packages.shared.nexus_shared.tools.base import BaseTool


# -----------------------------------------------------------------------------
# 1. browser.open_login_session
# -----------------------------------------------------------------------------
class BrowserOpenLoginSessionInput(BaseModel):
    url: str = Field(..., description="The login target URL to load in the visible browser.")
    timeout_seconds: int = Field(
        default=180,
        description="Duration in seconds to keep visible window open for manual 2FA/QR scanning.",
    )


class BrowserOpenLoginSessionOutput(BaseModel):
    success: bool
    url: str
    message: str


class BrowserOpenLoginSessionTool(BaseTool):
    name = "browser.open_login_session"
    description = "Launch a visible persistent browser window for manual authentication (QR code, 2FA, CAPTCHA)."
    input_schema = BrowserOpenLoginSessionInput
    output_schema = BrowserOpenLoginSessionOutput
    required_capability = "browser.open_login_session"
    default_risk_level = "LOW"
    timeout_seconds = 240.0
    is_reversible = False

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        super().__init__()
        self.session_manager = session_manager or get_browser_session_manager()

    async def run(
        self,
        user_id: str,
        params: BrowserOpenLoginSessionInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserOpenLoginSessionOutput:
        safe_url = validate_url_safe(params.url)
        page = await self.session_manager.get_active_page(user_id, headless=False)
        await page.goto(safe_url, timeout=30000, wait_until="domcontentloaded")

        # Wait for user authentication window
        try:
            await asyncio.sleep(min(params.timeout_seconds, 180))
        except asyncio.CancelledError:
            pass

        # Switch back to headless by closing visible session (profile remains saved on disk)
        await self.session_manager.close_session(user_id)

        return BrowserOpenLoginSessionOutput(
            success=True,
            url=safe_url,
            message="Visible authentication session completed. Persistent profile saved to disk.",
        )


# -----------------------------------------------------------------------------
# 2. browser.navigate
# -----------------------------------------------------------------------------
class BrowserNavigateInput(BaseModel):
    url: str = Field(..., description="Target web URL to navigate to within persistent profile.")


class BrowserNavigateOutput(BaseModel):
    url: str
    title: str
    status_code: int = 200


class BrowserNavigateTool(BaseTool):
    name = "browser.navigate"
    description = "Navigate to a web URL within the persistent browser session."
    input_schema = BrowserNavigateInput
    output_schema = BrowserNavigateOutput
    required_capability = "browser.navigate"
    default_risk_level = "LOW"
    timeout_seconds = 45.0
    is_reversible = False

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        super().__init__()
        self.session_manager = session_manager or get_browser_session_manager()

    async def run(
        self,
        user_id: str,
        params: BrowserNavigateInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserNavigateOutput:
        safe_url = validate_url_safe(params.url)
        page = await self.session_manager.get_active_page(user_id, headless=True)
        resp = await page.goto(safe_url, timeout=30000, wait_until="domcontentloaded")
        title = await page.title()
        status = resp.status if resp else 200
        return BrowserNavigateOutput(url=safe_url, title=title, status_code=status)


# -----------------------------------------------------------------------------
# 3. browser.get_snapshot
# -----------------------------------------------------------------------------
class BrowserGetSnapshotInput(BaseModel):
    extract_text: bool = Field(default=True, description="Extract text content and DOM summary.")
    capture_screenshot: bool = Field(default=False, description="Capture base64 viewport screenshot.")


class BrowserGetSnapshotOutput(BaseModel):
    url: str
    title: str
    text_content: str | None = None
    screenshot_base64: str | None = None


class BrowserGetSnapshotTool(BaseTool):
    name = "browser.get_snapshot"
    description = "Inspect current web page state, text summary, and accessibility snapshot."
    input_schema = BrowserGetSnapshotInput
    output_schema = BrowserGetSnapshotOutput
    required_capability = "browser.get_snapshot"
    default_risk_level = "LOW"
    timeout_seconds = 30.0
    is_reversible = False

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        super().__init__()
        self.session_manager = session_manager or get_browser_session_manager()

    async def run(
        self,
        user_id: str,
        params: BrowserGetSnapshotInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserGetSnapshotOutput:
        page = await self.session_manager.get_active_page(user_id, headless=True)
        title = await page.title()
        url = page.url

        text_content: str | None = None
        if params.extract_text:
            text_content = await page.inner_text("body")

        screenshot_b64: str | None = None
        if params.capture_screenshot:
            screenshot_bytes = await page.screenshot(type="png")
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")

        return BrowserGetSnapshotOutput(
            url=url,
            title=title,
            text_content=text_content[:4000] if text_content else None,
            screenshot_base64=screenshot_b64,
        )


# -----------------------------------------------------------------------------
# 4. browser.click (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class BrowserClickInput(BaseModel):
    selector: str = Field(..., description="Target CSS or text selector to click.")


class BrowserClickOutput(BaseModel):
    success: bool
    selector: str
    current_url: str


class BrowserClickTool(BaseTool):
    name = "browser.click"
    description = "Click an element or button on the current web page (requires user approval)."
    input_schema = BrowserClickInput
    output_schema = BrowserClickOutput
    required_capability = "browser.click"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0
    is_reversible = False

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        super().__init__()
        self.session_manager = session_manager or get_browser_session_manager()

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return f"selector:{validated_params.model_dump().get('selector', '')}"

    async def run(
        self,
        user_id: str,
        params: BrowserClickInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserClickOutput:
        page = await self.session_manager.get_active_page(user_id, headless=True)
        await page.click(params.selector, timeout=10000)
        return BrowserClickOutput(
            success=True,
            selector=params.selector,
            current_url=page.url,
        )


# -----------------------------------------------------------------------------
# 5. browser.type (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class BrowserTypeInput(BaseModel):
    selector: str = Field(..., description="Input element CSS or text selector.")
    text: str = Field(..., description="Text to enter into the input element.")
    submit: bool = Field(default=False, description="Whether to press Enter after typing.")


class BrowserTypeOutput(BaseModel):
    success: bool
    selector: str
    submitted: bool


class BrowserTypeTool(BaseTool):
    name = "browser.type"
    description = "Type text into a web form input or textarea (requires user approval)."
    input_schema = BrowserTypeInput
    output_schema = BrowserTypeOutput
    required_capability = "browser.type"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0
    is_reversible = False

    def __init__(self, session_manager: BrowserSessionManager | None = None) -> None:
        super().__init__()
        self.session_manager = session_manager or get_browser_session_manager()

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return f"selector:{validated_params.model_dump().get('selector', '')}"

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        return str(validated_params.model_dump().get("text", ""))

    async def run(
        self,
        user_id: str,
        params: BrowserTypeInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserTypeOutput:
        page = await self.session_manager.get_active_page(user_id, headless=True)
        await page.fill(params.selector, params.text, timeout=10000)
        if params.submit:
            await page.press(params.selector, "Enter")
        return BrowserTypeOutput(
            success=True,
            selector=params.selector,
            submitted=params.submit,
        )
