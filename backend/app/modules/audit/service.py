from __future__ import annotations
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


class AuditService:

    @staticmethod
    async def list_audit_events(
        db: AsyncSession,
        institution_id: Optional[uuid.UUID] = None,
        event_code: Optional[str] = None,
        actor_user_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AuditEvent], int]:
        """
        List audit events with tenant-scoped filtering for Admins,
        or global visibility for Super Admins.
        """
        stmt = select(AuditEvent)
        count_stmt = select(func.count(AuditEvent.id))

        if institution_id is not None:
            stmt = stmt.where(AuditEvent.institution_id == institution_id)
            count_stmt = count_stmt.where(AuditEvent.institution_id == institution_id)

        if event_code:
            stmt = stmt.where(AuditEvent.event_code == event_code)
            count_stmt = count_stmt.where(AuditEvent.event_code == event_code)

        if actor_user_id:
            stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
            count_stmt = count_stmt.where(AuditEvent.actor_user_id == actor_user_id)

        if target_type:
            stmt = stmt.where(AuditEvent.target_type == target_type)
            count_stmt = count_stmt.where(AuditEvent.target_type == target_type)

        total_count = (await db.execute(count_stmt)).scalar_one() or 0
        events = list((await db.execute(stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit))).scalars().all())

        return events, total_count

