"""macOS Native Application Control Execution Engine.

Provides dual-engine interaction:
1. Primary: JXA (JavaScript for Automation) / AppleScript via osascript to inspect
   and manipulate AXUIElement trees.
2. Fallback: CoreGraphics / Quartz synthetic event generation (mouse & keyboard) via ctypes.
3. Window Frame Capture: Uses screencapture with window ID resolution from CoreGraphics.
"""

import asyncio
import base64
import ctypes
import json
import os
import platform
import struct
import tempfile
from typing import Any

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.integrations.macos.engine")

# ---------------------------------------------------------------------------
# CoreGraphics / Quartz / CoreFoundation CTypes Bindings
# ---------------------------------------------------------------------------
class CGPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


# CGEvent constants
kCGSessionEventTap = 1
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 3
kCGEventRightMouseUp = 4
kCGMouseButtonLeft = 0
kCGMouseButtonRight = 1

kCGEventFlagMaskCommand = 0x00100000
kCGEventFlagMaskShift = 0x00020000
kCGEventFlagMaskAlternate = 0x00080000
kCGEventFlagMaskControl = 0x00040000

# Virtual Key Codes (macOS US Layout standard)
KEY_CODES: dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47,
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "backspace": 51, "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
}

_cg_lib = None
_cf_lib = None


def _load_macos_frameworks() -> tuple[Any, Any]:
    global _cg_lib, _cf_lib
    if platform.system() != "Darwin":
        return None, None
    if _cg_lib is None:
        try:
            _cg_lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        except OSError:
            _cg_lib = None
    if _cf_lib is None:
        try:
            _cf_lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        except OSError:
            _cf_lib = None
    return _cg_lib, _cf_lib


# ---------------------------------------------------------------------------
# JXA / osascript Runner
# ---------------------------------------------------------------------------
async def run_jxa(script: str, timeout: float = 10.0) -> Any:
    """Execute a JavaScript for Automation (JXA) script via osascript with timeout guards."""
    if platform.system() != "Darwin":
        raise RuntimeError("JXA automation is only supported on macOS.")

    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript",
            "-l",
            "JavaScript",
            "-e",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        raise TimeoutError(f"JXA script execution timed out after {timeout}s.") from exc

    err_text = stderr.decode("utf-8", errors="replace").strip()
    out_text = stdout.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        raise RuntimeError(f"JXA execution failed (code {proc.returncode}): {err_text or out_text}")

    if not out_text:
        return None

    try:
        return json.loads(out_text)
    except json.JSONDecodeError:
        return out_text


# ---------------------------------------------------------------------------
# High-Level Native App Operations (Primary: JXA)
# ---------------------------------------------------------------------------
async def list_applications() -> list[dict[str, Any]]:
    """List running desktop applications with name, bundle ID, PID, and frontmost status."""
    script = """
(() => {
  try {
    const se = Application("System Events");
    const procs = se.applicationProcesses.whose({backgroundOnly: false})();
    const results = [];
    for (let i = 0; i < procs.length; i++) {
      try {
        const p = procs[i];
        results.push({
          app_name: p.name(),
          bundle_id: p.bundleIdentifier() || "",
          pid: p.unixId() || 0,
          is_frontmost: Boolean(p.frontmost())
        });
      } catch (inner) {}
    }
    return JSON.stringify(results);
  } catch (err) {
    return JSON.stringify({error: err.toString()});
  }
})()
"""
    res = await run_jxa(script)
    if isinstance(res, dict) and "error" in res:
        raise RuntimeError(res["error"])
    return res if isinstance(res, list) else []


async def focus_application(app_name: str) -> bool:
    """Activate and bring the target application to the foreground."""
    clean_name = json.dumps(app_name)
    script = f"""
(() => {{
  try {{
    const targetName = {clean_name};
    try {{
      const app = Application(targetName);
      app.activate();
      return JSON.stringify({{success: true}});
    }} catch(e) {{
      const se = Application("System Events");
      const proc = se.applicationProcesses.byName(targetName);
      if (proc && proc.exists()) {{
        proc.frontmost = true;
        return JSON.stringify({{success: true}});
      }}
      return JSON.stringify({{success: false, error: "Application not found: " + targetName}});
    }}
  }} catch(err) {{
    return JSON.stringify({{success: false, error: err.toString()}});
  }}
}})()
"""
    res = await run_jxa(script)
    if isinstance(res, dict):
        if not res.get("success", False):
            raise RuntimeError(res.get("error", f"Failed to focus application '{app_name}'"))
        return True
    return False


