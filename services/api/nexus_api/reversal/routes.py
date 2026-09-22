"""REST API Endpoints for Reversible Actions, Diff Previews, and Rollback Operations."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.errors import StateConflictError
from packages.shared.nexus_shared.models import ActionSnapshotModel, UserModel
from packages.shared.nexus_shared.policy.evaluator import normalize_resource_target
from packages.shared.nexus_shared.reversal.manager import SnapshotManager, compute_sha256
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db
from services.api.nexus_api.reversal.schemas import (
    ActionSnapshotListResponse,
    ActionSnapshotResponse,
    DiffPreviewRequest,
    DiffPreviewResponse,
    RevertActionRequest,
    RevertActionResponse,
)

reversal_router = APIRouter(prefix="/reversal", tags=["reversal"])
_snapshot_manager = SnapshotManager()


@reversal_router.post(
    "/diff/preview",
    response_model=DiffPreviewResponse,
    summary="Generate unified diff preview for pending mutation without applying it",
)
async def generate_diff_preview(
    payload: DiffPreviewRequest,
    current_user: UserModel = Depends(get_current_user),
) -> DiffPreviewResponse:
    normalized_path = normalize_resource_target(payload.target_path)
    filename = Path(normalized_path).name

    pre_state = _snapshot_manager.capture_pre_state(normalized_path, payload.action_type)
    before_content = pre_state.get("content", "")
    sha256_before = pre_state.get("sha256")

    diff_patch = _snapshot_manager.generate_diff(before_content, payload.proposed_content, filename)
    sha256_after = compute_sha256(payload.proposed_content)

    lines_added = sum(
        1 for line in diff_patch.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    lines_removed = sum(
        1 for line in diff_patch.splitlines() if line.startswith("-") and not line.startswith("---")
    )

    _, is_reversible = _snapshot_manager.classify_action("filesystem.modify", payload.action_type)

    return DiffPreviewResponse(
        target_path=normalized_path,
        diff_patch=diff_patch,
        lines_added=lines_added,
        lines_removed=lines_removed,
        is_reversible=is_reversible,
        sha256_before=sha256_before,
        sha256_after=sha256_after,
    )


@reversal_router.get(
    "/snapshots",
    response_model=ActionSnapshotListResponse,
    summary="List action snapshots with multi-tenant isolation",
)
async def list_snapshots(
    status_filter: str | None = Query(None, alias="status"),
    action_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ActionSnapshotListResponse:
    query = select(ActionSnapshotModel).where(ActionSnapshotModel.user_id == current_user.id)

    if status_filter:
        query = query.where(ActionSnapshotModel.status == status_filter.upper())
    if action_type:
        query = query.where(ActionSnapshotModel.action_type == action_type.upper())

    count_stmt = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    query = query.order_by(ActionSnapshotModel.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(query)
    snapshots = res.scalars().all()

    items = [ActionSnapshotResponse.model_validate(s) for s in snapshots]
    return ActionSnapshotListResponse(items=items, total=total)


@reversal_router.get(
    "/snapshots/{snapshot_id}",
    response_model=ActionSnapshotResponse,
    summary="Get detailed action snapshot and diff patch",
)
async def get_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ActionSnapshotResponse:
    stmt = select(ActionSnapshotModel).where(
        ActionSnapshotModel.id == snapshot_id,
        ActionSnapshotModel.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    snapshot = res.scalar_one_or_none()

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action snapshot '{snapshot_id}' not found.",
        )

    return ActionSnapshotResponse.model_validate(snapshot)


@reversal_router.post(
    "/snapshots/{snapshot_id}/revert",
    response_model=RevertActionResponse,
    summary="Execute state rollback for a reversible action",
)
async def revert_snapshot(
    snapshot_id: str,
    payload: RevertActionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> RevertActionResponse:
    ip_addr = request.client.host if request.client else None
    try:
        reverted = await _snapshot_manager.revert_action(
            db=db,
            snapshot_id=snapshot_id,
            user_id=current_user.id,
            force=payload.force,
            ip_address=ip_addr,
        )
    except StateConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return RevertActionResponse(
        snapshot_id=reverted.id,
        status=reverted.status,
        message=f"Action '{snapshot_id}' was successfully reverted to pre-state.",
        target_path=reverted.target_path,
        reverted_at=reverted.reverted_at or reverted.created_at,
    )
