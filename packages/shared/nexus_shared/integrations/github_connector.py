"""GitHub External Integration Connector for NEXUS."""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from packages.shared.nexus_shared.integrations.base import BaseConnector
from packages.shared.nexus_shared.tools.base import BaseTool

GITHUB_API_BASE = "https://api.github.com"


# -----------------------------------------------------------------------------
# GitHub Credential Store (InMemory cache populated by DB or connect())
# -----------------------------------------------------------------------------
_github_tokens: dict[str, str] = {}


def set_user_github_token(user_id: str, token: str) -> None:
    _github_tokens[user_id] = token


def get_user_github_token(user_id: str) -> str | None:
    return _github_tokens.get(user_id)


def _get_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# -----------------------------------------------------------------------------
# 1. github.list_issues
# -----------------------------------------------------------------------------
class GitHubListIssuesInput(BaseModel):
    repo: str = Field(..., description="Repository in 'owner/repo' format.")
    state: str = Field(default="open", description="Issue state: 'open', 'closed', or 'all'.")


class GitHubListIssuesOutput(BaseModel):
    repo: str
    issues: list[dict[str, Any]]


class GitHubListIssuesTool(BaseTool):
    name = "github.list_issues"
    description = "List issues for a GitHub repository."
    input_schema = GitHubListIssuesInput
    output_schema = GitHubListIssuesOutput
    required_capability = "github.list_issues"
    default_risk_level = "LOW"
    timeout_seconds = 30.0

    async def run(
        self,
        user_id: str,
        params: GitHubListIssuesInput,
        context: dict[str, Any] | None = None,
    ) -> GitHubListIssuesOutput:
        token = get_user_github_token(user_id)
        headers = _get_headers(token) if token else {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{params.repo}/issues",
                headers=headers,
                params={"state": params.state},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"GitHub API error ({resp.status_code}): {resp.text}")
            raw_issues = resp.json()
            issues = [
                {
                    "id": item.get("id"),
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "html_url": item.get("html_url"),
                }
                for item in raw_issues
                if isinstance(item, dict) and "pull_request" not in item
            ]
            return GitHubListIssuesOutput(repo=params.repo, issues=issues)


# -----------------------------------------------------------------------------
# 2. github.read_file
# -----------------------------------------------------------------------------
class GitHubReadFileInput(BaseModel):
    repo: str = Field(..., description="Repository in 'owner/repo' format.")
    path: str = Field(..., description="Path to file within repository.")
    ref: str = Field(default="main", description="Branch, tag, or commit SHA.")


class GitHubReadFileOutput(BaseModel):
    repo: str
    path: str
    content: str
    sha: str | None = None


class GitHubReadFileTool(BaseTool):
    name = "github.read_file"
    description = "Read a file from a GitHub repository."
    input_schema = GitHubReadFileInput
    output_schema = GitHubReadFileOutput
    required_capability = "github.read_file"
    default_risk_level = "LOW"
    timeout_seconds = 30.0

    async def run(
        self,
        user_id: str,
        params: GitHubReadFileInput,
        context: dict[str, Any] | None = None,
    ) -> GitHubReadFileOutput:
        token = get_user_github_token(user_id)
        headers = _get_headers(token) if token else {}
        headers["Accept"] = "application/vnd.github.raw+json"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{params.repo}/contents/{params.path}",
                headers=headers,
                params={"ref": params.ref},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"GitHub file read failed ({resp.status_code}): {resp.text}")
            return GitHubReadFileOutput(
                repo=params.repo,
                path=params.path,
                content=resp.text,
            )


# -----------------------------------------------------------------------------
# 3. github.create_issue (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class GitHubCreateIssueInput(BaseModel):
    repo: str = Field(..., description="Repository in 'owner/repo' format.")
    title: str = Field(..., description="Issue title.")
    body: str = Field(..., description="Issue body text in Markdown.")


class GitHubCreateIssueOutput(BaseModel):
    id: int
    number: int
    title: str
    html_url: str