async def inspect_element_tree(app_name: str, max_depth: int = 3) -> dict[str, Any]:
    """Inspect structured accessibility tree of target app, pruning non-interactive layout nodes."""
    clean_name = json.dumps(app_name)
    script = f"""
(() => {{
  try {{
    const targetName = {clean_name};
    const se = Application("System Events");
    const proc = se.applicationProcesses.byName(targetName);
    if (!proc || !proc.exists()) {{
      return JSON.stringify({{error: "Application process not found: " + targetName}});
    }}

    function inspectNode(node, depth) {{
      if (depth > {max_depth}) return null;
      let role = "";
      let title = "";
      let desc = "";
      let val = "";
      let pos = [0, 0];
      let sz = [0, 0];
      let identifier = "";

      try {{ role = node.role() || ""; }} catch(e) {{}}
      try {{ title = node.title() || ""; }} catch(e) {{}}
      try {{ desc = node.description() || ""; }} catch(e) {{}}
      try {{ val = String(node.value() || ""); }} catch(e) {{}}
      try {{ pos = node.position() || [0, 0]; }} catch(e) {{}}
      try {{ sz = node.size() || [0, 0]; }} catch(e) {{}}
      try {{ identifier = node.subrole() || ""; }} catch(e) {{}}

      // Check if interactive or informative
      const isInteractive = role.includes("Button") || role.includes("TextField") ||
                            role.includes("Menu") || role.includes("Window") ||
                            role.includes("CheckBox") || role.includes("PopUp") ||
                            role.includes("StaticText") || Boolean(title) || Boolean(val);

      let children = [];
      try {{
        const rawChildren = node.uiElements();
        for (let i = 0; i < rawChildren.length; i++) {{
          const childNode = inspectNode(rawChildren[i], depth + 1);
          if (childNode) children.push(childNode);
        }}
      }} catch(e) {{}}

      // Prune empty containers
      if (!isInteractive && children.length === 0) return null;

      return {{
        role: role || "AXElement",
        title: title,
        description: desc,
        value: val,
        position: pos,
        size: sz,
        identifier: identifier,
        children: children
      }};
    }}

    const windows = proc.windows();
    const tree = [];
    for (let w = 0; w < windows.length; w++) {{
      const winNode = inspectNode(windows[w], 1);
      if (winNode) tree.push(winNode);
    }}

    return JSON.stringify({{
      app_name: targetName,
      pid: proc.unixId() || 0,
      window_count: windows.length,
      tree: tree
    }});
  }} catch(err) {{
    return JSON.stringify({{error: err.toString()}});
  }}
}})()
"""
    res = await run_jxa(script, timeout=15.0)
    if isinstance(res, dict) and "error" in res:
        raise RuntimeError(res["error"])
    return res if isinstance(res, dict) else {"tree": []}


async def ax_click_element(app_name: str, role: str, title: str) -> bool:
    """Click an accessibility element matching the given role and title via AXPress."""
    clean_app = json.dumps(app_name)
    clean_role = json.dumps(role)
    clean_title = json.dumps(title)

    script = f"""
(() => {{
  try {{
    const targetName = {clean_app};
    const targetRole = {clean_role};
    const targetTitle = {clean_title};
    const se = Application("System Events");
    const proc = se.applicationProcesses.byName(targetName);
    if (!proc || !proc.exists()) {{
      return JSON.stringify({{success: false, error: "Application process not found: " + targetName}});
    }}

    function findAndClick(node, depth) {{
      if (depth > 5) return false;
      let r = "";
      let t = "";
      let d = "";
      try {{ r = node.role() || ""; }} catch(e) {{}}
      try {{ t = node.title() || ""; }} catch(e) {{}}
      try {{ d = node.description() || ""; }} catch(e) {{}}

      if ((!targetRole || r.toLowerCase().includes(targetRole.toLowerCase())) &&
          (t.toLowerCase().includes(targetTitle.toLowerCase()) || d.toLowerCase().includes(targetTitle.toLowerCase()))) {{
        try {{
          node.click();
          return true;
        }} catch(clickErr) {{
          try {{
            node.actions.byName("AXPress").perform();
            return true;
          }} catch(axErr) {{}}
        }}
      }}

      try {{
        const children = node.uiElements();
        for (let i = 0; i < children.length; i++) {{
          if (findAndClick(children[i], depth + 1)) return true;
        }}
      }} catch(e) {{}}
      return false;
    }}

    const windows = proc.windows();
    for (let w = 0; w < windows.length; w++) {{
      if (findAndClick(windows[w], 1)) {{
        return JSON.stringify({{success: true}});
      }}
    }}
    return JSON.stringify({{success: false, error: `Element with role '${{targetRole}}' and title '${{targetTitle}}' not found`}});
  }} catch(err) {{
    return JSON.stringify({{success: false, error: err.toString()}});
  }}
}})()
"""
    res = await run_jxa(script)
    if isinstance(res, dict):
        if not res.get("success", False):
            raise RuntimeError(res.get("error", f"Click failed on {role} '{title}' in {app_name}"))
        return True
    return False


