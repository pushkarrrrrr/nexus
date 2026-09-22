"""Persistent Browser Session Manager using Playwright with Idle Reaping and POSIX Isolation."""

import asyncio
import os
import time
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.integrations.browser.session")

DEFAULT_IDLE_TIMEOUT_SECONDS = 600.0  # 10 minutes


class BrowserSessionRecord:
    """Tracks an active Playwright persistent context and its idle timer."""

    def __init__(self, context: BrowserContext, play: Playwright, headless: bool) -> None:
        self.context: BrowserContext = context
        self.playwright: Playwright = play
        self.headless: bool = headless
        self.last_active: float = time.time()
        self.current_page: Page | None = None

    def touch(self) -> None:
        self.last_active = time.time()

    def is_idle(self, timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> bool:
        return (time.time() - self.last_active) >= timeout_seconds


class BrowserSessionManager:
    """Manages isolated, persistent Chromium sessions per NEXUS user.

    Profiles are persisted in ~/.nexus/browser_profiles/{user_id} with 0700 permissions.
    An asynchronous reaper periodically closes contexts exceeding idle inactivity
    to cleanly release Chromium SingletonLock while keeping persistent state intact.
    """

    def __init__(self, base_profile_dir: str | None = None) -> None:
        if base_profile_dir is None:
            self.base_profile_dir = Path.home() / ".nexus" / "browser_profiles"
        else:
            self.base_profile_dir = Path(base_profile_dir)
        self._sessions: dict[str, BrowserSessionRecord] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task[None] | None = None

    def get_user_profile_dir(self, user_id: str) -> Path:
        """Create and enforce 0700 POSIX permissions on user browser profile directory."""
        profile_dir = self.base_profile_dir / user_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(profile_dir, 0o700)
        except OSError as e:
            logger.warning("failed_to_set_profile_permissions", path=str(profile_dir), error=str(e))
        return profile_dir

    def _ensure_reaper_started(self) -> None:
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(self._reaper_loop())

    async def _reaper_loop(self) -> None:
        """Periodic background loop that reaps idle contexts to release SingletonLock."""
        try:
            while True:
                await asyncio.sleep(60)
                await self.reap_idle_contexts()
        except asyncio.CancelledError:
            pass

    async def reap_idle_contexts(self, timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS) -> int:
        """Close any browser contexts that have been inactive longer than timeout_seconds."""
        async with self._lock:
            reaped_count = 0
            idle_users = [
                user_id
                for user_id, session in self._sessions.items()
                if session.is_idle(timeout_seconds)
            ]
            for user_id in idle_users:
                session = self._sessions.pop(user_id)
                try:
                    await session.context.close()
                    await session.playwright.stop()
                    reaped_count += 1
                    logger.info("reaped_idle_browser_context", user_id=user_id)
                except Exception as e:  # noqa: BLE001
                    logger.error("error_closing_idle_context", user_id=user_id, error=str(e))
            return reaped_count

    async def get_or_create_context(
        self,
        user_id: str,
        headless: bool = True,
        force_new: bool = False,
    ) -> BrowserSessionRecord:
        """Retrieve existing active session or launch persistent Chromium context."""
        async with self._lock:
            self._ensure_reaper_started()

            if not force_new and user_id in self._sessions:
                existing = self._sessions[user_id]
                # If existing mode matches headless request, reuse
                if existing.headless == headless:
                    existing.touch()
                    return existing
                # Otherwise close old mode before launching new
                try:
                    await existing.context.close()
                    await existing.playwright.stop()
                except (OSError, RuntimeError) as e:
                    logger.debug("error_closing_previous_session", error=str(e))
                self._sessions.pop(user_id, None)

            profile_dir = self.get_user_profile_dir(user_id)
            play = await async_playwright().start()

            context = await play.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                viewport={"width": 1280, "height": 800},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                ],
            )

            record = BrowserSessionRecord(context=context, play=play, headless=headless)
            self._sessions[user_id] = record
            logger.info(
                "launched_persistent_browser_context",
                user_id=user_id,
                headless=headless,
                profile=str(profile_dir),
            )
            return record

    async def get_active_page(self, user_id: str, headless: bool = True) -> Page:
        """Get or open the main active page in the user's persistent context."""
        session = await self.get_or_create_context(user_id, headless=headless)
        session.touch()
        if session.current_page and not session.current_page.is_closed():
            return session.current_page

        pages = session.context.pages
        if pages:
            session.current_page = pages[0]
        else:
            session.current_page = await session.context.new_page()
        return session.current_page

    async def close_session(self, user_id: str) -> bool:
        """Close user's persistent context and stop Playwright instance."""
        async with self._lock:
            session = self._sessions.pop(user_id, None)
            if session:
                try:
                    await session.context.close()
                    await session.playwright.stop()
                    logger.info("closed_browser_session", user_id=user_id)
                    return True
                except Exception as e:  # noqa: BLE001
                    logger.error("error_closing_session", user_id=user_id, error=str(e))
                    return False
            return False

    async def close_all(self) -> None:
        """Close all active sessions and cancel reaper task."""
        if self._reaper_task:
            self._reaper_task.cancel()
            self._reaper_task = None
        async with self._lock:
            for user_id, session in list(self._sessions.items()):
                try:
                    await session.context.close()
                    await session.playwright.stop()
                except (OSError, RuntimeError) as e:
                    logger.debug("error_closing_session_cleanup", error=str(e))
            self._sessions.clear()


_global_browser_manager: BrowserSessionManager | None = None


def get_browser_session_manager() -> BrowserSessionManager:
    global _global_browser_manager
    if _global_browser_manager is None:
        _global_browser_manager = BrowserSessionManager()
    return _global_browser_manager
