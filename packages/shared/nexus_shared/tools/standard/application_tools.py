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