async def ax_set_value(app_name: str, text: str, submit_key: str | None = None) -> bool:
    """Set text or type into the currently focused or text input element."""
    clean_app = json.dumps(app_name)
    clean_text = json.dumps(text)
    clean_submit = json.dumps(submit_key) if submit_key else "null"

    script = f"""
(() => {{
  try {{
    const targetName = {clean_app};
    const targetText = {clean_text};
    const submitKey = {clean_submit};
    const se = Application("System Events");
    const proc = se.applicationProcesses.byName(targetName);
    if (!proc || !proc.exists()) {{
      return JSON.stringify({{success: false, error: "Application process not found: " + targetName}});
    }}
    proc.frontmost = true;

    // Send keystroke text directly via System Events
    se.keystroke(targetText);

    if (submitKey) {{
      const sk = submitKey.toLowerCase();
      if (sk === "enter" || sk === "return") {{
        se.keyCode(36);
      }} else if (sk === "tab") {{
        se.keyCode(48);
      }}
    }}
    return JSON.stringify({{success: true}});
  }} catch(err) {{
    return JSON.stringify({{success: false, error: err.toString()}});
  }}
}})()
"""
    res = await run_jxa(script)
    if isinstance(res, dict):
        if not res.get("success", False):
            raise RuntimeError(res.get("error", f"Typing failed in {app_name}"))
        return True
    return False


# ---------------------------------------------------------------------------
# Fallback Engine (CoreGraphics / Quartz via ctypes)
# ---------------------------------------------------------------------------
def post_mouse_click(x: float, y: float, button: str = "left") -> bool:
    """Synthesize mouse down and up events at (x, y) using CoreGraphics."""
    cg, _ = _load_macos_frameworks()
    if not cg:
        raise RuntimeError("CoreGraphics framework is not available.")

    point = CGPoint(x=x, y=y)
    is_left = button.lower() == "left"
    down_type = kCGEventLeftMouseDown if is_left else kCGEventRightMouseDown
    up_type = kCGEventLeftMouseUp if is_left else kCGEventRightMouseUp
    mouse_btn = kCGMouseButtonLeft if is_left else kCGMouseButtonRight

    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, CGPoint, ctypes.c_uint32]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    cf, _ = _load_macos_frameworks()

    event_down = cg.CGEventCreateMouseEvent(None, down_type, point, mouse_btn)
    if not event_down:
        return False
    cg.CGEventPost(kCGSessionEventTap, event_down)

    event_up = cg.CGEventCreateMouseEvent(None, up_type, point, mouse_btn)
    if not event_up:
        if cf and hasattr(cf, "CFRelease"):
            cf.CFRelease(event_down)
        return False
    cg.CGEventPost(kCGSessionEventTap, event_up)

    if cf and hasattr(cf, "CFRelease"):
        cf.CFRelease(event_down)
        cf.CFRelease(event_up)
    return True


def post_keyboard_string(text: str, submit_key: str | None = None) -> bool:
    """Synthesize keyboard unicode input events using CoreGraphics."""
    cg, cf = _load_macos_frameworks()
    if not cg:
        raise RuntimeError("CoreGraphics framework is not available.")

    cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    cg.CGEventKeyboardSetUnicodeString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_char_p,
    ]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    utf16_bytes = text.encode("utf-16-le")
    num_chars = len(text)

    # Key down
    evt_down = cg.CGEventCreateKeyboardEvent(None, 0, True)
    cg.CGEventKeyboardSetUnicodeString(evt_down, num_chars, utf16_bytes)
    cg.CGEventPost(kCGSessionEventTap, evt_down)

    # Key up
    evt_up = cg.CGEventCreateKeyboardEvent(None, 0, False)
    cg.CGEventPost(kCGSessionEventTap, evt_up)

    if cf and hasattr(cf, "CFRelease"):
        cf.CFRelease(evt_down)
        cf.CFRelease(evt_up)

    if submit_key:
        sk = submit_key.lower()
        key_code = KEY_CODES.get(sk)
        if key_code is not None:
            ret_down = cg.CGEventCreateKeyboardEvent(None, key_code, True)
            cg.CGEventPost(kCGSessionEventTap, ret_down)
            ret_up = cg.CGEventCreateKeyboardEvent(None, key_code, False)
            cg.CGEventPost(kCGSessionEventTap, ret_up)
            if cf and hasattr(cf, "CFRelease"):
                cf.CFRelease(ret_down)
                cf.CFRelease(ret_up)

    return True


