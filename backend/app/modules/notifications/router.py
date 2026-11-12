from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.rbac.dependencies import get_current_user
from app.modules.auth.schemas import UserProfile
from app.modules.notifications.service import NotificationService
from app.modules.notifications.schemas import NotificationOut, UnreadCountOut

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])


@router.get("", response_model=List[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """List in-app notifications for the authenticated user."""
    return await NotificationService.list_user_notifications(
        db=db,
        user_id=uuid.UUID(current_user.id),
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Retrieve count of unread notifications for badge display."""
    count = await NotificationService.get_unread_count(
        db=db,
        user_id=uuid.UUID(current_user.id),
    )
    return UnreadCountOut(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Mark a notification as read."""
    return await NotificationService.mark_as_read(
        db=db,
        user_id=uuid.UUID(current_user.id),
        notification_id=notification_id,
    )


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Mark all inbox notifications as read."""
    updated = await NotificationService.mark_all_read(
        db=db,
        user_id=uuid.UUID(current_user.id),
    )
    return {"status": "ok", "marked_read_count": updated}

