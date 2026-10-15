"""Voice Action Dispatcher for NEXUS Ambient Layer.

Parses natural speech commands (English, Hindi, Hinglish) and immediately executes
Mac OS native actions:
1. Multi-Task Sequential Queue: Executes multiple actions sequentially if user gives multiple tasks
2. YouTube Video Search, Playback & Tab Reuse:
   - "youtube kholo" -> Opens YouTube & asks "YouTube open kar diya! Kya play karna hai?"
   - "youtube par [query] play karo" -> Reuses existing YouTube tab in Chrome/Brave/Safari and plays
3. Spotify Full Playback & Song Control:
   - "spotify kholo" -> Opens Spotify & asks "Spotify open kar diya! Kaun sa song play karna hai?"
   - "spotify par [query] play karo" -> Plays song directly
   - Next, previous, pause, resume
4. Apple Notes Integration & Context Saving:
   - "note app open karo" -> Opens Notes & asks "Notes app open kar diya! Kya likhna hai?"
   - "note mein [xyz] likho" -> Creates note directly
   - "isko note mein add kar do" -> Saves previous assistant answer into Notes
5. WhatsApp Staged Integration with Human-in-the-Loop Confirmation:
   - "whatsapp kholo" -> Opens WhatsApp & asks "WhatsApp open kar diya! Kise koi message send karna hai kya?"
   - "whatsapp par [contact] ko message [text] bhejo" -> Types draft, asks "Send kar doon?"
   - User confirms ("send kar do") -> Sends Return key
   - User denies ("cancel" / "mat bhejo") -> Discards draft
6. Mac Application Control (Open & Close native apps)
7. Media Navigation Controls (Next, Previous, Forward, Rewind, Pause, Resume, Mute)
8. Web & Product Search
"""

import asyncio
import json
import re
import time
from typing import Any

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.computer import get_computer_adapter
from packages.shared.nexus_shared.logging import get_logger
from packages.types.nexus_types.schemas import CompletionRequest

logger = get_logger("nexus.ambient.dispatcher")

# In-memory Human-in-the-Loop pending confirmation state (90s TTL)
PENDING_CONFIRMATION: dict[str, Any] | None = None

# Interactive conversational state machine for multi-turn voice prompts (90s TTL)
INTERACTIVE_STATE: dict[str, Any] | None = None

# Context memory of the last assistant reply (for "isko note mein add kar do")
LAST_ASSISTANT_REPLY: str = ""


def set_last_assistant_reply(reply: str) -> None:
    """Store the most recent assistant answer or explanation."""
    global LAST_ASSISTANT_REPLY
    if reply and reply.strip():
        LAST_ASSISTANT_REPLY = reply.strip()


def get_last_assistant_reply() -> str:
    """Retrieve the most recent assistant answer or explanation."""
    return LAST_ASSISTANT_REPLY


# Common application name aliases and common voice misspellings for macOS
APP_ALIASES: dict[str, str] = {
    "spotify": "Spotify",
    "sportify": "Spotify",
    "spotfy": "Spotify",
    "spoti": "Spotify",
    "chrome": "Google Chrome",
    "chorme": "Google Chrome",
    "chrom": "Google Chrome",
    "google chrome": "Google Chrome",
    "safari": "Safari",
    "calculator": "Calculator",
    "calc": "Calculator",
    "notes": "Notes",
    "note": "Notes",
    "apple notes": "Notes",
    "code": "Visual Studio Code",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "iterm2": "iTerm2",
    "finder": "Finder",
    "settings": "System Settings",
    "system settings": "System Settings",
    "preferences": "System Settings",
    "music": "Music",
    "apple music": "Music",
    "whatsapp": "WhatsApp",
    "watsap": "WhatsApp",
    "whatapp": "WhatsApp",
    "whatsap": "WhatsApp",
    "youtube": "YouTube",
    "yotube": "YouTube",
    "yt": "YouTube",
    "telegram": "Telegram",
    "slack": "Slack",
    "discord": "Discord",
    "photos": "Photos",
    "mail": "Mail",
    "calendar": "Calendar",
    "reminders": "Reminders",
    "messages": "Messages",
    "facetime": "FaceTime",
    "weather": "Weather",
    "maps": "Maps",
    "notion": "Notion",
    "figma": "Figma",
    "brave": "Brave Browser",
    "arc": "Arc",
    "firefox": "Firefox",
}


def normalize_app_name(raw: str) -> str:
    """Resolve user speech app name into standard macOS application name."""
    clean = raw.strip().lower()
    clean = re.sub(r"^(mac\s*ka|mac\s*me|mac\s*mein|mac\s*par|system\s*ka|computer\s*ka|mera)\s+", "", clean)
    clean = re.sub(r"^(the|an|a)\s+", "", clean)
    clean = re.sub(r"\s+app$", "", clean)
    clean = clean.strip()
    return APP_ALIASES.get(clean, clean.title())


def split_multi_task_commands(text: str) -> list[str]:
    """Split compound speech commands into discrete sequential tasks if multi-task connectors are present."""
    # Connectors: "aur fir", "aur phir", "and then", "fir", "phir", "aur", "and"
    # Only split if surrounded by valid command segments
    raw_parts = re.split(r"\s+(?:aur\s+fir|aur\s+phir|and\s+then|fir|phir)\s+", text, flags=re.IGNORECASE)
    if len(raw_parts) > 1:
        return [p.strip() for p in raw_parts if p.strip()]

    # Check for "aur" or "and" joining distinct action verbs
    parts = re.split(r"\s+(?:aur|and)\s+", text, flags=re.IGNORECASE)
    if len(parts) >= 2:
        # Verify that parts look like actionable commands
        action_keywords = ("kholo", "open", "play", "chalao", "likho", "send", "bhejo", "close", "band", "search", "note")
        action_count = sum(1 for p in parts if any(k in p.lower() for k in action_keywords))
        if action_count >= 2:
            return [p.strip() for p in parts if p.strip()]

    return [text]


