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
    app_name: str = Field(
        ..., description="Name of the application to activate and bring to foreground."
    )


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
    app_name: str = Field(
        ..., description="Target application name to inspect accessibility hierarchy for."
    )
    max_depth: int = Field(
        default=3, description="Maximum tree depth to traverse (default 3, max 5)."
    )


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
    role: str = Field(
        default="", description="UI element role (e.g. 'AXButton', 'AXMenuItem', 'AXPopUpButton')."
    )
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
        success = await engine.ax_click_element(
            params.app_name, role=params.role, title=params.title
        )
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
        success = await engine.ax_set_value(
            params.app_name, text=params.text, submit_key=params.submit_key
        )
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
    key: str = Field(
        ..., description="Primary key character or name (e.g., 'n', 's', 'return', 'space')."
    )
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


# -----------------------------------------------------------------------------
# 8. macos.list_windows
# -----------------------------------------------------------------------------
class MacOSWindowBounds(BaseModel):
    x: float
    y: float
    width: float
    height: float


class MacOSWindowInfo(BaseModel):
    id: int
    owner_name: str
    name: str
    layer: int
    pid: int
    bounds: MacOSWindowBounds
    is_onscreen: bool


class MacOSListWindowsInput(BaseModel):
    on_screen_only: bool = Field(
        default=True,
        description="Filter to windows that are currently visible on screen (default True).",
    )
    filter_app: str | None = Field(
        default=None,
        description="Optional filter by application name (case-insensitive).",
    )


class MacOSListWindowsOutput(BaseModel):
    windows: list[MacOSWindowInfo]
    count: int


class MacOSListWindowsTool(BaseTool):
    name = "macos.list_windows"
    description = (
        "Enumerate all open desktop windows across applications with window ID, title, "
        "owner application, layer, and pixel bounding coordinates."
    )
    input_schema = MacOSListWindowsInput
    output_schema = MacOSListWindowsOutput
    required_capability = "macos.list_windows"
    default_risk_level = "LOW"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSListWindowsInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSListWindowsOutput:
        raw_windows = engine.list_all_windows(
            on_screen_only=params.on_screen_only,
            filter_app=params.filter_app,
        )
        windows: list[MacOSWindowInfo] = [
            MacOSWindowInfo(
                id=w.get("id", 0),
                owner_name=w.get("owner_name", ""),
                name=w.get("name", ""),
                layer=w.get("layer", 0),
                pid=w.get("pid", 0),
                bounds=MacOSWindowBounds(
                    x=w.get("bounds", {}).get("x", 0.0),
                    y=w.get("bounds", {}).get("y", 0.0),
                    width=w.get("bounds", {}).get("width", 0.0),
                    height=w.get("bounds", {}).get("height", 0.0),
                ),
                is_onscreen=w.get("is_onscreen", True),
            )
            for w in raw_windows
        ]
        return MacOSListWindowsOutput(windows=windows, count=len(windows))


# -----------------------------------------------------------------------------
# 9. macos.read_window_content
# -----------------------------------------------------------------------------
class MacOSReadWindowContentInput(BaseModel):
    app_name: str | None = Field(
        default=None,
        description="Application to inspect. If null, inspects the current frontmost application.",
    )
    window_index: int = Field(
        default=0,
        description="Index of window to inspect if multiple are open (0 is frontmost).",
    )
    max_depth: int = Field(
        default=4,
        description="Maximum accessibility hierarchy traversal depth.",
    )


class MacOSUIElementSummary(BaseModel):
    role: str
    text: str
    position: list[float]
    size: list[float]


class MacOSReadWindowContentOutput(BaseModel):
    app_name: str
    window_title: str
    text_content: str
    elements: list[MacOSUIElementSummary]


