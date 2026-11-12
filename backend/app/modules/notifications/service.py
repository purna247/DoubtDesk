from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AppException
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import NotificationCreate, NotificationOut, UnreadCountOut


class NotificationService:

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        req: NotificationCreate,
    ) -> Notification:
        """
        Record a targeted in-app notification.
        Safeguard: Notification title and message must never leak anonymous doubt author identity.
        """
        notif = Notification(
            institution_id=req.institution_id,
            user_id=req.user_id,
            actor_user_id=req.actor_user_id,
            notification_type=req.notification_type,
            title=req.title,
            message=req.message,
            target_type=req.target_type,
            target_id=req.target_id,
            is_read=False,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)
        return notif

    @staticmethod
    async def list_user_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Fetch notification inbox for the recipient."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Return count of unread notifications for recipient."""
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        res = await db.execute(stmt)
        return res.scalar_one() or 0

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification:
        """Mark single notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        notif = (await db.execute(stmt)).scalars().first()
        if not notif:
            raise AppException(status_code=404, code="NOTIFICATION_NOT_FOUND", message="Notification not found.")

        if not notif.is_read:
            notif.is_read = True
            notif.read_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(notif)

        return notif

    @staticmethod
    async def mark_all_read(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Mark all unread notifications for recipient as read."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=now)
        )
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount

