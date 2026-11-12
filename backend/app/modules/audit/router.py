from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import get_current_user
from app.modules.auth.schemas import UserProfile
from app.modules.audit.service import AuditService
from app.modules.audit.schemas import AuditQueryResponse, AuditEventOut

router = APIRouter(prefix="/admin/audit", tags=["Security Audit Trail"])


@router.get("", response_model=AuditQueryResponse)
async def list_audit_events(
    event_code: Optional[str] = Query(None),
    actor_user_id: Optional[uuid.UUID] = Query(None),
    target_type: Optional[str] = Query(None),
    institution_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Query immutable security audit logs.
    Super Admins can view platform-wide or filter by institution.
    Institution Admins are strictly scoped to their own institution.
    """
    if current_user.role not in ("SUPER_ADMIN", "ADMIN"):
        raise AppException(
            status_code=403,
            code="ACCESS_FORBIDDEN",
            message="Only administrators may inspect the audit trail.",
        )

    # Scoping
    scoped_inst_id: Optional[uuid.UUID] = None
    if current_user.role == "ADMIN":
        if not current_user.institution_id:
            raise AppException(status_code=400, code="NO_TENANT_CONTEXT", message="Tenant context required.")
        scoped_inst_id = uuid.UUID(current_user.institution_id)
    else:
        # Super Admin
        scoped_inst_id = institution_id

    events, total = await AuditService.list_audit_events(
        db=db,
        institution_id=scoped_inst_id,
        event_code=event_code,
        actor_user_id=actor_user_id,
        target_type=target_type,
        limit=limit,
        offset=offset,
    )

    return AuditQueryResponse(
        events=[AuditEventOut.model_validate(e) for e in events],
        total_count=total,
    )

