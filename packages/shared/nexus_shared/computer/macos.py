"""Concrete macOS Computer Control Adapter for NEXUS."""

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from packages.shared.nexus_shared.computer.base import (
    MAX_COMMAND_OUTPUT_BYTES,
    ComputerControlAdapter,
    is_protected_directory,
)
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.policy.utils import normalize_resource_target

logger = get_logger("nexus.computer.macos")


class MacOSAdapter(ComputerControlAdapter):
    """Concrete macOS automation adapter using native tools and Python standard library."""

    async def open_application(self, app_name: str) -> dict[str, Any]:
        """Launch an approved application on macOS via /usr/bin/open -a."""
        app_clean = app_name.strip()
        if not app_clean or any(c in app_clean for c in ";|&$`\n"):
            raise ValueError(f"Invalid application name: '{app_name}'")

        if app_clean.lower() in ("whatsapp", "net.whatsapp.whatsapp"):
            script = '''
            try
                tell application id "net.whatsapp.WhatsApp" to activate
            on error
                tell application "WhatsApp" to activate
            end try
            '''
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                return {
                    "status": "success",
                    "application": "WhatsApp",
                    "message": "Successfully launched WhatsApp",
                }

        cmd = ["/usr/bin/open", "-a", app_clean]
        logger.info("macos_open_app", app=app_clean)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Failed to open application '{app_clean}': {err_msg}")

        return {
            "status": "success",
            "application": app_clean,
            "message": f"Successfully launched {app_clean}",
        }

    async def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the user's default browser on macOS via /usr/bin/open."""
        url_clean = url.strip()
        parsed = urlparse(url_clean)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Only http and https URLs are allowed: '{url}'")

        cmd = ["/usr/bin/open", url_clean]
        logger.info("macos_open_url", url=url_clean)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Failed to open URL '{url_clean}': {err_msg}")

        return {
            "status": "success",
            "url": url_clean,
            "message": f"Opened {url_clean} in default browser",
        }

    async def read_file(self, path: str, max_bytes: int | None = None) -> str:
        """Safely read text content from a file."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: '{resolved}'")
        if not resolved.is_file():
            raise IsADirectoryError(f"Target is a directory, not a file: '{resolved}'")

        raw_bytes = resolved.read_bytes()
        if max_bytes is not None and len(raw_bytes) > max_bytes:
            raw_bytes = raw_bytes[:max_bytes]

        return raw_bytes.decode("utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Safely write or overwrite text content to a file."""
        resolved = Path(normalize_resource_target(path)).resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {
            "status": "success",
            "path": resolved.as_posix(),
            "bytes_written": len(content.encode("utf-8")),
        }

    async def move_file(self, source_path: str, dest_path: str) -> dict[str, Any]:
        """Safely move or rename a file."""
        src = Path(normalize_resource_target(source_path)).resolve()
        dst = Path(normalize_resource_target(dest_path)).resolve()

        if not src.exists():
            raise FileNotFoundError(f"Source file not found: '{src}'")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src.as_posix(), dst.as_posix())

        return {
            "status": "success",
            "source": src.as_posix(),
            "destination": dst.as_posix(),
        }

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Safely remove a file from disk."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: '{resolved}'")

        if resolved.is_dir():
            shutil.rmtree(resolved.as_posix())
        else:
            resolved.unlink()

        return {
            "status": "success",
            "deleted_path": resolved.as_posix(),
        }

    async def list_dir(self, path: str) -> list[dict[str, Any]]:
        """Safely list directory contents with file metadata."""
        resolved = Path(normalize_resource_target(path)).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Directory not found: '{resolved}'")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Target is not a directory: '{resolved}'")

        items: list[dict[str, Any]] = []
        for entry in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
            try:
                stat = entry.stat()
                items.append(
                    {
                        "name": entry.name,
                        "path": entry.as_posix(),
                        "is_dir": entry.is_dir(),
                        "size_bytes": stat.st_size if entry.is_file() else 0,
                    }
                )
            except OSError:
                continue

        return items

    async def run_command(
        self,
        command: list[str],
        timeout_seconds: float = 30.0,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Safely execute a controlled subprocess with strict timeouts and buffer caps."""
        if not command:
            raise ValueError("Command cannot be empty.")

        # Safeguard 1: Workspace / CWD Path Validation
        effective_cwd: str | None = None
        if cwd:
            resolved_cwd = Path(normalize_resource_target(cwd)).resolve()
            if not resolved_cwd.exists() or not resolved_cwd.is_dir():
                raise NotADirectoryError(f"Working directory does not exist: '{resolved_cwd}'")
            if is_protected_directory(resolved_cwd.as_posix()):
                raise ValueError(
                    f"Execution denied in protected system directory: '{resolved_cwd.as_posix()}'"
                )
            effective_cwd = resolved_cwd.as_posix()

        # Build clean environment
        clean_env = os.environ.copy()
        if env:
            clean_env.update(env)

        logger.info("macos_run_command_started", binary=command[0], cwd=effective_cwd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=effective_cwd,
                env=clean_env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_seconds,
            )
            exit_code = proc.returncode or 0

        except TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Command '{command[0]}' timed out after {timeout_seconds} seconds.")

        # Safeguard 2: Stdout/Stderr Buffer Caps (100 KB)
        stdout_truncated = False
        if len(stdout_bytes) > MAX_COMMAND_OUTPUT_BYTES:
            stdout_bytes = stdout_bytes[:MAX_COMMAND_OUTPUT_BYTES]
            stdout_truncated = True

        stderr_truncated = False
        if len(stderr_bytes) > MAX_COMMAND_OUTPUT_BYTES:
            stderr_bytes = stderr_bytes[:MAX_COMMAND_OUTPUT_BYTES]
            stderr_truncated = True

        stdout_str = stdout_bytes.decode("utf-8", errors="replace")
        if stdout_truncated:
            stdout_str += f"\n[Output truncated at {MAX_COMMAND_OUTPUT_BYTES // 1024} KB]"

        stderr_str = stderr_bytes.decode("utf-8", errors="replace")
        if stderr_truncated:
            stderr_str += f"\n[Output truncated at {MAX_COMMAND_OUTPUT_BYTES // 1024} KB]"

        return {
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "cwd": effective_cwd,
            "truncated": stdout_truncated or stderr_truncated,
        }

    async def close_application(self, app_name: str) -> dict[str, Any]:
        """Quit or close an application on macOS via AppleScript and pkill."""
        app_clean = app_name.strip()
        if not app_clean or any(c in app_clean for c in ";|&$`\n\r><"):
            raise ValueError(f"Invalid application name: '{app_name}'")

        # Resolve generic targets ("app", "current", "this", "window") to active frontmost application
        if app_clean.lower() in ("app", "current", "this", "it", "window", "active", "is app", "yeh", "application"):
            frontmost = await self.get_frontmost_app()
            if frontmost and frontmost not in ("NEXUS Ambient", "Nexus Ambient", "nexus-ambient", "Window Server", "Dock"):
                app_clean = frontmost
            else:
                # Find active app behind ambient window
                try:
                    windows = await self.list_windows(on_screen_only=True)
                    for w in windows:
                        w_owner = w.get("owner_name", "")
                        if w_owner and w_owner not in ("NEXUS Ambient", "Nexus Ambient", "nexus-ambient", "Window Server", "Dock", "Finder"):
                            app_clean = w_owner
                            break
                except Exception as exc:  # noqa: BLE001
                    logger.debug(f"Failed to inspect window owners for close target: {exc}")

        logger.info("macos_close_app", app=app_clean)

        # Handle YouTube tab closing
        if app_clean.lower() == "youtube":
            yt_script = """
            tell application "System Events"
                set isChromeRunning to (count (every process whose bundle identifier is "com.google.Chrome")) > 0
                set isBraveRunning to (count (every process whose bundle identifier is "com.brave.Browser")) > 0
                set isSafariRunning to (count (every process whose bundle identifier is "com.apple.Safari")) > 0
            end tell
            if isChromeRunning then
                try
                    tell application "Google Chrome"
                        repeat with w in windows
                            repeat with t in (reverse of tabs of w)
                                if URL of t contains "youtube.com" then close t
                            end repeat
                        end repeat
                    end tell
                end try
            end if
            if isBraveRunning then
                try
                    tell application "Brave Browser"
                        repeat with w in windows
                            repeat with t in (reverse of tabs of w)
                                if URL of t contains "youtube.com" then close t
                            end repeat
                        end repeat
                    end tell
                end try
            end if
            if isSafariRunning then
                try
                    tell application "Safari"
                        repeat with w in windows
                            repeat with t in (reverse of tabs of w)
                                if URL of t contains "youtube.com" then close t
                            end repeat
                        end repeat
                    end tell
                end try
            end if
            """
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/osascript", "-e", yt_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return {
                "status": "success",
                "application": "YouTube",
                "message": "Successfully closed YouTube tabs",
            }

        # 1. Graceful quit via osascript
        script = f'tell application "{app_clean}" to quit'
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # 2. Force terminate via pkill as well to guarantee application completely exits
        pkill_proc = await asyncio.create_subprocess_exec(
            "/usr/bin/pkill", "-f", "-i", app_clean,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await pkill_proc.communicate()

        return {
            "status": "success",
            "application": app_clean,
            "message": f"Successfully closed {app_clean}",
        }

    async def search_web(self, query: str) -> dict[str, Any]:
        """Search the web for a query in the user's default browser."""
        import urllib.parse
        encoded = urllib.parse.quote_plus(query.strip())
        url = f"https://www.google.com/search?q={encoded}"
        res = await self.open_url(url)
        res["query"] = query
        res["message"] = f"Searched Google for '{query}'"
        return res

    async def search_youtube(self, query: str = "") -> dict[str, Any]:
        """Search and play a video on YouTube, reusing any open YouTube tab in Chrome/Brave/Safari."""
        import urllib.parse
        q_clean = query.strip()
        if q_clean:
            encoded = urllib.parse.quote_plus(q_clean)
            target_url = f"https://www.youtube.com/results?search_query={encoded}"
            msg = f"Playing '{q_clean}' on YouTube"
        else:
            target_url = "https://www.youtube.com"
            msg = "Opened YouTube"

        # Tab reuse script for Chrome, Brave, Safari
        reuse_script = f'''
        with timeout of 1 second
            set targetUrl to "{target_url}"
            tell application "System Events"
                set isChromeRunning to (count (every process whose bundle identifier is "com.google.Chrome")) > 0
                set isBraveRunning to (count (every process whose bundle identifier is "com.brave.Browser")) > 0
                set isSafariRunning to (count (every process whose bundle identifier is "com.apple.Safari")) > 0
            end tell

            if isChromeRunning then
                try
                    tell application "Google Chrome"
                        repeat with w in windows
                            set tabIdx to 1
                            repeat with t in tabs of w
                                if URL of t contains "youtube.com" then
                                    set active tab index of w to tabIdx
                                    set index of w to 1
                                    set URL of t to targetUrl
                                    activate
                                    return "reused_chrome"
                                end if
                                set tabIdx to tabIdx + 1
                            end repeat
                        end repeat
                    end tell
                end try
            end if

            if isBraveRunning then
                try
                    tell application "Brave Browser"
                        repeat with w in windows
                            set tabIdx to 1
                            repeat with t in tabs of w
                                if URL of t contains "youtube.com" then
                                    set active tab index of w to tabIdx
                                    set index of w to 1
                                    set URL of t to targetUrl
                                    activate
                                    return "reused_brave"
                                end if
                                set tabIdx to tabIdx + 1
                            end repeat
                        end repeat
                    end tell
                end try
            end if

            if isSafariRunning then
                try
                    tell application "Safari"
                        repeat with w in windows
                            set tabIdx to 1
                            repeat with t in tabs of w
                                if URL of t contains "youtube.com" then
                                    set current tab of w to t
                                    set index of w to 1
                                    set URL of t to targetUrl
                                    activate
                                    return "reused_safari"
                                end if
                                set tabIdx to tabIdx + 1
                            end repeat
                        end repeat
                    end tell
                end try
            end if

            return "not_found"
        end timeout
        '''
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/osascript", "-e", reuse_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1.8)
            status_res = stdout.decode().strip()
        except (TimeoutError, subprocess.SubprocessError, OSError, RuntimeError):
            status_res = "not_found"

        if status_res != "not_found" and status_res.startswith("reused"):
            logger.info("macos_youtube_tab_reused", status=status_res, query=q_clean)
            return {
                "status": "success",
                "tab_reused": True,
                "url": target_url,
                "query": q_clean,
                "message": msg,
            }

        # Fallback: No existing YouTube tab open, open in default browser
        res = await self.open_url(target_url)
        res["query"] = q_clean
        res["tab_reused"] = False
        res["message"] = msg
        return res

    async def control_media(self, action: str) -> dict[str, Any]:
        """Control media playback on macOS (play/pause, next, previous, forward, backward, mute)."""
        action_clean = action.strip().lower()

        # YouTube and general media controls mapped to AppleScript keystrokes
        script = ""
        desc = ""
        if action_clean in ("play_pause", "pause", "resume", "play", "toggle"):
            script = 'tell application "System Events" to keystroke "k"'
            desc = "Toggled playback"
        elif action_clean in ("next", "next_video", "skip"):
            script = 'tell application "System Events" to keystroke "N" using {shift down}'
            desc = "Playing next video"
        elif action_clean in ("previous", "prev", "prev_video", "back"):
            script = 'tell application "System Events" to keystroke "P" using {shift down}'
            desc = "Playing previous video"
        elif action_clean in ("forward", "seek_forward", "aage"):
            script = 'tell application "System Events" to keystroke "l"'
            desc = "Skipped forward 10 seconds"
        elif action_clean in ("backward", "rewind", "piche"):
            script = 'tell application "System Events" to keystroke "j"'
            desc = "Rewound 10 seconds"
        elif action_clean in ("mute", "unmute"):
            script = 'tell application "System Events" to keystroke "m"'
            desc = "Toggled mute"
        elif action_clean in ("fullscreen",):
            script = 'tell application "System Events" to keystroke "f"'
            desc = "Toggled fullscreen"
        else:
            raise ValueError(f"Unsupported media action: '{action}'")

        logger.info("macos_control_media", action=action_clean)
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        return {
            "status": "success",
            "action": action_clean,
            "message": desc,
        }

    async def spotify_play(self, query: str = "") -> dict[str, Any]:
        """Play a specific song/artist on Spotify or resume playback."""
        import urllib.parse
        q_clean = query.strip()
        # Filter out common conversational speech filler phrases (e.g. "ka jo koi ek pehla baja")
        q_clean = re.sub(
            r"\b(ka|ki|ke|jo|koi|ek|pehla|first|baja|bajao|sunao|chalao|play|song|gana|gaana|track|music|on spotify)\b",
            "",
            q_clean,
            flags=re.IGNORECASE,
        ).strip()
        q_clean = re.sub(r"\s+", " ", q_clean).strip()

        if q_clean:
            encoded = urllib.parse.quote(q_clean)
            script = f'''
            tell application "Spotify"
                activate
                play track "spotify:search:{encoded}"
                delay 0.3
                play
            end tell
            '''
            msg = f"Playing '{q_clean}' on Spotify"
        else:
            script = '''
            tell application "Spotify"
                activate
                play
            end tell
            '''
            msg = "Resumed Spotify playback"

        logger.info("macos_spotify_play", query=q_clean)
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {"status": "success", "query": q_clean, "message": msg}

    async def spotify_control(self, action: str) -> dict[str, Any]:
        """Control Spotify playback (next, previous, pause, play, toggle)."""
        act = action.strip().lower()
        if act in ("next", "next_song", "next_track"):
            script = 'tell application "Spotify" to next track'
            msg = "Playing next song on Spotify"
        elif act in ("previous", "prev", "previous_song", "prev_song"):
            script = 'tell application "Spotify" to previous track'
            msg = "Playing previous song on Spotify"
        elif act in ("pause", "stop"):
            script = 'tell application "Spotify" to pause'
            msg = "Paused Spotify"
        elif act in ("play", "resume"):
            script = 'tell application "Spotify" to play'
            msg = "Resumed Spotify"
        else:
            script = 'tell application "Spotify" to playpause'
            msg = "Toggled Spotify playback"

        logger.info("macos_spotify_control", action=act)
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {"status": "success", "action": act, "message": msg}

    async def create_note(self, title: str, body: str) -> dict[str, Any]:
        """Create a new note in Apple Notes."""
        t_clean = (title or "New Note").replace('"', '\\"').replace("\n", " ")
        b_clean = (body or "").replace('"', '\\"').replace("\n", "<br>")
        html_body = f"<div><h2>{t_clean}</h2><p>{b_clean}</p></div>"

        script = f'''
        tell application "Notes"
            activate
            make new note with properties {{body:"{html_body}"}}
        end tell
        '''
        logger.info("macos_create_note", title=t_clean)
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {
            "status": "success",
            "title": title,
            "body": body,
            "message": f"Created new note '{title}' in Notes app",
        }

    async def whatsapp_draft_message(self, contact: str, message: str) -> dict[str, Any]:
        """Stage a message in WhatsApp for a contact without sending it."""
        c_clean = contact.replace('"', '\\"').replace("'", "")
        m_clean = message.replace('"', '\\"')

        # Use clipboard pasting for flawless emoji and multilingual character support
        script = f'''
        set the clipboard to "{m_clean}"
        try
            tell application id "net.whatsapp.WhatsApp" to activate
        on error
            tell application "WhatsApp" to activate
        end try
        delay 0.5
        tell application "System Events"
            -- Focus search bar
            keystroke "f" using {{command down}}
            delay 0.3
            keystroke "{c_clean}"
            delay 0.8
            -- Select first contact match
            key code 125
            delay 0.15
            key code 36
            delay 0.5
            -- Paste message into chat input
            keystroke "v" using {{command down}}
        end tell
        '''
        logger.info("macos_whatsapp_draft", contact=contact)
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {
            "status": "staged",
            "contact": contact,
            "message": message,
        }

    async def whatsapp_confirm_send(self) -> dict[str, Any]:
        """Confirm and send the staged WhatsApp message by sending the Return key."""
        script = '''
        try
            tell application id "net.whatsapp.WhatsApp" to activate
        on error
            tell application "WhatsApp" to activate
        end try
        delay 0.25
        tell application "System Events"
            key code 36
        end tell
        '''
        logger.info("macos_whatsapp_confirm_send")
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {"status": "sent", "message": "WhatsApp message sent"}

    async def whatsapp_cancel_send(self) -> dict[str, Any]:
        """Cancel and delete the staged WhatsApp message draft."""
        script = '''
        try
            tell application id "net.whatsapp.WhatsApp" to activate
        on error
            tell application "WhatsApp" to activate
        end try
        delay 0.25
        tell application "System Events"
            keystroke "a" using {command down}
            delay 0.1
            key code 51
        end tell
        '''
        logger.info("macos_whatsapp_cancel_send")
        proc = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript", "-e", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return {"status": "cancelled", "message": "WhatsApp message draft cancelled"}

    async def get_frontmost_app(self) -> str:
        """Get the name of the currently active frontmost application."""
        script = 'tell application "System Events" to get name of first application process whose frontmost is true'
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/osascript", "-e", script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip()
        except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
            logger.warning(f"Failed to get frontmost app: {exc}")
        return ""

    async def scroll(self, direction: str = "down", amount: int = 5, delta_x: int = 0) -> dict[str, Any]:
        """Perform scrolling in the active window."""
        from packages.shared.nexus_shared.integrations.macos.engine import post_scroll

        dir_clean = direction.lower()
        delta_y = -amount if dir_clean in ("down", "niche", "bottom") else amount
        dx = -amount if dir_clean in ("right", "daye") else (amount if dir_clean in ("left", "baye") else delta_x)
        logger.info("macos_scroll", direction=direction, delta_y=delta_y, delta_x=dx)
        success = await asyncio.to_thread(post_scroll, delta_y=delta_y, delta_x=dx)
        return {"status": "success" if success else "failed", "direction": direction, "delta_y": delta_y, "delta_x": dx}

    async def click_coords(self, x: int, y: int, button: str = "left", click_count: int = 1) -> dict[str, Any]:
        """Click at specific screen coordinates."""
        from packages.shared.nexus_shared.integrations.macos.engine import post_mouse_click_coords

        logger.info("macos_click_coords", x=x, y=y, button=button, click_count=click_count)
        success = await asyncio.to_thread(post_mouse_click_coords, x=x, y=y, button=button, click_count=click_count)
        return {"status": "success" if success else "failed", "x": x, "y": y, "button": button, "click_count": click_count}

    async def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 15) -> dict[str, Any]:
        """Drag mouse between two screen coordinates."""
        from packages.shared.nexus_shared.integrations.macos.engine import post_mouse_drag

        logger.info("macos_mouse_drag", start=(start_x, start_y), end=(end_x, end_y), steps=steps)
        success = await asyncio.to_thread(post_mouse_drag, start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y, steps=steps)
        return {"status": "success" if success else "failed", "start": (start_x, start_y), "end": (end_x, end_y)}

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a keyboard key."""
        from packages.shared.nexus_shared.integrations.macos.engine import post_key_press

        logger.info("macos_press_key", key=key)
        success = await asyncio.to_thread(post_key_press, key=key)
        return {"status": "success" if success else "failed", "key": key}

    async def list_windows(self, on_screen_only: bool = True, filter_app: str | None = None) -> list[dict[str, Any]]:
        """List open application windows."""
        from packages.shared.nexus_shared.integrations.macos.engine import list_all_windows

        logger.info("macos_list_windows", on_screen_only=on_screen_only, filter_app=filter_app)
        return await asyncio.to_thread(list_all_windows, on_screen_only=on_screen_only, filter_app=filter_app)

    async def read_window_content(self, app_name: str | None = None, window_index: int = 1, max_depth: int = 4) -> dict[str, Any]:
        """Read UI elements and text content from a window."""
        from packages.shared.nexus_shared.integrations.macos.engine import (
            read_window_content as engine_read_window_content,
        )

        target_app = app_name
        if not target_app:
            target_app = await self.get_frontmost_app() or "Finder"
        return await engine_read_window_content(app_name=target_app, window_index=window_index, max_depth=max_depth)
