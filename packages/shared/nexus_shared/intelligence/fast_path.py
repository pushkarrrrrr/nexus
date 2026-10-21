"""Sub-15ms Multi-Lingual Fast-Path Intent Engine for NEXUS.

Enables instant pattern recognition and sub-20ms local dispatch for common
operating system actions, media controls, application workflows, notes, and screen glances
without incurring cloud LLM latency or network roundtrips.
"""

import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.intelligence.fast_path")


@dataclass
class FastPathMatch:
    """Result of an ultra-fast local intent classification pass."""

    matched: bool
    action_type: str = ""
    target: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    latency_ms: float = 0.0
    explanation: str = ""
    reply_template: str = ""


class FastPathEngine:
    """High-throughput, multi-lingual deterministic intent matcher with LRU caching."""

    def __init__(self, cache_size: int = 512) -> None:
        self.cache_size = cache_size
        self._cache: OrderedDict[str, FastPathMatch] = OrderedDict()
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Compile regex tables for English, Hindi, and Hinglish OS actions."""
        # Media controls (Playback state)
        self.media_patterns = [
            (re.compile(r"^(?:next|aage|agla|agle|forward|skip)(?:\s+(?:video|song|track|gaana|karo|kro|badhao))?$", re.IGNORECASE), "media_next", "Media forward/next"),
            (re.compile(r"^(?:prev|previous|pichla|pichhe|piche|back)(?:\s+(?:video|song|track|gaana|karo|kro|badhao))?$", re.IGNORECASE), "media_prev", "Media previous"),
            (re.compile(r"^(?:pause|rok do|ruko|stop|chup|shant)$", re.IGNORECASE), "media_pause", "Media pause"),
            (re.compile(r"^(?:resume|play|chalao|bajao|start karo)$", re.IGNORECASE), "media_play", "Media resume"),
            (re.compile(r"^(?:mute|awaaz band|sound off)$", re.IGNORECASE), "media_mute", "Media mute"),
            (re.compile(r"^(?:unmute|awaaz chalu|sound on)$", re.IGNORECASE), "media_unmute", "Media unmute"),
        ]

        # App Launching: "open spotify", "spotify kholo", "launch chrome", "calculator start karo"
        self.open_app_patterns = [
            re.compile(r"^(?:open|launch|start|chalu karo)\s+([a-zA-Z0-9\s\.\-_]+)$", re.IGNORECASE),
            re.compile(r"^([a-zA-Z0-9\s\.\-_]+?)\s+(?:kholo|open karo|chalu karo|start karo)$", re.IGNORECASE),
        ]

        # App Termination: "close spotify", "spotify band karo", "quit chrome"
        self.close_app_patterns = [
            re.compile(r"^(?:close|quit|exit|kill|band karo)\s+([a-zA-Z0-9\s\.\-_]+)$", re.IGNORECASE),
            re.compile(r"^([a-zA-Z0-9\s\.\-_]+?)\s+(?:band karo|close karo|hatao)$", re.IGNORECASE),
        ]

        # YouTube playback: "youtube par [query] play karo", "play [query] on youtube"
        self.yt_play_patterns = [
            re.compile(r"^(?:youtube\s+(?:par|pe|mein)\s+)?(?:play|chalao|bajao)\s+(.+?)(?:\s+on\s+youtube|\s+youtube\s+(?:par|pe|mein))?$", re.IGNORECASE),
            re.compile(r"^youtube\s+(?:par|pe|mein)\s+(.+?)\s+(?:play|chalao|bajao|search)(?:\s+karo)?$", re.IGNORECASE),
        ]

        # Spotify playback: "spotify par [query] play karo", "play [query] on spotify"
        self.spotify_play_patterns = [
            re.compile(r"^(?:spotify\s+(?:par|pe|mein)\s+)?(?:play|chalao|bajao)\s+(.+?)(?:\s+on\s+spotify|\s+spotify\s+(?:par|pe|mein))?$", re.IGNORECASE),
            re.compile(r"^spotify\s+(?:par|pe|mein)\s+(.+?)\s+(?:play|chalao|bajao|search)(?:\s+karo)?$", re.IGNORECASE),
        ]

        # Screen perception: "what is on my screen", "screen par kya hai", "read screen"
        self.screen_patterns = [
            re.compile(r"^(?:what(?:'s|\s+is)\s+on\s+(?:my\s+)?screen|read\s+screen|screen\s+(?:par|pe)\s+kya\s+hai|screen\s+dekho)$", re.IGNORECASE),
        ]

        # System status / health
        self.system_patterns = [
            re.compile(r"^(?:system\s+(?:status|health|metrics|info)|cpu\s+(?:status|load)|ram\s+(?:status|usage)|battery\s+status)$", re.IGNORECASE),
        ]

        # Quick notes: "note likho [text]", "add note [text]", "save note [text]"
        self.note_patterns = [
            re.compile(r"^(?:note\s+(?:likho|karo|banao)|add\s+note|save\s+note|write\s+note)\s*[:\-]?\s*(.+)$", re.IGNORECASE),
            re.compile(r"^note\s+mein\s+(.+?)\s+(?:likho|add\s+karo|save\s+karo)$", re.IGNORECASE),
        ]

        # Web search: "search web for [query]", "google par search karo [query]"
        self.web_search_patterns = [
            re.compile(r"^(?:google|web|internet)\s+(?:par|pe)?\s*search\s+(?:karo\s+)?(.+)$", re.IGNORECASE),
            re.compile(r"^(?:search\s+(?:web|google|internet)\s+for)\s+(.+)$", re.IGNORECASE),
        ]

    def match(self, text: str) -> FastPathMatch:
        """Evaluate text against deterministic intent index in < 15ms."""
        t_start = time.perf_counter()
        raw = text.strip()
        if not raw:
            return FastPathMatch(matched=False, explanation="Empty query")

        # 1. Check LRU Cache
        clean_key = raw.lower()
        if clean_key in self._cache:
            hit = self._cache[clean_key]
            # Refresh position in LRU
            self._cache.move_to_end(clean_key)
            latency = (time.perf_counter() - t_start) * 1000.0
            return FastPathMatch(
                matched=hit.matched,
                action_type=hit.action_type,
                target=hit.target,
                args=dict(hit.args),
                confidence=hit.confidence,
                latency_ms=round(latency, 2),
                explanation=f"{hit.explanation} (cache_hit)",
                reply_template=hit.reply_template,
            )

        match_result = self._eval_rules(raw)
        latency = (time.perf_counter() - t_start) * 1000.0
        match_result.latency_ms = round(latency, 2)

        # Update cache
        if len(self._cache) >= self.cache_size:
            self._cache.popitem(last=False)
        self._cache[clean_key] = match_result

        return match_result

    def _eval_rules(self, text: str) -> FastPathMatch:
        clean = text.strip()

        # 1. Screen Reading
        for pat in self.screen_patterns:
            if pat.search(clean):
                return FastPathMatch(
                    matched=True,
                    action_type="read_screen",
                    target="active_window",
                    confidence=0.98,
                    explanation="Fast-path screen inspection intent matched",
                    reply_template="Screen ka content inspect kiya ja raha hai...",
                )

        # 2. System Status
        for pat in self.system_patterns:
            if pat.search(clean):
                return FastPathMatch(
                    matched=True,
                    action_type="system_metrics",
                    target="system",
                    confidence=0.95,
                    explanation="Fast-path system telemetry intent matched",
                    reply_template="System health aur resource metrics retrieve kiye gaye hain.",
                )

        # 3. Media Controls
        for pat, action, desc in self.media_patterns:
            if pat.search(clean):
                return FastPathMatch(
                    matched=True,
                    action_type=action,
                    target="media_player",
                    confidence=0.99,
                    explanation=f"Fast-path {desc} intent matched",
                    reply_template=f"{desc} command execute kar diya gaya hai.",
                )

        # 4. YouTube Play
        if "youtube" in clean.lower():
            for pat in self.yt_play_patterns:
                m = pat.search(clean)
                if m:
                    query = m.group(1).strip()
                    # Exclude generic app opening
                    if query and query.lower() not in ("kholo", "open", "chalu karo"):
                        return FastPathMatch(
                            matched=True,
                            action_type="youtube_play",
                            target=query,
                            args={"query": query},
                            confidence=0.95,
                            explanation=f"Fast-path YouTube playback matched for '{query}'",
                            reply_template=f"YouTube par '{query}' play kar raha hoon.",
                        )

        # 5. Spotify Play
        if "spotify" in clean.lower():
            for pat in self.spotify_play_patterns:
                m = pat.search(clean)
                if m:
                    query = m.group(1).strip()
                    if query and query.lower() not in ("kholo", "open", "chalu karo"):
                        return FastPathMatch(
                            matched=True,
                            action_type="spotify_play",
                            target=query,
                            args={"song": query},
                            confidence=0.95,
                            explanation=f"Fast-path Spotify playback matched for '{query}'",
                            reply_template=f"Spotify par '{query}' play kar diya hai.",
                        )

        # 6. Quick Notes
        for pat in self.note_patterns:
            m = pat.search(clean)
            if m:
                content = m.group(1).strip()
                if content:
                    return FastPathMatch(
                        matched=True,
                        action_type="quick_note",
                        target="Notes",
                        args={"content": content},
                        confidence=0.95,
                        explanation="Fast-path Apple Notes memo matched",
                        reply_template=f"Notes app mein memo save kar diya: '{content[:50]}...'",
                    )

        # 7. Web Search
        for pat in self.web_search_patterns:
            m = pat.search(clean)
            if m:
                query = m.group(1).strip()
                if query:
                    return FastPathMatch(
                        matched=True,
                        action_type="web_search",
                        target=query,
                        args={"query": query},
                        confidence=0.92,
                        explanation=f"Fast-path web search query matched for '{query}'",
                        reply_template=f"Web par '{query}' search kiya ja raha hai.",
                    )

        # 8. Close Application
        for pat in self.close_app_patterns:
            m = pat.search(clean)
            if m:
                app_target = m.group(1).strip()
                if app_target and len(app_target.split()) <= 4:
                    return FastPathMatch(
                        matched=True,
                        action_type="close_app",
                        target=app_target,
                        args={"app_name": app_target},
                        confidence=0.94,
                        explanation=f"Fast-path application termination for '{app_target}'",
                        reply_template=f"{app_target} band kar diya hai.",
                    )

        # 9. Open Application
        for pat in self.open_app_patterns:
            m = pat.search(clean)
            if m:
                app_target = m.group(1).strip()
                if app_target and len(app_target.split()) <= 4:
                    return FastPathMatch(
                        matched=True,
                        action_type="open_app",
                        target=app_target,
                        args={"app_name": app_target},
                        confidence=0.94,
                        explanation=f"Fast-path application launch for '{app_target}'",
                        reply_template=f"{app_target} open kar diya hai.",
                    )

        return FastPathMatch(matched=False, explanation="No deterministic fast-path pattern matched")


# Global singleton instance for sub-15ms application reuse
_fast_path_singleton: FastPathEngine | None = None


def get_fast_path_engine() -> FastPathEngine:
    """Retrieve or initialize the global FastPathEngine singleton."""
    global _fast_path_singleton
    if _fast_path_singleton is None:
        _fast_path_singleton = FastPathEngine()
    return _fast_path_singleton
