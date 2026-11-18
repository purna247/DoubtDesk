"""Database ownership guards for long-running, checkpointed jobs."""
import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import event, select, text
from app.modules.jobs.models import BackgroundJob


class LeaseLost(RuntimeError):
    """The current worker must stop without committing further output."""


def install_job_fence(db, job_id, worker_id):
    """Check and lock the persisted lease before EVERY handler commit, before flush.

    The row lock lasts through commit, closing the ownership check/write race.
    It is not held during provider calls. A terminal transition permits only
    read-only commits afterward (some handlers use a final empty commit).
    """
    finished = False

    def before_commit(session):
        nonlocal finished
        if finished:
            if session.new or session.dirty or session.deleted:
                raise LeaseLost("Job no longer owns a running lease.")
            return
        row = session.connection().execute(select(
            BackgroundJob.status, BackgroundJob.lease_owner, BackgroundJob.lease_expires_at,
        ).where(BackgroundJob.id == job_id).with_for_update()).first()
        now = datetime.now(timezone.utc)
        expiry = row.lease_expires_at if row else None
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if not row or row.status != 'running' or row.lease_owner != worker_id or not expiry or expiry <= now:
            raise LeaseLost("Job lease expired or was reassigned.")
        job = session.get(BackgroundJob, job_id)
        finished = job.status != 'running' or job.lease_owner != worker_id

    event.listen(db.sync_session, 'before_commit', before_commit)
    return lambda: event.remove(db.sync_session, 'before_commit', before_commit)


@asynccontextmanager
async def course_execution_lock(db, offering_id: uuid.UUID):
    async with course_execution_locks(db,[offering_id]) as acquired:
        yield acquired


@asynccontextmanager
async def course_execution_locks(db, offering_ids):
    """Session advisory lock survives checkpoint commits; separate connection.

    PostgreSQL releases it on disconnect, including worker process death.
    SQLite is only used by isolated unit tests and does not emulate this lock.
    """
    if db.bind.dialect.name != 'postgresql':
        yield True
        return
    keys=[int.from_bytes(hashlib.sha256(f'academic:{offering_id}'.encode()).digest()[:8], 'big', signed=True) for offering_id in sorted(set(offering_ids),key=str)]
    async with db.bind.connect() as connection:
        held=[]
        try:
            for key in keys:
                if not await connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key':key}):
                    yield False
                    return
                held.append(key)
            await connection.commit()
            yield True
        finally:
            for key in reversed(held):
                await connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key':key})
            if held:
                await connection.commit()
