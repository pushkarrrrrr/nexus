"""Standard Application and Browser Control Tools for NEXUS."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from packages.shared.nexus_shared.tools.base import BaseTool

# ---------------------------------------------------------------------------
# 1. applications.open
# ---------------------------------------------------------------------------


class ApplicationOpenInput(BaseModel):
    app_name: str = Field(
        ..., description="Name of the application to launch (e.g. 'Safari', 'Calculator', 'Notes')"
    )

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, v: str) -> str:
        v = v.strip()
        if not v or any(char in v for char in (";", "&", "|", "`", "$", "\n", "\r", ">", "<")):
            raise ValueError("Application name contains invalid characters")
        return v


class ApplicationOpenOutput(BaseModel):
    status: str
    application: str
    message: str


class ApplicationOpenTool(BaseTool):
    name = "applications.open"
    description = "Launch an approved native application on the host operating system."
    input_schema = ApplicationOpenInput
    output_schema = ApplicationOpenOutput
    required_capability = "system.configure"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: ApplicationOpenInput,
        context: dict[str, Any] | None = None,
    ) -> ApplicationOpenOutput:
        res = await self.adapter.open_application(params.app_name)
        return ApplicationOpenOutput(**res)


# ---------------------------------------------------------------------------
# 2. browser.open_url
# ---------------------------------------------------------------------------


class BrowserOpenUrlInput(BaseModel):
    url: str = Field(
        ..., description="Web URL to open in default browser (must be http:// or https://)"
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class BrowserOpenUrlOutput(BaseModel):
    status: str
    url: str
    message: str


class BrowserOpenUrlTool(BaseTool):
    name = "browser.open_url"
    description = "Open a valid web URL in the user's default browser."
    input_schema = BrowserOpenUrlInput
    output_schema = BrowserOpenUrlOutput
    required_capability = "browser.open"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: BrowserOpenUrlInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserOpenUrlOutput:
        res = await self.adapter.open_url(params.url)
        return BrowserOpenUrlOutput(**res)


# ---------------------------------------------------------------------------
# 3. applications.close
# ---------------------------------------------------------------------------


class ApplicationCloseInput(BaseModel):
    app_name: str = Field(
        ..., description="Name of the application to quit/close (e.g. 'Spotify', 'Safari', 'Calculator')"
    )

    @field_validator("app_name")
    @classmethod
    def validate_app_name(cls, v: str) -> str:
        v = v.strip()
        if not v or any(char in v for char in (";", "&", "|", "`", "$", "\n", "\r", ">", "<")):
            raise ValueError("Application name contains invalid characters")
        return v


class ApplicationCloseOutput(BaseModel):
    status: str
    application: str
    message: str


class ApplicationCloseTool(BaseTool):
    name = "applications.close"
    description = "Quit or close an active native application on the host operating system."
    input_schema = ApplicationCloseInput
    output_schema = ApplicationCloseOutput
    required_capability = "system.configure"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: ApplicationCloseInput,
        context: dict[str, Any] | None = None,
    ) -> ApplicationCloseOutput:
        res = await self.adapter.close_application(params.app_name)
        return ApplicationCloseOutput(**res)


# ---------------------------------------------------------------------------
# 4. browser.search
# ---------------------------------------------------------------------------


class BrowserSearchInput(BaseModel):
    query: str = Field(..., description="Query or product to search on the web")


class BrowserSearchOutput(BaseModel):
    status: str
    query: str
    url: str
    message: str


class BrowserSearchTool(BaseTool):
    name = "browser.search"
    description = "Search the web for information, products, or answers using the user's default browser."
    input_schema = BrowserSearchInput
    output_schema = BrowserSearchOutput
    required_capability = "browser.open"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: BrowserSearchInput,
        context: dict[str, Any] | None = None,
    ) -> BrowserSearchOutput:
        res = await self.adapter.search_web(params.query)
        return BrowserSearchOutput(**res)


# ---------------------------------------------------------------------------
# 5. youtube.play
# ---------------------------------------------------------------------------


class YouTubePlayInput(BaseModel):
    query: str = Field(..., description="Video, song, artist, or topic to search and play on YouTube")


class YouTubePlayOutput(BaseModel):
    status: str
    query: str
    url: str
    message: str


class YouTubePlayTool(BaseTool):
    name = "youtube.play"
    description = "Search and immediately play any video or music on YouTube in the default browser."
    input_schema = YouTubePlayInput
    output_schema = YouTubePlayOutput
    required_capability = "browser.open"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: YouTubePlayInput,
        context: dict[str, Any] | None = None,
    ) -> YouTubePlayOutput:
        res = await self.adapter.search_youtube(params.query)
        return YouTubePlayOutput(**res)


# ---------------------------------------------------------------------------
# 6. media.control
# ---------------------------------------------------------------------------


class MediaControlInput(BaseModel):
    action: str = Field(
        ...,
        description="Action to perform: 'play_pause', 'next', 'previous', 'forward', 'backward', 'mute'",
    )


class MediaControlOutput(BaseModel):
    status: str
    action: str
    message: str


class MediaControlTool(BaseTool):
    name = "media.control"
    description = "Control video/audio playback: toggle play/pause, next video, previous video, fast-forward, rewind, or mute."
    input_schema = MediaControlInput
    output_schema = MediaControlOutput
    required_capability = "system.configure"
    default_risk_level = "LOW"
    timeout_seconds = 5.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: MediaControlInput,
        context: dict[str, Any] | None = None,
    ) -> MediaControlOutput:
        res = await self.adapter.control_media(params.action)
        return MediaControlOutput(**res)
