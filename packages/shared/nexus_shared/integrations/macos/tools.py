"""Native macOS Application Control Tools for NEXUS."""

from typing import Any

from pydantic import BaseModel, Field

from packages.shared.nexus_shared.integrations.macos import engine
from packages.shared.nexus_shared.tools.base import BaseTool


# -----------------------------------------------------------------------------
# 1. macos.list_running_apps
# -----------------------------------------------------------------------------
class MacOSListRunningAppsInput(BaseModel):
    filter_name: str | None = Field(
        default=None,
        description="Optional filter string to match application names (case-insensitive).",
    )


class MacOSAppItem(BaseModel):
    app_name: str
    bundle_id: str
    pid: int
    is_frontmost: bool


class MacOSListRunningAppsOutput(BaseModel):
    apps: list[MacOSAppItem]
    count: int


class MacOSListRunningAppsTool(BaseTool):
    name = "macos.list_running_apps"
    description = "List currently running macOS graphical applications with name, bundle ID, PID, and frontmost status."
    input_schema = MacOSListRunningAppsInput
    output_schema = MacOSListRunningAppsOutput
    required_capability = "macos.list_running_apps"
    default_risk_level = "LOW"
    timeout_seconds = 15.0

    async def run(
        self,
        user_id: str,
        params: MacOSListRunningAppsInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSListRunningAppsOutput:
        raw_apps = await engine.list_applications()
        apps: list[MacOSAppItem] = []
        filter_str = params.filter_name.lower() if params.filter_name else None

        for item in raw_apps:
            app_name = item.get("app_name", "")
            if filter_str and filter_str not in app_name.lower():
                continue
            apps.append(
                MacOSAppItem(
                    app_name=app_name,
                    bundle_id=item.get("bundle_id", ""),
                    pid=item.get("pid", 0),
                    is_frontmost=item.get("is_frontmost", False),
                )
            )

        return MacOSListRunningAppsOutput(apps=apps, count=len(apps))


# -----------------------------------------------------------------------------
# 2. macos.focus_app
# -----------------------------------------------------------------------------
class MacOSFocusAppInput(BaseModel):
    app_name: str = Field(..., description="Name of the application to activate and bring to foreground.")


class MacOSFocusAppOutput(BaseModel):
    success: bool
    app_name: str
    message: str


class MacOSFocusAppTool(BaseTool):
    name = "macos.focus_app"
    description = "Bring the specified macOS application window to the foreground."
    input_schema = MacOSFocusAppInput
    output_schema = MacOSFocusAppOutput
    required_capability = "macos.focus_app"
    default_risk_level = "LOW"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSFocusAppInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSFocusAppOutput:
        success = await engine.focus_application(params.app_name)
        return MacOSFocusAppOutput(
            success=success,
            app_name=params.app_name,
            message=f"Application '{params.app_name}' activated and brought to foreground.",
        )


# -----------------------------------------------------------------------------
# 3. macos.inspect_ui
# -----------------------------------------------------------------------------
class MacOSInspectUIInput(BaseModel):
    app_name: str = Field(..., description="Target application name to inspect accessibility hierarchy for.")
    max_depth: int = Field(default=3, description="Maximum tree depth to traverse (default 3, max 5).")


class MacOSInspectUIOutput(BaseModel):
    app_name: str
    pid: int
    window_count: int
    tree: list[dict[str, Any]]


class MacOSInspectUITool(BaseTool):
    name = "macos.inspect_ui"
    description = "Dumps the structured accessibility (AXUIElement) tree of target macOS app, pruning empty containers."
    input_schema = MacOSInspectUIInput
    output_schema = MacOSInspectUIOutput
    required_capability = "macos.inspect_ui"
    default_risk_level = "LOW"
    timeout_seconds = 20.0

    async def run(
        self,
        user_id: str,
        params: MacOSInspectUIInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSInspectUIOutput:
        depth = min(max(params.max_depth, 1), 5)
        res = await engine.inspect_element_tree(params.app_name, max_depth=depth)
        return MacOSInspectUIOutput(
            app_name=res.get("app_name", params.app_name),
            pid=res.get("pid", 0),
            window_count=res.get("window_count", 0),
            tree=res.get("tree", []),
        )


# -----------------------------------------------------------------------------
# 4. macos.capture_window
# -----------------------------------------------------------------------------
class MacOSCaptureWindowInput(BaseModel):
    app_name: str = Field(..., description="Target application name.")
    window_id: int | None = Field(default=None, description="Optional specific window ID.")


class MacOSCaptureWindowOutput(BaseModel):
    app_name: str
    window_id: int | None
    format: str
    width: int
    height: int
    size_bytes: int
    data_base64: str


class MacOSCaptureWindowTool(BaseTool):
    name = "macos.capture_window"
    description = "Captures a screenshot of the target macOS application window returning base64 PNG data for visual grounding."
    input_schema = MacOSCaptureWindowInput
    output_schema = MacOSCaptureWindowOutput
    required_capability = "macos.capture_window"
    default_risk_level = "LOW"
    timeout_seconds = 15.0

    async def run(
        self,
        user_id: str,
        params: MacOSCaptureWindowInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSCaptureWindowOutput:
        res = await engine.capture_window_image(params.app_name, window_id=params.window_id)
        return MacOSCaptureWindowOutput(
            app_name=res["app_name"],
            window_id=res["window_id"],
            format=res["format"],
            width=res["width"],
            height=res["height"],
            size_bytes=res["size_bytes"],
            data_base64=res["data_base64"],
        )


# -----------------------------------------------------------------------------
# 5. macos.click_element
# -----------------------------------------------------------------------------
class MacOSClickElementInput(BaseModel):
    app_name: str = Field(..., description="Target application name.")
    role: str = Field(default="", description="UI element role (e.g. 'AXButton', 'AXMenuItem', 'AXPopUpButton').")
    title: str = Field(..., description="Title, label, or description of the UI element to click.")


class MacOSClickElementOutput(BaseModel):
    success: bool
    app_name: str
    role: str
    title: str
    message: str


class MacOSClickElementTool(BaseTool):
    name = "macos.click_element"
    description = "Click an element in the target macOS application by role and title using native AXPress or fallback click."
    input_schema = MacOSClickElementInput
    output_schema = MacOSClickElementOutput
    required_capability = "macos.click_element"
    default_risk_level = "HIGH"
    timeout_seconds = 15.0

    async def run(
        self,
        user_id: str,
        params: MacOSClickElementInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSClickElementOutput:
        success = await engine.ax_click_element(params.app_name, role=params.role, title=params.title)
        return MacOSClickElementOutput(
            success=success,
            app_name=params.app_name,
            role=params.role,
            title=params.title,
            message=f"Clicked element with title '{params.title}' (role: '{params.role}') in {params.app_name}.",
        )


# -----------------------------------------------------------------------------
# 6. macos.type_text
# -----------------------------------------------------------------------------
class MacOSTypeTextInput(BaseModel):
    app_name: str = Field(..., description="Target application name.")
    text: str = Field(..., description="Text string to type into the focused input element.")
    submit_key: str | None = Field(
        default=None,
        description="Optional key to press after typing (e.g. 'enter', 'return', 'tab').",
    )


class MacOSTypeTextOutput(BaseModel):
    success: bool
    app_name: str
    typed_length: int
    message: str


class MacOSTypeTextTool(BaseTool):
    name = "macos.type_text"
    description = "Set text or send synthetic keystrokes into the focused input element of target macOS application."
    input_schema = MacOSTypeTextInput
    output_schema = MacOSTypeTextOutput
    required_capability = "macos.type_text"
    default_risk_level = "HIGH"
    timeout_seconds = 15.0

    async def run(
        self,
        user_id: str,
        params: MacOSTypeTextInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSTypeTextOutput:
        success = await engine.ax_set_value(params.app_name, text=params.text, submit_key=params.submit_key)
        return MacOSTypeTextOutput(
            success=success,
            app_name=params.app_name,
            typed_length=len(params.text),
            message=f"Successfully typed {len(params.text)} characters into {params.app_name}.",
        )


# -----------------------------------------------------------------------------
# 7. macos.send_shortcut
# -----------------------------------------------------------------------------
class MacOSSendShortcutInput(BaseModel):
    app_name: str = Field(..., description="Target application name.")
    key: str = Field(..., description="Primary key character or name (e.g., 'n', 's', 'return', 'space').")
    modifiers: list[str] = Field(
        ...,
        description="Modifier keys to apply, e.g. ['cmd'], ['cmd', 'shift'], ['alt'], ['ctrl'].",
    )


class MacOSSendShortcutOutput(BaseModel):
    success: bool
    app_name: str
    key: str
    modifiers: list[str]
    message: str


class MacOSSendShortcutTool(BaseTool):
    name = "macos.send_shortcut"
    description = "Send a global shortcut key combination to the target macOS application (e.g. cmd+n, cmd+s)."
    input_schema = MacOSSendShortcutInput
    output_schema = MacOSSendShortcutOutput
    required_capability = "macos.send_shortcut"
    default_risk_level = "HIGH"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSSendShortcutInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSSendShortcutOutput:
        # First ensure app is focused
        try:
            await engine.focus_application(params.app_name)
        except Exception:  # noqa: BLE001, S110
            pass

        success = engine.post_shortcut(params.key, params.modifiers)
        mod_str = "+".join(params.modifiers)
        return MacOSSendShortcutOutput(
            success=success,
            app_name=params.app_name,
            key=params.key,
            modifiers=params.modifiers,
            message=f"Dispatched shortcut '{mod_str}+{params.key}' to {params.app_name}.",
        )
