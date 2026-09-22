"""Pydantic schemas for Reversible Actions and Diff Approval REST endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiffPreviewRequest(BaseModel):
    target_path: str
    proposed_content: str
    action_type: str = Field(default="FILE_MODIFY")


class DiffPreviewResponse(BaseModel):
    target_path: str
    diff_patch: str
    lines_added: int
    lines_removed: int
    is_reversible: bool
    sha256_before: str | None
    sha256_after: str


class ActionSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    task_id: str | None
    step_id: str | None
    capability_name: str
    action_type: str
    is_reversible: bool
    target_path: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    diff_patch: str | None
    status: str
    reverted_at: datetime | None
    created_at: datetime


class ActionSnapshotListResponse(BaseModel):
    items: list[ActionSnapshotResponse]
    total: int


class RevertActionRequest(BaseModel):
    force: bool = False


class RevertActionResponse(BaseModel):
    snapshot_id: str
    status: str
    message: str
    target_path: str | None
    reverted_at: datetime
