"""Screen Perception & Multi-Modal Context Reasoner for NEXUS.

Reads the user's active macOS window state, accessibility elements, and visual text
to ground agent comprehension in actual display context.
"""

from typing import Any

from packages.shared.nexus_shared.computer import get_computer_adapter
from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.intelligence.screen_reasoner")


class ScreenPerceptionReasoner:
    """Extracts, analyzes, and answers contextual questions about the user's active screen."""

    def __init__(self) -> None:
        self.adapter = get_computer_adapter()

    async def inspect_active_screen(self, target_app: str | None = None) -> dict[str, Any]:
        """Capture deep textual and structural metadata from the frontmost application."""
        try:
            content = await self.adapter.read_window_content(app_name=target_app)
            windows = await self.adapter.list_windows(on_screen_only=True)
            frontmost = await self.adapter.get_frontmost_app()

            active_windows = [
                w.get("owner_name")
                for w in windows
                if w.get("owner_name") and w.get("layer") == 0 and w.get("owner_name") not in ("Window Server", "Dock")
            ]
            distinct_apps = list(dict.fromkeys(filter(None, active_windows)))

            text_summary = content.get("text_summary", "").strip() if content else ""
            app_name = content.get("app_name") or frontmost or "Unknown App"
            window_title = content.get("window_title", "")

            return {
                "status": "success",
                "app_name": app_name,
                "window_title": window_title,
                "text_summary": text_summary,
                "visible_apps": distinct_apps[:6],
                "char_count": len(text_summary),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("screen_inspection_failed", error=str(exc))
            return {
                "status": "error",
                "error": str(exc),
                "app_name": "Unknown",
                "window_title": "",
                "text_summary": "",
                "visible_apps": [],
                "char_count": 0,
            }

    async def answer_screen_query(self, user_query: str, target_app: str | None = None) -> dict[str, Any]:
        """Answer queries such as 'What is on my screen?' or 'Explain the error showing'."""
        info = await self.inspect_active_screen(target_app)
        app_name = info["app_name"]
        title = info["window_title"]
        summary = info["text_summary"]
        apps = info["visible_apps"]

        clean_q = user_query.lower()

        # 1. Error diagnosis request
        if any(w in clean_q for w in ("error", "exception", "fault", "crash", "traceback")):
            error_keywords = ("error", "exception", "failed", "traceback", "fatal", "warning")
            lines = summary.split("\n")
            matching_lines = [
                line.strip() for line in lines
                if any(kw in line.lower() for kw in error_keywords) and len(line.strip()) > 5
            ]
            if matching_lines:
                snippet = "; ".join(matching_lines[:3])
                reply = f"Aapke {app_name} window par yeh error dikh raha hai: '{snippet[:160]}'."
                return {
                    "reply": reply,
                    "diagnosis": matching_lines,
                    "screen_info": info,
                    "category": "error_diagnosis",
                }
            else:
                reply = f"Aapke active window ({app_name}) par koi explicit runtime crash ya error message detect nahi hua."
                return {
                    "reply": reply,
                    "diagnosis": [],
                    "screen_info": info,
                    "category": "error_diagnosis",
                }

        # 2. General screen perception
        if not summary and title:
            reply = f"Screen par {app_name} open hai jiska title '{title}' hai."
        elif not summary and not title:
            app_list_str = ", ".join(apps) if apps else app_name
            reply = f"Screen par active application '{app_name}' hai aur open apps hain: {app_list_str}."
        else:
            compact_summary = summary.replace("\n", " ")[:180]
            reply = f"Screen par {app_name} ({title or 'Active'}) open hai: {compact_summary}..."

        return {
            "reply": reply,
            "diagnosis": [],
            "screen_info": info,
            "category": "general_perception",
        }


# Global singleton reasoner
_screen_reasoner_singleton: ScreenPerceptionReasoner | None = None


def get_screen_perception_reasoner() -> ScreenPerceptionReasoner:
    """Retrieve or initialize the global ScreenPerceptionReasoner singleton."""
    global _screen_reasoner_singleton
    if _screen_reasoner_singleton is None:
        _screen_reasoner_singleton = ScreenPerceptionReasoner()
    return _screen_reasoner_singleton
