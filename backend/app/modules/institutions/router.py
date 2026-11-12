from __future__ import annotations
import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import require_super_admin, get_current_user
from app.modules.auth.schemas import UserProfile
from app.modules.institutions.service import InstitutionService
from app.modules.institutions.schemas import InstitutionCreate, InstitutionOut

router = APIRouter(prefix="/institutions", tags=["Institutions & Multi-Tenancy"])


@router.get("", response_model=List[InstitutionOut])
async def list_institutions(
    db: AsyncSession = Depends(get_db),
    _current_user: UserProfile = Depends(require_super_admin),
):
    """Super Admin: list all registered universities."""
    return await InstitutionService.list_institutions(db)


@router.post("", response_model=InstitutionOut, status_code=status.HTTP_201_CREATED)
async def create_institution(
    req: InstitutionCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: UserProfile = Depends(require_super_admin),
):
    """Super Admin: provision a new university tenant."""
    return await InstitutionService.create_institution(db, req)


@router.get("/{institution_id}", response_model=InstitutionOut)
async def get_institution(
    institution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Retrieve details for a single institution."""
    if current_user.role != "SUPER_ADMIN":
        if not current_user.institution_id or uuid.UUID(current_user.institution_id) != institution_id:
            raise AppException(status_code=403, code="ACCESS_FORBIDDEN", message="Unauthorized tenant access.")

    return await InstitutionService.get_institution(db, institution_id)