async def process_command_with_gemini(
    message: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Use Google Gemini in real-time to semantically understand natural voice commands.

    Extracts structured action queues (closing apps, opening apps, playing YouTube/Spotify,
    controlling playback, taking notes, WhatsApp drafts) regardless of phrasing, accents,
    Hindi/Hinglish/English mixing, or phonetic spelling variations (e.g. 'sportify' -> 'Spotify').
    """
    clean_msg = message.strip()
    if not clean_msg:
        return None

    gateway = get_model_gateway()

    context_str = ""
    if context and context.get("app_name"):
        context_str = f" [Current Frontmost App: {context.get('app_name')}]"

    system_prompt = (
        "You are the NEXUS Real-Time OS Voice Action Processor for macOS.\n"
        "Your task: Determine if the user's spoken instruction contains executable OS commands.\n"
        "Users may speak in English, Hindi, Hinglish, or casual slang with typos (e.g. 'sportify band kro', 'yt kholo', 'zara chrome open kardo').\n\n"
        "SUPPORTED ACTION TYPES:\n"
        "- 'close_app': Close/Quit/Exit an app. target: standard app name (e.g. 'Spotify', 'Google Chrome', 'Notes', 'WhatsApp', 'Terminal', 'Calculator', 'Finder', 'Safari'). Auto-correct typos like 'sportify' -> 'Spotify'.\n"
        "- 'open_app': Open/Launch an app. target: standard app name.\n"
        "- 'scroll': Scroll up/down in the active window. target: 'down' or 'up'. args: {'amount': int (default 5)}.\n"
        "- 'read_screen': Read and summarize what is visible on the screen or in current/specified app. target: app name or 'current'.\n"
        "- 'list_windows': List all open windows and applications on screen. target: ''.\n"
        "- 'press_key': Press a keyboard key. target: 'enter', 'space', 'escape', 'tab', 'page_down', 'page_up', 'home', 'end', 'backspace'.\n"
        "- 'click_screen': Click on screen coordinates. target: 'center' or description. args: {'x': int, 'y': int}.\n"
        "- 'spotify_play': Search & play song on Spotify. target: song/artist name (e.g. 'arijit singh', 'lofi beats').\n"
        "- 'spotify_control': Control Spotify playback. target: 'play', 'pause', 'resume', 'next', 'previous'.\n"
        "- 'youtube_play': Open & play video on YouTube. target: search query.\n"
        "- 'notes_write': Write/save note into Apple Notes. target: content to write.\n"
        "- 'whatsapp_send': Draft/send WhatsApp message. target: contact name, args: {'message': text}.\n"
        "- 'media_control': Playback control. target: 'next', 'previous', 'pause', 'resume', 'mute', 'forward', 'backward'.\n"
        "- 'web_search': Search Google. target: search query.\n\n"
        "RULES:\n"
        "1. If user asks to close/quit/band an app (e.g. 'sportify band kro', 'spotify band kar do', 'band karo spotify', 'close spotify'), "
        "set action_type='close_app' and target='Spotify'.\n"
        "2. If user asks to scroll (e.g. 'scroll down', 'niche scroll karo', 'thoda niche jao', 'page up'), set action_type='scroll' with target='down' or 'up'.\n"
        "3. If user asks what is on screen or to read the window (e.g. 'screen pe kya hai', 'read screen', 'what is on my screen'), set action_type='read_screen'.\n"
        "4. If user asks what windows or apps are open (e.g. 'kaun se windows open hai', 'what windows are open'), set action_type='list_windows'.\n"
        "5. If user asks to press a key (e.g. 'press enter', 'enter dabao', 'space press karo'), set action_type='press_key' with target=key_name.\n"
        "6. If multiple commands are present (e.g. 'spotify band karo aur chrome kholo'), extract ALL actions in sequential order.\n"
        "7. If conversational question without OS actions, set is_action=false, actions=[].\n"
        "8. Always provide a natural, concise 1-sentence reply in Hindi/Hinglish/English suitable for voice speech.\n"
        "5. Respond with ONLY valid JSON: {\"is_action\": bool, \"actions\": [{\"action_type\": string, \"target\": string, \"args\": {}}], \"reply\": string}."
    )

    prompt = f"User Voice Input: {clean_msg}{context_str}"

    try:
        req = CompletionRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            model="gemini-3.5-flash-lite",
            temperature=0.1,
            max_tokens=180,
        )
        response = await gateway.complete(
            req,
            provider_name="gemini",
            timeout_sec=8.0,
            max_retries=1,
        )

        content = response.content.strip()
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1).strip()
            else:
                content = content.replace("```json", "").replace("```", "").strip()

        data = json.loads(content)
        if not isinstance(data, dict):
            return None

        is_action = data.get("is_action", False)
        actions = data.get("actions", [])
        reply = data.get("reply", "").replace("*", "").replace("#", "").strip()

        return {
            "is_action": bool(is_action and actions),
            "actions": actions if is_action else [],
            "reply": reply or "Theek hai, process kar diya.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[process_command_with_gemini] Gemini parsing failed: {exc}")
        return None


async def execute_action_plan(actions: list[dict[str, Any]], reply_text: str) -> dict[str, Any]:
    """Execute a sequence of extracted actions one by one (Queue Method)."""
    global INTERACTIVE_STATE
    adapter = get_computer_adapter()
    results = []

    for action in actions:
        atype = action.get("action_type", "")
        target = action.get("target", "").strip()
        args = action.get("args") or {}

        try:
            if atype == "close_app":
                app_name = normalize_app_name(target) if target else "Spotify"
                logger.info("gemini_exec_close_app", app=app_name)
                res = await adapter.close_application(app_name)
                results.append(res)

            elif atype == "open_app":
                app_name = normalize_app_name(target) if target else ""
                if app_name.lower() == "spotify":
                    await adapter.open_application("Spotify")
                    INTERACTIVE_STATE = {"type": "awaiting_spotify_query", "timestamp": time.time()}
                elif "youtube" in app_name.lower():
                    await adapter.open_url("https://www.youtube.com")
                    INTERACTIVE_STATE = {"type": "awaiting_youtube_query", "timestamp": time.time()}
                elif "note" in app_name.lower():
                    await adapter.open_application("Notes")
                    INTERACTIVE_STATE = {"type": "awaiting_note_content", "timestamp": time.time()}
                elif "whatsapp" in app_name.lower():
                    await adapter.open_application("WhatsApp")
                    INTERACTIVE_STATE = {"type": "awaiting_whatsapp_recipient", "timestamp": time.time()}
                elif app_name:
                    logger.info("gemini_exec_open_app", app=app_name)
                    res = await adapter.open_application(app_name)
                    results.append(res)

            elif atype == "spotify_play":
                logger.info("gemini_exec_spotify_play", query=target)
                res = await adapter.spotify_play(target or "top hits")
                results.append(res)

            elif atype == "spotify_control":
                logger.info("gemini_exec_spotify_control", control=target)
                res = await adapter.spotify_control(target or "play")
                results.append(res)

            elif atype == "youtube_play":
                logger.info("gemini_exec_youtube_play", query=target)
                res = await adapter.search_youtube(target or "trending")
                results.append(res)

            elif atype == "notes_write":
                content = target or args.get("content", "")
                title = args.get("title", "Voice Note")
                logger.info("gemini_exec_notes_write", title=title)
                res = await adapter.create_note(title, content)
                results.append(res)

            elif atype == "whatsapp_send":
                contact = target
                msg = args.get("message", "")
                logger.info("gemini_exec_whatsapp_send", contact=contact)
                res = await adapter.whatsapp_draft_message(contact, msg)
                results.append(res)

            elif atype == "media_control":
                logger.info("gemini_exec_media_control", action=target)
                res = await adapter.control_media(target or "play_pause")
                results.append(res)

            elif atype == "web_search":
                logger.info("gemini_exec_web_search", query=target)
                res = await adapter.search_web(target)
                results.append(res)

            elif atype == "scroll":
                direction = target.lower() if target else "down"
                amount = int(args.get("amount") or 6)
                logger.info("gemini_exec_scroll", direction=direction, amount=amount)
                res = await adapter.scroll(direction=direction, amount=amount)
                results.append(res)

            elif atype == "read_screen":
                app_target = target if target and target.lower() not in ("active", "current", "screen") else None
                logger.info("gemini_exec_read_screen", app=app_target)
                content_res = await adapter.read_window_content(app_name=app_target)
                results.append(content_res)
                if content_res and content_res.get("text_summary"):
                    app_label = content_res.get("app_name") or "active window"
                    summary = content_res["text_summary"].strip().replace("\n", " ")
                    if summary:
                        reply_text = f"Screen par {app_label} open hai: {summary[:200]}"

            elif atype == "list_windows":
                logger.info("gemini_exec_list_windows")
                win_list = await adapter.list_windows(on_screen_only=True)
                results.append(win_list)
                if win_list:
                    names = list(dict.fromkeys(
                        w["owner_name"] for w in win_list
                        if w.get("owner_name") and w.get("layer") == 0 and w.get("owner_name") not in ("Window Server", "Dock")
                    ))
                    if names:
                        reply_text = f"Screen par open applications hain: {', '.join(names[:6])}."

            elif atype == "press_key":
                key = target.lower() if target else args.get("key", "enter")
                logger.info("gemini_exec_press_key", key=key)
                res = await adapter.press_key(key)
                results.append(res)

            elif atype == "click_screen":
                x = int(args.get("x") or 600)
                y = int(args.get("y") or 400)
                logger.info("gemini_exec_click_screen", x=x, y=y)
                res = await adapter.click_coords(x, y)
                results.append(res)

            if len(actions) > 1:
                await asyncio.sleep(0.25)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error executing queued action '{atype}' for '{target}': {e}")

    return {
        "action": "gemini.executed_plan",
        "actions_count": len(actions),
        "reply": reply_text,
        "voice": reply_text,
    }


async def try_dispatch_voice_action(message: str, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Analyze spoken voice commands, handling queueing, HITL confirmation, and interactive prompts."""
    global PENDING_CONFIRMATION, INTERACTIVE_STATE

    clean = message.strip()
    if not clean:
        return None

    adapter = get_computer_adapter()
    text = clean.lower()

    # -------------------------------------------------------------------------
    # 0. Active Human-in-the-Loop Confirmation Check (WhatsApp Send / Cancel)
    # -------------------------------------------------------------------------
    if PENDING_CONFIRMATION:
        now = time.time()
        # Expire after 90 seconds
        if now - PENDING_CONFIRMATION.get("timestamp", 0) < 90.0:
            # 1. Negative cancellation FIRST: "cancel", "mat bhejo", "no", "nahi", "rehne do"
            if PENDING_CONFIRMATION["type"] == "whatsapp" and re.search(
                r"\b(cancel|mat\s*(?:bhejo|bhej|send\s*kro|send\s*karo)|no|nahi|nah|stop|rehne\s*do)\b",
                text,
            ):
                logger.info("ambient_whatsapp_cancelled")
                await adapter.whatsapp_cancel_send()
                PENDING_CONFIRMATION = None
                return {
                    "action": "whatsapp.send_cancelled",
                    "reply": "Theek hai, message cancel kar diya gaya hai.",
                    "voice": "Message draft cancelled.",
                }

            # 2. Positive confirmation: "send kar do", "haan bhej do", "bhej do", "yes", "send"
            if PENDING_CONFIRMATION["type"] == "whatsapp" and re.search(
                r"\b(send\s*(?:kar\s*do|kro|kr\s*do|do)?|bhej\s*(?:do|de|dijiye)?|haan|yes|yep|kar\s*do|kr\s*do|sure|ok|okay)\b",
                text,
            ):
                contact = PENDING_CONFIRMATION["contact"]
                logger.info("ambient_whatsapp_confirmed_send", contact=contact)
                await adapter.whatsapp_confirm_send()
                PENDING_CONFIRMATION = None
                return {
                    "action": "whatsapp.send_confirmed",
                    "reply": f"{contact} ko message send kar diya!",
                    "voice": f"Message sent to {contact}.",
                }
        else:
            PENDING_CONFIRMATION = None

    # -------------------------------------------------------------------------
    # 0.1 Active Interactive State Handling (Follow-up response from user)
    # -------------------------------------------------------------------------
    if INTERACTIVE_STATE:
        now = time.time()
        if now - INTERACTIVE_STATE.get("timestamp", 0) < 90.0:
            state_type = INTERACTIVE_STATE.get("type")

            # Check if user explicitly wants to cancel
            if re.search(r"\b(cancel|stop|kuch\s*nahi|rehne\s*do|no|nahi)\b", text):
                INTERACTIVE_STATE = None
                return {
                    "action": "interactive.cancelled",
                    "reply": "Theek hai, cancel kar diya.",
                    "voice": "Cancelled.",
                }
        else:
            INTERACTIVE_STATE = None

    # Augment context with active interactive state for Gemini
    merged_context = dict(context or {})
    if INTERACTIVE_STATE:
        merged_context["interactive_state"] = INTERACTIVE_STATE.get("type")

    # -------------------------------------------------------------------------
    # 0.2 Context Memory: "Isko note mein add kar do" / "Save this to Notes"
    # -------------------------------------------------------------------------
    if (
        re.search(r"\b(isko|ise|yeh|ye|it|this)\s*(?:ko)?\s*(?:note|notes)\s*(?:app\s*)?(?:me|mein|par|pe)?\s*(?:add|save|likh|daal)\b", text)
        or re.search(r"\b(add\s*this\s*to\s*notes|save\s*(?:this\s*)?to\s*notes|make\s*a\s*note\s*of\s*this|note\s*this\s*down|isko\s*note\s*banao)\b", text)
        or (("isko" in text or "ise" in text or "this" in text) and ("note" in text or "notes" in text) and any(k in text for k in ("add", "save", "likh", "banao", "daal")))
    ):
        last_answer = get_last_assistant_reply()
        if last_answer:
            words = last_answer.split()
            title = ("NEXUS: " + " ".join(words[:4])).title()
            logger.info("ambient_note_save_context", title=title)
            await adapter.create_note(title, last_answer)
            return {
                "action": "notes.context_saved",
                "title": title,
                "body": last_answer,
                "reply": "Jo maine abhi bataya tha, usse Notes app mein save kar diya hai!",
                "voice": "Saved previous answer into Notes app.",
            }
        else:
            return {
                "action": "notes.no_context",
                "reply": "Abhi koi previous answer nahi mila. Kya note likhna chahte hain?",
                "voice": "No previous response found to save. What would you like to note?",
            }

    # -------------------------------------------------------------------------
    # 0.3 Fast Local Multi-Task Sequential Queue (Instant local execution, 0ms network)
    # -------------------------------------------------------------------------
    sub_tasks = split_multi_task_commands(clean)
    if len(sub_tasks) > 1:
        logger.info("ambient_multi_task_queue_detected", tasks=sub_tasks)
        executed_replies: list[str] = []
        for task_item in sub_tasks:
            res = await _execute_single_voice_action(task_item)
            if res and res.get("reply"):
                executed_replies.append(res["reply"])

        if executed_replies:
            combined_reply = " Aur ".join(executed_replies)
            return {
                "action": "queue.multi_task_executed",
                "reply": combined_reply,
                "voice": combined_reply,
            }

    # -------------------------------------------------------------------------
    # 0.4 Fast Local Single Action Dispatch (Instant <15ms execution for all standard macOS commands)
    # -------------------------------------------------------------------------
    local_action = await _execute_single_voice_action(clean)
    if local_action:
        logger.info("ambient_fast_local_action_dispatched", action=local_action.get("action"))
        return local_action

    # -------------------------------------------------------------------------
    # 0.5 Real-Time Gemini Semantic Voice Command Understanding & Execution
    # (Used when phrasing is non-standard, conversational, or requires LLM reasoning)
    # -------------------------------------------------------------------------
    gemini_plan = await process_command_with_gemini(clean, merged_context)
    if gemini_plan:
        if gemini_plan.get("is_action") and gemini_plan.get("actions"):
            INTERACTIVE_STATE = None  # Clear interactive state upon action execution
            logger.info("ambient_gemini_action_executed", actions=gemini_plan["actions"])
            return await execute_action_plan(gemini_plan["actions"], gemini_plan["reply"])
        elif not gemini_plan.get("is_action") and gemini_plan.get("reply"):
            return {
                "action": "gemini.conversational_reply",
                "reply": gemini_plan["reply"],
                "voice": gemini_plan["reply"],
            }

    # -------------------------------------------------------------------------
    # 0.6 Local Interactive State Fallback (Offline)
    # -------------------------------------------------------------------------
    if INTERACTIVE_STATE and (time.time() - INTERACTIVE_STATE.get("timestamp", 0) < 90.0):
        state_type = INTERACTIVE_STATE.get("type")
        if state_type == "awaiting_youtube_query":
            INTERACTIVE_STATE = None
            clean_query = re.sub(r"\b(play|kro|karo|chalao|lagao|video|vide|song|gaana|gana)\b", "", text).strip()
            query = clean_query or text
            logger.info("ambient_interactive_youtube_play", query=query)
            await adapter.search_youtube(query)
            return {
                "action": "youtube.play",
                "query": query,
                "reply": f"YouTube par '{query}' play kar diya hai!",
                "voice": f"Playing {query} on YouTube.",
            }

        if state_type == "awaiting_spotify_query":
            INTERACTIVE_STATE = None
            clean_song = re.sub(r"\b(play|kro|karo|chalao|lagao|song|gaana|gana|track)\b", "", text).strip()
            song = clean_song or text
            logger.info("ambient_interactive_spotify_play", query=song)
            await adapter.spotify_play(song)
            return {
                "action": "spotify.play_song",
                "query": song,
                "reply": f"Spotify par '{song}' play kar diya!",
                "voice": f"Playing {song} on Spotify.",
            }

        if state_type == "awaiting_notes_content":
            INTERACTIVE_STATE = None
            note_body = clean
            words = note_body.split()
            title = " ".join(words[:4]).title() if len(words) >= 4 else note_body.title()
            logger.info("ambient_interactive_create_note", title=title)
            await adapter.create_note(title, note_body)
            return {
                "action": "notes.create",
                "title": title,
                "body": note_body,
                "reply": "Notes app mein naya note likh diya hai!",
                "voice": "Created new note in Notes app.",
            }

    return None


async def _execute_single_voice_action(message: str) -> dict[str, Any] | None:
    """Internal router for executing a single atomic voice command."""
    global PENDING_CONFIRMATION, INTERACTIVE_STATE

    adapter = get_computer_adapter()
    text = message.strip().lower()

    # -------------------------------------------------------------------------
    # 1. WhatsApp Integration: Draft & Interactive Prompt
    # -------------------------------------------------------------------------
    # Check for standalone "whatsapp open karo" / "whatsapp kholo"
    clean_wa_open = re.sub(r"\b(whatsapp|kholo|open|app|kro|karo|start|launch)\b", "", text).strip()
    if ("whatsapp" in text or "what's app" in text) and not clean_wa_open and not any(k in text for k in ("bolo", "likho", "bhejo", "send", "message", "text")):
        logger.info("ambient_whatsapp_open_interactive")
        await adapter.open_application("WhatsApp")
        INTERACTIVE_STATE = {
            "type": "awaiting_whatsapp_draft",
            "timestamp": time.time(),
        }
        return {
            "action": "whatsapp.interactive_open",
            "reply": "WhatsApp open kar diya! Kise koi message send karna hai kya?",
            "voice": "Opened WhatsApp. Would you like to send a message to someone?",
        }

    # WhatsApp draft message with recipient and content
    wa_match = re.search(
        r"(?:whatsapp\s*(?:par|pe|me|mein)?\s*)?([a-zA-Z0-9\s]+?)\s*ko\s*(?:message|text)?\s*(?:bolo|likho|bhejo|send\s*(?:kro|karo))?\s*[:\s,-]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if (wa_match or "whatsapp" in text or " ko " in text) and any(
        k in text for k in ("bolo", "likho", "bhejo", "send", "message")
    ) and not any(k in text for k in ("note", "notes", "spotify", "youtube")):
        contact = ""
        msg_text = ""

        if wa_match:
            raw_contact = wa_match.group(1).strip()
            raw_msg = wa_match.group(2).strip()
            contact = re.sub(
                r"^(?:whatsapp\s*(?:par|pe|me|mein)?|jake|ja\s*ke|iss\s*insaan|uss\s*insaan|person)\s+",
                "",
                raw_contact,
                flags=re.IGNORECASE,
            ).strip().title()
            msg_text = raw_msg
        else:
            parts = re.split(r"\s+ko\s+", text, maxsplit=1)
            if len(parts) == 2:
                raw_contact, raw_msg = parts[0].strip(), parts[1].strip()
                contact = re.sub(
                    r"^(?:whatsapp\s*(?:par|pe|me|mein)?|jake|ja\s*ke|iss\s*insaan|uss\s*insaan|person)\s+",
                    "",
                    raw_contact,
                    flags=re.IGNORECASE,
                ).strip().title()
                msg_text = raw_msg

        if contact and msg_text:
            msg_clean = re.sub(
                r"\s*(?:aur\s*send\s*(?:kro|karo)\s*(?:yeh\s*text)?|send\s*kro|send\s*karo|bhej\s*do)$",
                "",
                msg_text,
                flags=re.IGNORECASE,
            )
            msg_clean = re.sub(
                r"^(?:bolo|likho|message\s*likho|message\s*bhejo|bhejo|send\s*(?:kro|karo))\s*(?:ki|yeh)?\s*",
                "",
                msg_clean,
                flags=re.IGNORECASE,
            )
            msg_clean = re.sub(
                r"\s*(?:bolo|likho|bhejo)$",
                "",
                msg_clean,
                flags=re.IGNORECASE,
            ).strip()

            final_msg = msg_clean or msg_text
            final_msg = final_msg[0].upper() + final_msg[1:] if len(final_msg) > 1 else final_msg

            logger.info("ambient_whatsapp_draft_initiating", contact=contact, message=final_msg)
            await adapter.whatsapp_draft_message(contact, final_msg)

            PENDING_CONFIRMATION = {
                "type": "whatsapp",
                "contact": contact,
                "message": final_msg,
                "timestamp": time.time(),
            }

            return {
                "action": "whatsapp.draft_staged",
                "contact": contact,
                "message": final_msg,
                "reply": f"Aapke bolne par maine {contact} ke liye yeh text type kar diya hai: '{final_msg}'. Send kar doon?",
                "voice": f"I have typed '{final_msg}' for {contact}. Should I send it?",
            }

    # -------------------------------------------------------------------------
    # 2. Apple Notes Integration: Direct & Interactive Prompt
    # -------------------------------------------------------------------------
    # Interactive "note app open karo" / "notes kholo" without body
    if (
        re.search(r"^(?:note\s*app|notes\s*app|notes|note)\s*(?:open\s*(?:kro|karo)|kholo|launch|start)$", text)
        or re.search(r"^(?:open|kholo|launch)\s*(?:note\s*app|notes\s*app|notes|apple\s*notes)$", text)
    ):
        logger.info("ambient_notes_open_interactive")
        await adapter.open_application("Notes")
        INTERACTIVE_STATE = {
            "type": "awaiting_notes_content",
            "timestamp": time.time(),
        }
        return {
            "action": "notes.interactive_open",
            "reply": "Notes app open kar diya! Kya likhna hai?",
            "voice": "Opened Notes app. What would you like to write?",
        }

    # Explicit note creation: "note likho xyz", "notes mein jao meeting notes likho"
    if any(k in text for k in ("note app", "notes app", "new note", "note likho", "naya note", "note banao", "note mein jao", "notes mein")):
        clean_content = re.sub(
            r"^(?:note\s*app\s*khole\s*new\s*note\s*mein\s*jake|notes\s*app\s*khole|new\s*note\s*mein\s*jake|new\s*note\s*mein|notes\s*mein\s*jake|notes\s*mein|note\s*mein\s*jao|note\s*mein|note\s*likho\s*:?|ek\s*naya\s*note\s*banao|naya\s*note\s*banao|new\s*note)\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        clean_content = re.sub(
            r"\s*(?:likho|vo\s*sub\s*likho|yeh\s*sub\s*likho|kro|karo|banao)$",
            "",
            clean_content,
            flags=re.IGNORECASE,
        ).strip()

        note_body = clean_content or "Notes by NEXUS Voice Assistant"
        words = note_body.split()
        title = " ".join(words[:4]).title() if len(words) >= 4 else note_body.title()

        logger.info("ambient_create_note", title=title)
        await adapter.create_note(title, note_body)
        return {
            "action": "notes.create",
            "title": title,
            "body": note_body,
            "reply": "Notes app mein naya note likh diya hai!",
            "voice": "Created new note in Notes app.",
        }

    # -------------------------------------------------------------------------
    # 3. Spotify Full Control & Interactive Prompt
    # -------------------------------------------------------------------------
    if "spotify" in text or (
        any(k in text for k in ("song", "gana", "gaana", "track"))
        and not any(k in text for k in ("youtube", "video", "vide"))
    ):
        # Interactive check: "spotify kholo" / "open spotify" without query
        clean_sp_open = re.sub(r"\b(spotify|kholo|open|app|kro|karo|start|launch|music)\b", "", text).strip()
        if ("spotify" in text) and not clean_sp_open and not any(k in text for k in ("play", "chalao", "lagao", "next", "previous", "pause", "resume")):
            logger.info("ambient_spotify_open_interactive")
            await adapter.open_application("Spotify")
            INTERACTIVE_STATE = {
                "type": "awaiting_spotify_query",
                "timestamp": time.time(),
            }
            return {
                "action": "spotify.interactive_open",
                "reply": "Spotify open kar diya! Kaun sa song play karna hai?",
                "voice": "Opened Spotify. Which song would you like to play?",
            }

        # Next song
        if re.search(r"\b(next\s*(?:song|gana|gaana|track)?|agla\s*(?:song|gana|gaana)|skip)\b", text):
            await adapter.spotify_control("next")
            return {
                "action": "spotify.next",
                "reply": "Spotify par agla gaana chala diya!",
                "voice": "Playing next song on Spotify.",
            }

        # Previous song
        if re.search(
            r"\b(previous\s*(?:song|gana|gaana|track)?|prev\s*(?:song|gana)?|p[eh]+le\s*w[al]+\s*(?:song|gana|gaana)|pichla\s*(?:song|gana|gaana))\b",
            text,
        ):
            await adapter.spotify_control("previous")
            return {
                "action": "spotify.previous",
                "reply": "Spotify par pehle wala gaana chala diya!",
                "voice": "Playing previous song on Spotify.",
            }

        # Pause Spotify
        if re.search(r"\b(pause|roko|stop)\b", text):
            await adapter.spotify_control("pause")
            return {
                "action": "spotify.pause",
                "reply": "Spotify pause kar diya.",
                "voice": "Spotify paused.",
            }

        # Specific song check FIRST before generic resume
        song_query = re.sub(
            r"\b(spotify\s*(?:pe|par|me|mein)?|yeh\s*song|yeh\s*gana|song|gana|gaana|track|play\s*(?:kro|karo)?|chalao|lagao|sunao|kro|karo|on\s*spotify|music)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if song_query and not re.search(r"^(next|previous|prev|pause|stop|resume|continue)$", song_query):
            logger.info("ambient_spotify_play_song", query=song_query)
            await adapter.spotify_play(song_query)
            return {
                "action": "spotify.play_song",
                "query": song_query,
                "reply": f"Spotify par '{song_query}' play kar diya!",
                "voice": f"Playing {song_query} on Spotify.",
            }

        # Resume / Play Spotify
        if re.search(r"\b(resume|continue|chalao|play)\b", text):
            await adapter.spotify_control("play")
            return {
                "action": "spotify.play",
                "reply": "Spotify continue kar diya.",
                "voice": "Resuming Spotify.",
            }

        final_song = song_query or "top hits"
        logger.info("ambient_spotify_play_song", query=final_song)
        await adapter.spotify_play(final_song)
        return {
            "action": "spotify.play_song",
            "query": final_song,
            "reply": f"Spotify par '{final_song}' play kar diya!",
            "voice": f"Playing {final_song} on Spotify.",
        }

    # -------------------------------------------------------------------------
    # 4. Media Controls (Next, Previous, Forward, Rewind, Pause, Resume, Mute)
    # -------------------------------------------------------------------------
    if re.search(r"\b(next\s*(?:video|vide|song|track)?|agla\s*(?:video|vide|gana)?|skip\s*(?:video|vide|song)?|aage\s*wala\s*(?:video|vide))\b", text):
        await adapter.control_media("next")
        return {
            "action": "media.next",
            "reply": "Agla video play kar diya!",
            "voice": "Playing next video.",
        }

    if re.search(r"\b(previous\s*(?:video|vide|song)?|prev\s*(?:video|vide)?|pichla\s*(?:video|vide|gana)?|p[eh]+le\s*w[al]+\s*(?:video|vide)?|pichle\s*(?:video|vide))\b", text):
        await adapter.control_media("previous")
        return {
            "action": "media.previous",
            "reply": "Pehle wala video chala diya!",
            "voice": "Playing previous video.",
        }

    if re.search(r"\b(aage\s*(?:kro|karo|badhao|chalao)?|forward\s*(?:kro|karo)?|fast\s*forward|skip\s*ahead|10\s*second\s*aage)\b", text) and not re.search(r"\b(video|vide|song)\b", text):
        await adapter.control_media("forward")
        return {
            "action": "media.forward",
            "reply": "10 second aage kar diya!",
            "voice": "Skipped forward ten seconds.",
        }

    if re.search(r"\b(piche\s*(?:kro|karo|jao|badhao)?|rewind\s*(?:kro|karo)?|skip\s*back|10\s*second\s*piche)\b", text) and not re.search(r"\b(video|vide|song)\b", text):
        await adapter.control_media("backward")
        return {
            "action": "media.backward",
            "reply": "10 second piche kar diya!",
            "voice": "Rewound ten seconds.",
        }

    if re.search(r"\b(pause\s*(?:video|vide|gana)?|(?:video|vide|gana)\s*pause|(?:video|vide|gana)\s*roko|pause\s*(?:kro|karo)|rok\s*do|stop\s*(?:video|vide)?)\b", text) or text in ("pause", "roko", "stop"):
        await adapter.control_media("pause")
        return {
            "action": "media.pause",
            "reply": "Video pause kar diya.",
            "voice": "Playback paused.",
        }

    if re.search(r"\b(resume\s*(?:video|vide)?|(?:video|vide)\s*resume|play\s*(?:video|vide)|continue\s*(?:kro|karo)|chalao|shuru\s*(?:kro|karo))\b", text) and not re.search(r"\byoutube\b", text):
        await adapter.control_media("resume")
        return {
            "action": "media.resume",
            "reply": "Video continue kar diya.",
            "voice": "Resuming playback.",
        }

    if re.search(r"\b(mute\s*(?:kro|karo)?|unmute\s*(?:kro|karo)?|awaz\s*band\s*(?:kro|karo))\b", text):
        await adapter.control_media("mute")
        return {
            "action": "media.mute",
            "reply": "Audio toggle kar diya.",
            "voice": "Muted audio.",
        }

    # -------------------------------------------------------------------------
    # 5. YouTube Tab Reuse & Interactive Prompt
    # -------------------------------------------------------------------------
    if "youtube" in text:
        # Check if user just said "youtube kholo" / "open youtube" without a specific video
        clean_yt = re.sub(
            r"\b(youtube|kholo|open|kro|karo|app|chalao|start|launch)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        if not clean_yt or clean_yt in ("pe", "par", "me", "mein", "video", "vide"):
            logger.info("ambient_youtube_open_interactive")
            await adapter.search_youtube("")
            INTERACTIVE_STATE = {
                "type": "awaiting_youtube_query",
                "timestamp": time.time(),
            }
            return {
                "action": "youtube.interactive_open",
                "reply": "YouTube open kar diya! Kya play karna hai?",
                "voice": "Opened YouTube. What would you like to play?",
            }

        # User specified a video query to play
        cleaned_query = re.sub(
            r"\b(youtube|mein|me|par|pe|play|kro|karo|toh|kro|chalao|video|vide|koi|bhi|lagao|song|search|kholo)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        query = cleaned_query or "trending video"

        logger.info("ambient_youtube_play", query=query)
        await adapter.search_youtube(query)
        return {
            "action": "youtube.play",
            "query": query,
            "reply": f"YouTube par '{query}' play kar diya hai!",
            "voice": f"Playing {query} on YouTube.",
        }

    # -------------------------------------------------------------------------
    # 6. Close Application
    # -------------------------------------------------------------------------
    close_match = re.search(
        r"(?:close|quit|band\s*(?:kro|karo|kar\s*do|kr\s*do)|exit)\s+([a-zA-Z0-9\s]+?)(?:\s*(?:app|application|kro|karo|ko|kar\s*do|kr\s*do))?$|^([a-zA-Z0-9\s]+?)\s+(?:close\s*(?:kro|karo)|band\s*(?:kro|karo|kar\s*do)|quit\s*(?:kro|karo))",
        text,
        re.IGNORECASE,
    )
    if close_match and not any(k in text for k in ("tab", "window", "video", "vide", "gana", "song")):
        raw_app = (close_match.group(1) or close_match.group(2) or "").strip()
        if raw_app and raw_app not in ("this", "it", "yeh", "kuch", "all"):
            app_name = normalize_app_name(raw_app)
            try:
                logger.info("ambient_close_app", app=app_name)
                await adapter.close_application(app_name)
                return {
                    "action": "applications.close",
                    "application": app_name,
                    "reply": f"{app_name} close kar diya gaya hai.",
                    "voice": f"Closed {app_name}.",
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to close app '{app_name}': {e}")
                return {
                    "action": "applications.close",
                    "application": app_name,
                    "reply": f"{app_name} close karne ki koshish ki.",
                    "voice": f"Attempted to close {app_name}.",
                }

    # -------------------------------------------------------------------------
    # 7. Screen Scroll Control (Up, Down, Left, Right)
    # -------------------------------------------------------------------------
    if re.search(
        r"\b(scroll\s*(?:down|up|niche|upar|kro|karo)?|niche\s*(?:scroll|kro|karo|jao)|upar\s*(?:scroll|kro|karo|jao)|page\s*(?:down|up)|thoda\s*(?:niche|upar)|aur\s*niche)\b",
        text,
    ):
        direction = "up" if any(k in text for k in ("up", "upar", "page up")) else "down"
        amount = 12 if any(k in text for k in ("page", "zyada", "fast", "pura")) else 6
        logger.info("ambient_screen_scroll", direction=direction, amount=amount)
        await adapter.scroll(direction=direction, amount=amount)
        reply = f"Screen {'upar' if direction == 'up' else 'niche'} scroll kar diya."
        voice = f"Scrolled {direction}."
        return {
            "action": "screen.scroll",
            "direction": direction,
            "amount": amount,
            "reply": reply,
            "voice": voice,
        }

    # -------------------------------------------------------------------------
    # 8. Read Screen / Active Window Inspection
    # -------------------------------------------------------------------------
    if (
        re.search(
            r"\b(screen\s*(?:par|pe)?\s*kya\s*hai|kya\s*likha\s*hai|read\s*(?:screen|window|content)|what(?:'s|\s*is)\s*on\s*(?:my\s*)?screen|is\s*window\s*me\s*kya\s*hai|active\s*window\s*read\s*kro)\b",
            text,
        )
        or ("screen" in text and any(k in text for k in ("read", "dekho", "batao", "padho")))
    ):
        logger.info("ambient_read_screen")
        window_info = await adapter.read_window_content()
        app_name = window_info.get("app_name") or "Application"
        summary = window_info.get("text_summary") or ""
        if summary:
            first_line = summary[:200].replace("\n", " ")
            reply = f"Screen par {app_name} dikh raha hai: {first_line}"
            voice = f"On screen in {app_name}: {first_line}"
        else:
            reply = f"Screen par {app_name} active hai."
            voice = f"{app_name} is active on screen."
        return {
            "action": "screen.read_content",
            "app_name": app_name,
            "reply": reply,
            "voice": voice,
        }

    # -------------------------------------------------------------------------
    # 9. List Open Windows & Active Applications
    # -------------------------------------------------------------------------
    if re.search(
        r"\b(kaun\s*(?:se|si)\s*(?:windows|apps|application)\s*open\s*hai|kya\s*kya\s*open\s*hai|what\s*windows\s*are\s*open|list\s*(?:all\s*)?windows|show\s*(?:open\s*)?windows|open\s*apps\s*dikhao)\b",
        text,
    ):
        logger.info("ambient_list_windows")
        windows = await adapter.list_windows(on_screen_only=True)
        app_names = list(dict.fromkeys(
            w["owner_name"] for w in windows
            if w.get("owner_name") and w.get("layer") == 0 and w.get("owner_name") not in ("Window Server", "Dock")
        ))
        if app_names:
            apps_str = ", ".join(app_names[:6])
            reply = f"Screen par yeh applications open hain: {apps_str}."
            voice = f"Open applications are: {apps_str}."
        else:
            reply = "Abhi screen par koi primary application window nahi mili."
            voice = "No visible application windows found."
        return {
            "action": "screen.list_windows",
            "applications": app_names,
            "reply": reply,
            "voice": voice,
        }

    # -------------------------------------------------------------------------
    # 10. Keyboard Key Press (Enter, Space, Escape, Tab, etc.)
    # -------------------------------------------------------------------------
    key_match = re.search(
        r"\b(?:press|hit|daba\s*do|dabao|type)\s*(enter|space|spacebar|escape|esc|tab|page\s*down|page\s*up|home|end|backspace)\b|\b(enter|space|spacebar|escape|esc|tab)\s*(?:press\s*kro|press\s*karo|dabao|daba\s*do)\b",
        text,
    )
    if key_match:
        raw_key = (key_match.group(1) or key_match.group(2) or "enter").strip().lower()
        if raw_key == "esc":
            raw_key = "escape"
        elif raw_key == "spacebar":
            raw_key = "space"
        elif "page down" in raw_key:
            raw_key = "page_down"
        elif "page up" in raw_key:
            raw_key = "page_up"
        logger.info("ambient_press_key", key=raw_key)
        await adapter.press_key(raw_key)
        return {
            "action": "keyboard.press_key",
            "key": raw_key,
            "reply": f"'{raw_key.title()}' key press kar diya.",
            "voice": f"Pressed {raw_key}.",
        }

    # -------------------------------------------------------------------------
    # 11. Screen Mouse Click / Coordinate Interaction
    # -------------------------------------------------------------------------
    if re.search(r"\b(click\s*(?:center|middle|screen)?|screen\s*pe\s*click\s*(?:kro|karo)|center\s*pe\s*click)\b", text):
        logger.info("ambient_screen_click")
        await adapter.click_coords(x=600, y=400)
        return {
            "action": "screen.click",
            "reply": "Screen par click kar diya.",
            "voice": "Clicked on screen.",
        }

    # -------------------------------------------------------------------------
    # 12. Open Application
    # -------------------------------------------------------------------------
    open_match = re.search(
        r"(?:open|launch|kholo|start|shuru\s*(?:kro|karo))\s+([a-zA-Z0-9\s]+?)(?:\s*(?:app|application|kro|karo|kar\s*do|kr\s*do|kijiye))?$|^([a-zA-Z0-9\s]+?)\s+(?:open\s*(?:kro|karo|kar\s*do|kr\s*do)|kholo|shuru\s*(?:kro|karo))",
        text,
        re.IGNORECASE,
    )
    if open_match and not any(k in text for k in ("web", "google", "youtube", "url", "link", "search", "window", "windows", "screen", "kaun", "kya", "hai")):
        raw_app = (open_match.group(1) or open_match.group(2) or "").strip()
        if raw_app and raw_app not in ("this", "it", "yeh", "kuch", "file"):
            app_name = normalize_app_name(raw_app)
            try:
                logger.info("ambient_open_app", app=app_name)
                await adapter.open_application(app_name)
                return {
                    "action": "applications.open",
                    "application": app_name,
                    "reply": f"{app_name} open kar diya!",
                    "voice": f"Opening {app_name} for you.",
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to open app '{app_name}': {e}")
                return {
                    "action": "applications.open",
                    "application": app_name,
                    "reply": f"{app_name} launch karne ki koshish ki.",
                    "voice": f"Attempted to open {app_name}.",
                }

    # -------------------------------------------------------------------------
    # 13. Web / Product Search
    # -------------------------------------------------------------------------
    if any(k in text for k in ("search", "dhoondho", "khojo", "web par", "google par", "google pe")):
        clean_q = re.sub(
            r"\b(web\s*par\s*jao|web\s*par|google\s*par|google\s*pe|google|internet|par\s*web|on\s*web|on\s*google)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        clean_q = re.sub(
            r"\b(search\s*(?:kro|karo|kijiye|krke|karke|kr\s*do|kar\s*do|karo\s*na)?|batao|toh\s*batao|dhoondho|khojo|find|look\s*up)\b",
            "",
            clean_q,
            flags=re.IGNORECASE,
        )
        clean_q = re.sub(
            r"\b(yeh|ye|chize|chizon|chiz|product|ke\s*bare\s*mein|ke\s*bare\s*me|kuch|bhi)\b",
            "",
            clean_q,
            flags=re.IGNORECASE,
        ).strip()

        final_query = clean_q or "trending products and news"
        logger.info("ambient_web_search", query=final_query)
        await adapter.search_web(final_query)
        return {
            "action": "browser.search",
            "query": final_query,
            "reply": f"Maine web par '{final_query}' search kar diya hai!",
            "voice": f"Searching the web for {final_query}.",
        }

    return None
