"""macOS TCC (Transparency, Consent, and Control) Permission Verification.

Provides checking for Accessibility (AXIsProcessTrusted) and Screen Recording
(CGPreflightScreenCaptureAccess) using pure Python ctypes without external binary dependencies.
"""

import ctypes
import ctypes.util
import platform
import sys
from typing import Any

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.integrations.macos.permissions")

ACCESSIBILITY_PREF_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
SCREEN_CAPTURE_PREF_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"


def _check_accessibility_trusted() -> bool:
    """Check if the current process is trusted for macOS Accessibility APIs."""
    if platform.system() != "Darwin":
        return False
    try:
        # Load ApplicationServices framework
        app_services_path = "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        try:
            app_services = ctypes.cdll.LoadLibrary(app_services_path)
        except OSError:
            lib_path = ctypes.util.find_library("ApplicationServices")
            if not lib_path:
                return False
            app_services = ctypes.cdll.LoadLibrary(lib_path)

        if hasattr(app_services, "AXIsProcessTrusted"):
            app_services.AXIsProcessTrusted.argtypes = []
            app_services.AXIsProcessTrusted.restype = ctypes.c_bool
            return bool(app_services.AXIsProcessTrusted())
        return False
    except Exception as e:  # noqa: BLE001
        logger.debug("accessibility_trust_check_failed", error=str(e))
        return False


def _check_screen_capture_allowed() -> bool:
    """Check if the current process has Screen Recording permission."""
    if platform.system() != "Darwin":
        return False
    try:
        # Load CoreGraphics framework
        cg_path = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        try:
            cg = ctypes.cdll.LoadLibrary(cg_path)
        except OSError:
            lib_path = ctypes.util.find_library("CoreGraphics")
            if not lib_path:
                return False
            cg = ctypes.cdll.LoadLibrary(lib_path)

        if hasattr(cg, "CGPreflightScreenCaptureAccess"):
            cg.CGPreflightScreenCaptureAccess.argtypes = []
            cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
            return bool(cg.CGPreflightScreenCaptureAccess())
        return False
    except Exception as e:  # noqa: BLE001
        logger.debug("screen_capture_check_failed", error=str(e))
        return False


def check_macos_permissions() -> dict[str, Any]:
    """Inspect and return current macOS TCC permission state with diagnostics.

    Returns:
        dict containing accessibility trust, screen recording permission,
        diagnostic messages, python executable path, and system preference deep-links.
    """
    is_mac = platform.system() == "Darwin"
    accessibility_trusted = _check_accessibility_trusted() if is_mac else False
    screen_capture_allowed = _check_screen_capture_allowed() if is_mac else False
    all_granted = bool(accessibility_trusted and screen_capture_allowed)

    diagnostics: dict[str, str] = {
        "accessibility": (
            "Granted"
            if accessibility_trusted
            else "Missing: Enable in System Settings > Privacy & Security > Accessibility"
        ),
        "screen_capture": (
            "Granted"
            if screen_capture_allowed
            else "Missing: Enable in System Settings > Privacy & Security > Screen Recording"
        ),
    }

    if not is_mac:
        diagnostics["platform"] = f"Unsupported platform: {platform.system()}. macOS required."

    return {
        "is_macos": is_mac,
        "platform": platform.system(),
        "executable_path": sys.executable,
        "accessibility_trusted": accessibility_trusted,
        "screen_capture_allowed": screen_capture_allowed,
        "all_permissions_granted": all_granted,
        "settings_urls": {
            "accessibility": ACCESSIBILITY_PREF_URL,
            "screen_capture": SCREEN_CAPTURE_PREF_URL,
        },
        "diagnostics": diagnostics,
    }
