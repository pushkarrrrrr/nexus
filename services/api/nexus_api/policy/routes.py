"""NEXUS Policy Engine & Security REST API Endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.models import (
    ApprovalRequestModel,
    AuditLogModel,
    CapabilityModel,
    UserModel,
    UserPermissionModel,
)
from packages.shared.nexus_shared.policy import (
    CapabilityDefinition,
    PolicyEngine,
    PolicyManager,
    get_capability_registry,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db
from services.api.nexus_api.policy.schemas import (
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
    ApprovalResolutionRequest,
    ApprovalResolutionResponse,
    AuditLogListResponse,
    AuditLogResponse,
    CapabilityListResponse,
    CapabilityResponse,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    UserPermissionListResponse,
    UserPermissionResponse,
)

policy_router = APIRouter(prefix="/policy", tags=["policy"])
_policy_engine = PolicyEngine()
_policy_manager = PolicyManager()


@policy_router.get(
    "/capabilities",
    response_model=CapabilityListResponse,
    summary="List registered system capabilities and baseline risk tiers",
)
async def list_capabilities(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CapabilityListResponse:
    # Query database capabilities if available, fallback to in-memory registry
    stmt = select(CapabilityModel).order_by(CapabilityModel.name.asc())
    res = await db.execute(stmt)
    db_caps = res.scalars().all()

    if db_caps:
        items = [
            CapabilityResponse(
                id=c.id,
                name=c.name,
                category=c.category,
                default_risk_level=c.default_risk_level,
                description=c.description,
                is_active=c.is_active,
            )
            for c in db_caps
        ]
    else:
        reg = get_capability_registry()
        caps: list[CapabilityDefinition] = reg.list_all()
        items = [
            CapabilityResponse(
                id=f"cap_{c.name.replace('.', '_')}",
                name=c.name,
                category=c.category,
                default_risk_level=c.default_risk_level,
                description=c.description,
                is_active=c.is_active,
            )
            for c in caps
        ]

    return CapabilityListResponse(items=items, total=len(items))


@policy_router.get(
    "/permissions",
    response_model=UserPermissionListResponse,
    summary="List active user permissions and session grants",
)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> UserPermissionListResponse:
    now = datetime.now(UTC)
    stmt = (
        select(UserPermissionModel)
        .where(
            UserPermissionModel.user_id == current_user.id,
            or_(
                UserPermissionModel.expires_at.is_(None),
                UserPermissionModel.expires_at > now,
            ),
        )
        .order_by(UserPermissionModel.created_at.desc())
    )
    res = await db.execute(stmt)
    perms = res.scalars().all()

    items = [UserPermissionResponse.model_validate(p) for p in perms]
    return UserPermissionListResponse(items=items, total=len(items))


@policy_router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an active permission grant",
)
async def revoke_permission(
    permission_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    ip_addr = request.client.host if request.client else None
    revoked = await _policy_manager.revoke_permission(
        db=db,
        user_id=current_user.id,
        permission_id=permission_id,
        ip_address=ip_addr,
    )
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission grant '{permission_id}' not found.",
        )


@policy_router.get(
    "/approvals",
    response_model=ApprovalRequestListResponse,
    summary="List pending and historical approval requests",
)
async def list_approvals(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ApprovalRequestListResponse:
    # Auto-expire stale pending approvals prior to querying
    await _policy_manager.auto_expire_approvals(db)

    query = select(ApprovalRequestModel).where(ApprovalRequestModel.user_id == current_user.id)
    if status_filter:
        query = query.where(ApprovalRequestModel.status == status_filter.upper())

    count_stmt = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    query = query.order_by(ApprovalRequestModel.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(query)
    approvals = res.scalars().all()

    items = [ApprovalRequestResponse.model_validate(a) for a in approvals]
    return ApprovalRequestListResponse(items=items, total=total)


@policy_router.post(
    "/approvals/{approval_id}/resolve",
    response_model=ApprovalResolutionResponse,
    summary="Resolve a pending approval request",
)
async def resolve_approval(
    approval_id: str,
    payload: ApprovalResolutionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ApprovalResolutionResponse:
    ip_addr = request.client.host if request.client else None
    try:
        resolved = await _policy_manager.resolve_approval(
            db=db,
            user_id=current_user.id,
            approval_id=approval_id,
            decision=payload.decision,
            chosen_scope=payload.chosen_scope,
            session_ttl_minutes=payload.session_ttl_minutes,
            ip_address=ip_addr,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ApprovalResolutionResponse(
        approval=ApprovalRequestResponse.model_validate(resolved),
        message=f"Approval request '{approval_id}' successfully marked as {resolved.status}.",
    )


@policy_router.post(
    "/evaluate",
    response_model=PolicyEvaluateResponse,
    summary="Evaluate action against policy engine",
)
async def evaluate_action(
    payload: PolicyEvaluateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> PolicyEvaluateResponse:
    ip_addr = request.client.host if request.client else None
    decision = await _policy_engine.evaluate_action(
        db=db,
        user_id=current_user.id,
        capability_name=payload.capability_name,
        resource_target=payload.resource_target,
        params=payload.params,
        session_id=payload.session_id,
        ip_address=ip_addr,
        task_id=payload.task_id,
        step_id=payload.step_id,
    )
    return PolicyEvaluateResponse(
        verdict=decision.verdict,
        capability_name=decision.capability_name,
        risk_level=decision.risk_level,
        reason=decision.reason,
        approval_id=decision.approval_id,
        matching_permission_id=decision.matching_permission_id,
        affected_resource=decision.affected_resource,
        timestamp=decision.timestamp,
    )


@policy_router.get(
    "/audit",
    response_model=AuditLogListResponse,
    summary="Query immutable append-only audit ledger",
)
async def query_audit_logs(
    risk_level: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    event_type: str | None = Query(None),
    capability_name: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> AuditLogListResponse:
    query = select(AuditLogModel).where(AuditLogModel.user_id == current_user.id)

    if risk_level:
        query = query.where(AuditLogModel.risk_level == risk_level.upper())
    if status_filter:
        query = query.where(AuditLogModel.status == status_filter.upper())
    if event_type:
        query = query.where(AuditLogModel.event_type == event_type.upper())
    if capability_name:
        query = query.where(AuditLogModel.capability_name == capability_name)
    if start_date:
        query = query.where(AuditLogModel.created_at >= start_date)
    if end_date:
        query = query.where(AuditLogModel.created_at <= end_date)

    count_stmt = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    query = query.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(query)
    logs = res.scalars().all()

    items = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            session_id=log.session_id,
            step_id=log.step_id,
            agent_name=log.agent_name,
            tool_name=log.tool_name,
            action_type=log.action_type,
            risk_level=log.risk_level,
            event_type=log.event_type,
            capability_name=log.capability_name,
            status=log.status,
            policy_verdict=log.policy_verdict,
            details=log.details or {},
            ip_address=log.ip_address,
            created_at=log.created_at,
            timestamp=log.timestamp or log.created_at,
        )
        for log in logs
    ]

    return AuditLogListResponse(items=items, total=total)