class MacOSReadWindowContentTool(BaseTool):
    name = "macos.read_window_content"
    description = (
        "Extract visible text lines, labels, inputs, and UI elements from a window in reading order "
        "via native accessibility inspection."
    )
    input_schema = MacOSReadWindowContentInput
    output_schema = MacOSReadWindowContentOutput
    required_capability = "macos.read_window_content"
    default_risk_level = "LOW"
    timeout_seconds = 20.0

    async def run(
        self,
        user_id: str,
        params: MacOSReadWindowContentInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSReadWindowContentOutput:
        res = await engine.read_window_content(
            app_name=params.app_name,
            window_index=params.window_index,
            max_depth=params.max_depth,
        )
        elems: list[MacOSUIElementSummary] = [
            MacOSUIElementSummary(
                role=e.get("role", ""),
                text=e.get("text", ""),
                position=[float(p) for p in e.get("position", [0, 0])],
                size=[float(s) for s in e.get("size", [0, 0])],
            )
            for e in res.get("elements", [])
        ]
        return MacOSReadWindowContentOutput(
            app_name=res.get("app_name", params.app_name or ""),
            window_title=res.get("window_title", ""),
            text_content=res.get("text_content", ""),
            elements=elems,
        )


# -----------------------------------------------------------------------------
# 10. macos.scroll
# -----------------------------------------------------------------------------
class MacOSScrollInput(BaseModel):
    direction: str = Field(
        default="down",
        description="Direction to scroll: 'up', 'down', 'left', or 'right'.",
    )
    amount: int = Field(
        default=5,
        description="Scroll amount in lines (default 5).",
    )
    x: float | None = Field(
        default=None,
        description="Optional horizontal coordinate where scroll should occur.",
    )
    y: float | None = Field(
        default=None,
        description="Optional vertical coordinate where scroll should occur.",
    )


class MacOSScrollOutput(BaseModel):
    success: bool
    direction: str
    amount: int
    message: str


class MacOSScrollTool(BaseTool):
    name = "macos.scroll"
    description = "Synthesize scroll wheel events on screen (up, down, left, right)."
    input_schema = MacOSScrollInput
    output_schema = MacOSScrollOutput
    required_capability = "macos.scroll"
    default_risk_level = "HIGH"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSScrollInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSScrollOutput:
        d = params.direction.lower().strip()
        delta_y = 0
        delta_x = 0
        if d == "down":
            delta_y = -abs(params.amount)
        elif d == "up":
            delta_y = abs(params.amount)
        elif d == "left":
            delta_x = -abs(params.amount)
        elif d == "right":
            delta_x = abs(params.amount)
        else:
            raise ValueError(f"Invalid scroll direction: '{params.direction}'")

        success = engine.post_scroll(delta_y=delta_y, delta_x=delta_x, x=params.x, y=params.y)
        return MacOSScrollOutput(
            success=success,
            direction=d,
            amount=params.amount,
            message=f"Scrolled {d} by {params.amount} units.",
        )


# -----------------------------------------------------------------------------
# 11. macos.click_coords
# -----------------------------------------------------------------------------
class MacOSClickCoordsInput(BaseModel):
    x: float = Field(..., description="Screen X pixel coordinate.")
    y: float = Field(..., description="Screen Y pixel coordinate.")
    button: str = Field(
        default="left", description="Mouse button: 'left' or 'right' (default 'left')."
    )
    click_count: int = Field(
        default=1, description="Number of clicks: 1 for single-click, 2 for double-click."
    )


class MacOSClickCoordsOutput(BaseModel):
    success: bool
    x: float
    y: float
    button: str
    click_count: int
    message: str


class MacOSClickCoordsTool(BaseTool):
    name = "macos.click_coords"
    description = "Click or double-click at explicit screen pixel coordinates (X, Y)."
    input_schema = MacOSClickCoordsInput
    output_schema = MacOSClickCoordsOutput
    required_capability = "macos.click_coords"
    default_risk_level = "HIGH"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSClickCoordsInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSClickCoordsOutput:
        success = engine.post_mouse_click_coords(
            x=params.x,
            y=params.y,
            button=params.button,
            click_count=params.click_count,
        )
        action_name = "Double-clicked" if params.click_count == 2 else "Clicked"
        return MacOSClickCoordsOutput(
            success=success,
            x=params.x,
            y=params.y,
            button=params.button,
            click_count=params.click_count,
            message=f"{action_name} {params.button} button at ({params.x}, {params.y}).",
        )


# -----------------------------------------------------------------------------
# 12. macos.mouse_drag
# -----------------------------------------------------------------------------
class MacOSMouseDragInput(BaseModel):
    start_x: float = Field(..., description="Starting screen X coordinate.")
    start_y: float = Field(..., description="Starting screen Y coordinate.")
    end_x: float = Field(..., description="Ending screen X coordinate.")
    end_y: float = Field(..., description="Ending screen Y coordinate.")
    steps: int = Field(
        default=10, description="Number of intermediate drag steps for smooth motion."
    )


class MacOSMouseDragOutput(BaseModel):
    success: bool
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    message: str


class MacOSMouseDragTool(BaseTool):
    name = "macos.mouse_drag"
    description = "Drag from (start_x, start_y) to (end_x, end_y) synthesizing native mouse drag events."
    input_schema = MacOSMouseDragInput
    output_schema = MacOSMouseDragOutput
    required_capability = "macos.mouse_drag"
    default_risk_level = "HIGH"
    timeout_seconds = 15.0

    async def run(
        self,
        user_id: str,
        params: MacOSMouseDragInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSMouseDragOutput:
        success = engine.post_mouse_drag(
            start_x=params.start_x,
            start_y=params.start_y,
            end_x=params.end_x,
            end_y=params.end_y,
            steps=params.steps,
        )
        return MacOSMouseDragOutput(
            success=success,
            start_x=params.start_x,
            start_y=params.start_y,
            end_x=params.end_x,
            end_y=params.end_y,
            message=f"Dragged mouse from ({params.start_x}, {params.start_y}) to ({params.end_x}, {params.end_y}).",
        )


# -----------------------------------------------------------------------------
# 13. macos.press_key
# -----------------------------------------------------------------------------
class MacOSPressKeyInput(BaseModel):
    key: str = Field(
        ...,
        description="Key to press: e.g. 'page_down', 'page_up', 'space', 'return', 'escape', 'up', 'down', 'left', 'right'.",
    )


class MacOSPressKeyOutput(BaseModel):
    success: bool
    key: str
    message: str


class MacOSPressKeyTool(BaseTool):
    name = "macos.press_key"
    description = (
        "Press a single navigation or functional key on the keyboard (e.g. page down, page up, space, return, escape)."
    )
    input_schema = MacOSPressKeyInput
    output_schema = MacOSPressKeyOutput
    required_capability = "macos.press_key"
    default_risk_level = "HIGH"
    timeout_seconds = 10.0

    async def run(
        self,
        user_id: str,
        params: MacOSPressKeyInput,
        context: dict[str, Any] | None = None,
    ) -> MacOSPressKeyOutput:
        success = engine.post_key_press(params.key)
        return MacOSPressKeyOutput(
            success=success,
            key=params.key,
            message=f"Pressed key '{params.key}'.",
        )
