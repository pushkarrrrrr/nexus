"""Google Workspace External Integration Connector (Gmail & Calendar) for NEXUS."""

import base64
from typing import Any

import httpx
from pydantic import BaseModel, Field

from packages.shared.nexus_shared.integrations.base import BaseConnector
from packages.shared.nexus_shared.tools.base import BaseTool

GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


# -----------------------------------------------------------------------------
# Google Credential Store (InMemory cache populated by DB or connect())
# -----------------------------------------------------------------------------
_google_tokens: dict[str, str] = {}


def set_user_google_token(user_id: str, token: str) -> None:
    _google_tokens[user_id] = token


def get_user_google_token(user_id: str) -> str | None:
    return _google_tokens.get(user_id)


def _get_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# -----------------------------------------------------------------------------
# 1. google.list_calendar_events
# -----------------------------------------------------------------------------
class GoogleListCalendarEventsInput(BaseModel):
    time_min: str = Field(..., description="Start of time range (RFC3339 timestamp).")
    time_max: str = Field(..., description="End of time range (RFC3339 timestamp).")
    max_results: int = Field(default=10, description="Maximum number of events to return.")


class GoogleListCalendarEventsOutput(BaseModel):
    events: list[dict[str, Any]]


class GoogleListCalendarEventsTool(BaseTool):
    name = "google.list_calendar_events"
    description = "List Google Calendar events within a specified time range."
    input_schema = GoogleListCalendarEventsInput
    output_schema = GoogleListCalendarEventsOutput
    required_capability = "google.list_calendar_events"
    default_risk_level = "LOW"
    timeout_seconds = 30.0

    async def run(
        self,
        user_id: str,
        params: GoogleListCalendarEventsInput,
        context: dict[str, Any] | None = None,
    ) -> GoogleListCalendarEventsOutput:
        token = get_user_google_token(user_id)
        if not token:
            raise RuntimeError("No Google integration credentials configured for this user.")
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events",
                headers=headers,
                params={
                    "timeMin": params.time_min,
                    "timeMax": params.time_max,
                    "maxResults": params.max_results,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Google Calendar API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            events = [
                {
                    "id": item.get("id"),
                    "summary": item.get("summary", "No Title"),
                    "start": item.get("start"),
                    "end": item.get("end"),
                    "status": item.get("status"),
                }
                for item in data.get("items", [])
            ]
            return GoogleListCalendarEventsOutput(events=events)


# -----------------------------------------------------------------------------
# 2. google.create_calendar_event (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class GoogleCreateCalendarEventInput(BaseModel):
    summary: str = Field(..., description="Event title.")
    start_time: str = Field(..., description="Start time (RFC3339 timestamp).")
    end_time: str = Field(..., description="End time (RFC3339 timestamp).")
    description: str = Field(default="", description="Optional event description.")


class GoogleCreateCalendarEventOutput(BaseModel):
    id: str
    summary: str
    html_link: str


class GoogleCreateCalendarEventTool(BaseTool):
    name = "google.create_calendar_event"
    description = "Create a new event in Google Calendar (requires user approval)."
    input_schema = GoogleCreateCalendarEventInput
    output_schema = GoogleCreateCalendarEventOutput
    required_capability = "google.create_calendar_event"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return "calendar:primary/events"

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        data = validated_params.model_dump()
        return f"Event: {data.get('summary')}\nTime: {data.get('start_time')} to {data.get('end_time')}\nDescription: {data.get('description')}"

    async def run(
        self,
        user_id: str,
        params: GoogleCreateCalendarEventInput,
        context: dict[str, Any] | None = None,
    ) -> GoogleCreateCalendarEventOutput:
        token = get_user_google_token(user_id)
        if not token:
            raise RuntimeError("No Google integration credentials configured for this user.")
        headers = _get_headers(token)
        payload = {
            "summary": params.summary,
            "description": params.description,
            "start": {"dateTime": params.start_time},
            "end": {"dateTime": params.end_time},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events",
                headers=headers,
                json=payload,
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Failed to create Google Calendar event ({resp.status_code}): {resp.text}"
                )
            data = resp.json()
            return GoogleCreateCalendarEventOutput(
                id=data.get("id", ""),
                summary=data.get("summary", params.summary),
                html_link=data.get("htmlLink", ""),
            )


# -----------------------------------------------------------------------------
# 3. google.search_gmail
# -----------------------------------------------------------------------------
class GoogleSearchGmailInput(BaseModel):
    query: str = Field(..., description="Gmail search query filter syntax.")
    max_results: int = Field(default=10, description="Max messages to retrieve.")


class GoogleSearchGmailOutput(BaseModel):
    query: str
    messages: list[dict[str, Any]]


class GoogleSearchGmailTool(BaseTool):
    name = "google.search_gmail"
    description = "Search emails in Gmail using standard query filter syntax."
    input_schema = GoogleSearchGmailInput
    output_schema = GoogleSearchGmailOutput
    required_capability = "google.search_gmail"
    default_risk_level = "LOW"
    timeout_seconds = 30.0

    async def run(
        self,
        user_id: str,
        params: GoogleSearchGmailInput,
        context: dict[str, Any] | None = None,
    ) -> GoogleSearchGmailOutput:
        token = get_user_google_token(user_id)
        if not token:
            raise RuntimeError("No Google integration credentials configured for this user.")
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GMAIL_API_BASE}/messages",
                headers=headers,
                params={"q": params.query, "maxResults": params.max_results},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Gmail search failed ({resp.status_code}): {resp.text}")
            data = resp.json()
            messages = data.get("messages", [])
            return GoogleSearchGmailOutput(query=params.query, messages=messages)


