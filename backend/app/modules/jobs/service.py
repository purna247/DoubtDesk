import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.jobs.models import BackgroundJob, BackgroundJobEvent


class JobService:
    """PostgreSQL-backed durable job queue with transactional claiming and lease recovery."""

    @staticmethod
    async def enqueue_job(
        db: AsyncSession,
        job_type: str,
        target_entity_type: str,
        target_entity_id: Optional[uuid.UUID] = None,
        input_reference_json: Optional[dict] = None,
        institution_id: Optional[uuid.UUID] = None,
        requested_by_user_id: Optional[uuid.UUID] = None,
        scope_course_offering_id: Optional[uuid.UUID] = None,
        max_attempts: int = 3,
    ) -> BackgroundJob:
        now = datetime.now(timezone.utc)
        job = BackgroundJob(
            id=uuid.uuid4(),
            institution_id=institution_id,
            requested_by_user_id=requested_by_user_id,
            job_type=job_type,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            scope_course_offering_id=scope_course_offering_id,
            status="queued",
            current_stage="queued",
            progress_percent=0.0,
            attempt_count=0,
            max_attempts=max_attempts,
            input_reference_json=input_reference_json or {},
            created_at=now,
            updated_at=now,
        )
        db.add(job)

        event = BackgroundJobEvent(
            id=uuid.uuid4(),
            job_id=job.id,
            event_type="job_enqueued",
            stage_name="queued",
            progress_percent=0.0,
            message_safe="Job submitted to durable processing queue.",
            details_json=input_reference_json or {},
            created_at=now,
        )
        db.add(event)

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def claim_next_job(
        db: AsyncSession,
        worker_id: str,
        lease_duration_seconds: int = 300,
    ) -> Optional[BackgroundJob]:
        """
        Claim the next pending job atomically.
        Uses FOR UPDATE SKIP LOCKED on PostgreSQL; simple lock on SQLite.
        """
        now = datetime.now(timezone.utc)

        stmt = select(BackgroundJob).where(
            or_(
                BackgroundJob.status == "queued",
                and_(
                    BackgroundJob.status == "retrying",
                    or_(BackgroundJob.next_retry_at.is_(None), BackgroundJob.next_retry_at <= now),
                ),
            )
        ).order_by(BackgroundJob.created_at.asc()).limit(1)

        # Check dialect for SKIP LOCKED support
        is_sqlite = db.bind and db.bind.dialect.name == "sqlite"
        if not is_sqlite:
            stmt = stmt.with_for_update(skip_locked=True)

        res = await db.execute(stmt)
        job = res.scalars().first()

        if not job:
            return None

        # Acquire lease
        job.status = "running"
        job.attempt_count += 1
        job.lease_owner = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_duration_seconds)
        if not job.started_at:
            job.started_at = now
        job.updated_at = now

        db.add(
            BackgroundJobEvent(
                id=uuid.uuid4(),
                job_id=job.id,
                event_type="lease_acquired",
                stage_name=job.current_stage,
                progress_percent=job.progress_percent,
                message_safe=f"Job claimed by worker lease owner: {worker_id}",
                created_at=now,
            )
        )
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def recover_expired_leases(db: AsyncSession) -> int:
        """
        Recover stalled or orphaned jobs whose lease expired (e.g. worker process crashed).
        Re-queues them if attempt_count < max_attempts; marks failed if exhausted.
        """
        now = datetime.now(timezone.utc)

        stmt = select(BackgroundJob).where(
            and_(
                BackgroundJob.status == "running",
                BackgroundJob.lease_expires_at.is_not(None),
                BackgroundJob.lease_expires_at < now,
            )
        )
        res = await db.execute(stmt)
        expired_jobs = res.scalars().all()
        recovered_count = 0

        for job in expired_jobs:
            if job.attempt_count < job.max_attempts:
                job.status = "retrying"
                job.next_retry_at = now
                job.lease_owner = None
                job.lease_expires_at = None
                job.updated_at = now

                db.add(
                    BackgroundJobEvent(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        event_type="lease_recovered",
                        stage_name=job.current_stage,
                        progress_percent=job.progress_percent,
                        message_safe="Expired worker lease detected. Job recovered and scheduled for retry.",
                        created_at=now,
                    )
                )
            else:
                job.status = "failed"
                job.error_code = "LEASE_TIMEOUT_EXHAUSTED"
                job.safe_error_summary = "Worker lease expired and max retry attempts were exceeded."
                job.completed_at = now
                job.updated_at = now

                db.add(
                    BackgroundJobEvent(
                        id=uuid.uuid4(),
                        job_id=job.id,
                        event_type="error",
                        stage_name=job.current_stage,
                        progress_percent=job.progress_percent,
                        message_safe="Job failed permanently due to lease timeout exhaustion.",
                        created_at=now,
                    )
                )
            recovered_count += 1

        if recovered_count > 0:
            await db.commit()
        return recovered_count

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        job_id: uuid.UUID,
        stage: str,
        progress_percent: float,
        message_safe: str,
        details_json: Optional[dict] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        job = await db.get(BackgroundJob, job_id)
        if not job:
            return

        job.current_stage = stage
        job.progress_percent = progress_percent
        job.updated_at = now

        db.add(
            BackgroundJobEvent(
                id=uuid.uuid4(),
                job_id=job.id,
                event_type="progress_updated",
                stage_name=stage,
                progress_percent=progress_percent,
                message_safe=message_safe,
                details_json=details_json or {},
                created_at=now,
            )
        )
        await db.commit()

    @staticmethod
    async def complete_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        result_reference_json: Optional[dict] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        job = await db.get(BackgroundJob, job_id)
        if not job:
            return

        job.status = "succeeded"
        job.progress_percent = 100.0
        job.current_stage = "completed"
        job.completed_at = now
        job.result_reference_json = result_reference_json or {}
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now

        db.add(
            BackgroundJobEvent(
                id=uuid.uuid4(),
                job_id=job.id,
                event_type="completed",
                stage_name="completed",
                progress_percent=100.0,
                message_safe="Job execution completed successfully.",
                details_json=result_reference_json or {},
                created_at=now,
            )
        )
        await db.commit()

    @staticmethod
    async def fail_job(
        db: AsyncSession,
        job_id: uuid.UUID,
        error_code: str,
        safe_error_summary: str,
        retry: bool = True,
    ) -> None:
        now = datetime.now(timezone.utc)
        job = await db.get(BackgroundJob, job_id)
        if not job:
            return

        can_retry = retry and (job.attempt_count < job.max_attempts)
        job.error_code = error_code
        job.safe_error_summary = safe_error_summary
        job.updated_at = now

        if can_retry:
            job.status = "retrying"
            job.next_retry_at = now + timedelta(seconds=30)
            job.lease_owner = None
            job.lease_expires_at = None
        else:
            job.status = "failed"
            job.completed_at = now
            job.lease_owner = None
            job.lease_expires_at = None

        db.add(
            BackgroundJobEvent(
                id=uuid.uuid4(),
                job_id=job.id,
                event_type="error",
                stage_name=job.current_stage,
                progress_percent=job.progress_percent,
                message_safe=safe_error_summary,
                details_json={"error_code": error_code, "retry_scheduled": can_retry},
                created_at=now,
            )
        )
        await db.commit()

    @staticmethod
    async def get_job_status(
        db: AsyncSession, job_id: uuid.UUID
    ) -> Optional[BackgroundJob]:
        stmt = (
            select(BackgroundJob)
            .where(BackgroundJob.id == job_id)
            .options(selectinload(BackgroundJob.events))
        )
        res = await db.execute(stmt)
        return res.scalars().first()