def post_shortcut(key: str, modifiers: list[str]) -> bool:
    """Synthesize shortcut combination with modifier masks."""
    cg, cf = _load_macos_frameworks()
    if not cg:
        raise RuntimeError("CoreGraphics framework is not available.")

    key_lower = key.lower()
    key_code = KEY_CODES.get(key_lower)
    if key_code is None:
        raise ValueError(f"Unknown key for shortcut: '{key}'")

    flags = 0
    for mod in modifiers:
        m = mod.lower()
        if m in ("cmd", "command"):
            flags |= kCGEventFlagMaskCommand
        elif m == "shift":
            flags |= kCGEventFlagMaskShift
        elif m in ("alt", "opt", "option"):
            flags |= kCGEventFlagMaskAlternate
        elif m in ("ctrl", "control"):
            flags |= kCGEventFlagMaskControl

    cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]

    down_evt = cg.CGEventCreateKeyboardEvent(None, key_code, True)
    cg.CGEventSetFlags(down_evt, flags)
    cg.CGEventPost(kCGSessionEventTap, down_evt)

    up_evt = cg.CGEventCreateKeyboardEvent(None, key_code, False)
    cg.CGEventSetFlags(up_evt, flags)
    cg.CGEventPost(kCGSessionEventTap, up_evt)

    if cf and hasattr(cf, "CFRelease"):
        cf.CFRelease(down_evt)
        cf.CFRelease(up_evt)

    return True


# ---------------------------------------------------------------------------
# Window Frame Resolution & Capture
# ---------------------------------------------------------------------------
def resolve_window_id(app_name: str) -> int | None:
    """Resolve the frontmost window ID for the given application name using CoreGraphics."""
    cg, cf = _load_macos_frameworks()
    if not cg or not cf:
        return None

    try:
        cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        arr = cg.CGWindowListCopyWindowInfo(1, 0)  # kCGWindowListOptionOnScreenOnly = 1
        if not arr:
            return None

        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]

        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cf.CFNumberGetValue.restype = ctypes.c_bool
        cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]

        kCFStringEncodingUTF8 = 0x08000100
        kOwnerKey = cf.CFStringCreateWithCString(None, b"kCGWindowOwnerName", kCFStringEncodingUTF8)
        kNumKey = cf.CFStringCreateWithCString(None, b"kCGWindowNumber", kCFStringEncodingUTF8)

        count = cf.CFArrayGetCount(arr)
        target_win_id: int | None = None
        target_lower = app_name.lower()

        for i in range(count):
            dict_ref = cf.CFArrayGetValueAtIndex(arr, i)
            owner_ref = cf.CFDictionaryGetValue(dict_ref, kOwnerKey)
            num_ref = cf.CFDictionaryGetValue(dict_ref, kNumKey)
            if owner_ref and num_ref:
                buf = ctypes.create_string_buffer(256)
                if cf.CFStringGetCString(owner_ref, buf, 256, kCFStringEncodingUTF8):
                    owner_name = buf.value.decode("utf-8", errors="ignore")
                    if target_lower in owner_name.lower():
                        win_num = ctypes.c_uint32(0)
                        cf.CFNumberGetValue(num_ref, 3, ctypes.byref(win_num))  # kCFNumberSInt32Type = 3
                        target_win_id = win_num.value
                        break

        cf.CFRelease(arr)
        cf.CFRelease(kOwnerKey)
        cf.CFRelease(kNumKey)
        return target_win_id
    except Exception as e:  # noqa: BLE001
        logger.debug("resolve_window_id_failed", app=app_name, error=str(e))
        return None


async def capture_window_image(app_name: str, window_id: int | None = None) -> dict[str, Any]:
    """Capture a screenshot of target window returning base64 PNG data, dimensions, and metadata."""
    if platform.system() != "Darwin":
        raise RuntimeError("Window capture is only supported on macOS.")

    # Resolve window ID if not explicitly provided
    resolved_id = window_id if window_id is not None else resolve_window_id(app_name)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        cmd: list[str] = ["screencapture", "-o", "-C"]
        if resolved_id is not None:
            cmd.append(f"-l{resolved_id}")
        cmd.append(tmp_path)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"screencapture failed: {err_msg}")

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError(f"screencapture produced empty file for application '{app_name}'")

        def _read_bytes() -> bytes:
            with open(tmp_path, "rb") as f:
                return f.read()

        raw_bytes = await asyncio.to_thread(_read_bytes)

        b64_data = base64.b64encode(raw_bytes).decode("ascii")

        # Parse PNG dimensions from IHDR chunk (bytes 16..24)
        width, height = 0, 0
        if len(raw_bytes) >= 24 and raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            width, height = struct.unpack(">II", raw_bytes[16:24])

        return {
            "app_name": app_name,
            "window_id": resolved_id,
            "format": "png",
            "width": width,
            "height": height,
            "size_bytes": len(raw_bytes),
            "data_base64": b64_data,
        }
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