class GitHubCreateIssueTool(BaseTool):
    name = "github.create_issue"
    description = "Create a new issue in a GitHub repository (requires user approval)."
    input_schema = GitHubCreateIssueInput
    output_schema = GitHubCreateIssueOutput
    required_capability = "github.create_issue"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return f"github:{validated_params.model_dump().get('repo', '')}/issues"

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        data = validated_params.model_dump()
        return f"# {data.get('title')}\n\n{data.get('body')}"

    async def run(
        self,
        user_id: str,
        params: GitHubCreateIssueInput,
        context: dict[str, Any] | None = None,
    ) -> GitHubCreateIssueOutput:
        token = get_user_github_token(user_id)
        if not token:
            raise RuntimeError("No GitHub integration credentials configured for this user.")
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GITHUB_API_BASE}/repos/{params.repo}/issues",
                headers=headers,
                json={"title": params.title, "body": params.body},
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Failed to create GitHub issue ({resp.status_code}): {resp.text}")
            data = resp.json()
            return GitHubCreateIssueOutput(
                id=data.get("id", 0),
                number=data.get("number", 0),
                title=data.get("title", params.title),
                html_url=data.get("html_url", ""),
            )


# -----------------------------------------------------------------------------
# 4. github.create_pr (MUTATING / HIGH RISK)
# -----------------------------------------------------------------------------
class GitHubCreatePRInput(BaseModel):
    repo: str = Field(..., description="Repository in 'owner/repo' format.")
    title: str = Field(..., description="Pull request title.")
    head: str = Field(..., description="Branch containing changes.")
    base: str = Field(default="main", description="Target branch to merge into.")
    body: str = Field(..., description="Pull request description.")


class GitHubCreatePROutput(BaseModel):
    id: int
    number: int
    title: str
    html_url: str


class GitHubCreatePRTool(BaseTool):
    name = "github.create_pr"
    description = "Create a pull request in a GitHub repository (requires user approval)."
    input_schema = GitHubCreatePRInput
    output_schema = GitHubCreatePROutput
    required_capability = "github.create_pr"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0

    def get_target_resource(self, validated_params: BaseModel) -> str:
        return f"github:{validated_params.model_dump().get('repo', '')}/pulls"

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        data = validated_params.model_dump()
        return f"# {data.get('title')}\n\n{data.get('body')}"

    async def run(
        self,
        user_id: str,
        params: GitHubCreatePRInput,
        context: dict[str, Any] | None = None,
    ) -> GitHubCreatePROutput:
        token = get_user_github_token(user_id)
        if not token:
            raise RuntimeError("No GitHub integration credentials configured for this user.")
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{GITHUB_API_BASE}/repos/{params.repo}/pulls",
                headers=headers,
                json={
                    "title": params.title,
                    "head": params.head,
                    "base": params.base,
                    "body": params.body,
                },
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"Failed to create GitHub PR ({resp.status_code}): {resp.text}")
            data = resp.json()
            return GitHubCreatePROutput(
                id=data.get("id", 0),
                number=data.get("number", 0),
                title=data.get("title", params.title),
                html_url=data.get("html_url", ""),
            )


# -----------------------------------------------------------------------------
# GitHub Connector
# -----------------------------------------------------------------------------
class GitHubConnector(BaseConnector):
    """GitHub API Connector implementing BaseConnector lifecycle."""

    provider = "github"

    async def connect(
        self,
        user_id: str,
        credentials: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        token = credentials.get("token") or credentials.get("access_token")
        if not token:
            raise ValueError("Missing 'token' in GitHub credentials")
        set_user_github_token(user_id, token)
        return True

    async def disconnect(self, user_id: str) -> bool:
        _github_tokens.pop(user_id, None)
        return True

    async def health_check(self, user_id: str) -> dict[str, Any]:
        token = get_user_github_token(user_id)
        if not token:
            return {"provider": self.provider, "status": "disconnected", "error": "No token stored"}
        headers = _get_headers(token)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/user", headers=headers)
            if resp.status_code == 200:
                user_info = resp.json()
                return {
                    "provider": self.provider,
                    "status": "healthy",
                    "login": user_info.get("login"),
                    "name": user_info.get("name"),
                }
            return {
                "provider": self.provider,
                "status": "unhealthy",
                "status_code": resp.status_code,
                "error": resp.text,
            }

    def register_tools(self) -> list[BaseTool]:
        return [
            GitHubListIssuesTool(),
            GitHubReadFileTool(),
            GitHubCreateIssueTool(),
            GitHubCreatePRTool(),
        ]
