from __future__ import annotations
import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.exceptions import AppException
from app.modules.institutions.models import Institution, InstitutionSettings
from app.modules.institutions.schemas import InstitutionCreate


class InstitutionService:

    @staticmethod
    async def create_institution(
        db: AsyncSession,
        req: InstitutionCreate,
    ) -> Institution:
        """Super Admin provisions a new university tenant."""
        code_stmt = select(Institution).where(Institution.institution_code == req.institution_code.strip().upper())
        existing = (await db.execute(code_stmt)).scalars().first()
        if existing:
            raise AppException(
                status_code=400,
                code="INSTITUTION_CODE_EXISTS",
                message=f"Institution code '{req.institution_code}' is already registered.",
            )

        inst = Institution(
            institution_code=req.institution_code.strip().upper(),
            legal_name=req.legal_name.strip(),
            display_name=req.display_name.strip(),
            primary_domain=req.primary_domain.strip().lower() if req.primary_domain else None,
            status="active",
            timezone=req.timezone,
        )
        db.add(inst)
        await db.flush()

        settings = InstitutionSettings(
            institution_id=inst.id,
            allow_teacher_view_anonymous=False,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(inst)
        return inst

    @staticmethod
    async def list_institutions(
        db: AsyncSession,
    ) -> List[Institution]:
        """List all institutions (Super Admin view)."""
        stmt = select(Institution).order_by(Institution.display_name.asc())
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_institution(
        db: AsyncSession,
        institution_id: uuid.UUID,
    ) -> Institution:
        """Fetch single institution details."""
        stmt = select(Institution).where(Institution.id == institution_id)
        inst = (await db.execute(stmt)).scalars().first()
        if not inst:
            raise AppException(status_code=404, code="INSTITUTION_NOT_FOUND", message="Institution not found.")
        return inst