# -----------------------------------------------------------------------------
# 4. google.send_email (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class GoogleSendEmailInput(BaseModel):
    to: str = Field(..., description="Recipient email address.")
    subject: str = Field(..., description="Email subject line.")
    body: str = Field(..., description="Plaintext email message body.")


class GoogleSendEmailOutput(BaseModel):
    id: str
    to: str
    subject: str


class GoogleSendEmailTool(BaseTool):
    name = "google.send_email"
    description = "Send an email via Gmail (requires user approval)."
    input_schema = GoogleSendEmailInput
    output_schema = GoogleSendEmailOutput
    required_capability = "google.send_email"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return f"email:{validated_params.model_dump().get('to', '')}"

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        data = validated_params.model_dump()
        return f"To: {data.get('to')}\nSubject: {data.get('subject')}\n\n{data.get('body')}"

    async def run(
        self,
        user_id: str,
        params: GoogleSendEmailInput,
        context: dict[str, Any] | None = None,
    ) -> GoogleSendEmailOutput:
        token = get_user_google_token(user_id)
        if not token:
            raise RuntimeError("No Google integration credentials configured for this user.")
        headers = _get_headers(token)

        # Build raw RFC 2822 email and base64url encode
        raw_msg = f"To: {params.to}\r\nSubject: {params.subject}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{params.body}"
        raw_b64 = base64.urlsafe_b64encode(raw_msg.encode("utf-8")).decode("ascii")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/messages/send",
                headers=headers,
                json={"raw": raw_b64},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Failed to send email ({resp.status_code}): {resp.text}")
            data = resp.json()
            return GoogleSendEmailOutput(
                id=data.get("id", ""),
                to=params.to,
                subject=params.subject,
            )


# -----------------------------------------------------------------------------
# Google Workspace Connector
# -----------------------------------------------------------------------------
class GoogleWorkspaceConnector(BaseConnector):
    """Google Workspace API Connector implementing BaseConnector lifecycle."""

    provider = "google"

    async def connect(
        self,
        user_id: str,
        credentials: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        token = credentials.get("token") or credentials.get("access_token")
        if not token:
            raise ValueError("Missing 'token' in Google credentials")
        set_user_google_token(user_id, token)
        return True

    async def disconnect(self, user_id: str) -> bool:
        _google_tokens.pop(user_id, None)
        return True

    async def health_check(self, user_id: str) -> dict[str, Any]:
        token = get_user_google_token(user_id)
        if not token:
            return {"provider": self.provider, "status": "disconnected", "error": "No token stored"}
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GMAIL_API_BASE}/profile", headers=headers)
            if resp.status_code == 200:
                profile = resp.json()
                return {
                    "provider": self.provider,
                    "status": "healthy",
                    "email": profile.get("emailAddress"),
                }
            return {
                "provider": self.provider,
                "status": "unhealthy",
                "status_code": resp.status_code,
                "error": resp.text,
            }

    def register_tools(self) -> list[BaseTool]:
        return [
            GoogleListCalendarEventsTool(),
            GoogleCreateCalendarEventTool(),
            GoogleSearchGmailTool(),
            GoogleSendEmailTool(),
        ]
