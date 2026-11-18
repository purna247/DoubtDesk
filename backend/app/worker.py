import asyncio
import argparse
import logging
import os
import signal
import socket
import uuid
from contextlib import suppress
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.database import async_session_factory, engine
import app.model_registry  # noqa: F401 - register all ORM models before worker queries
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.service import JobService
from app.modules.jobs.execution import install_job_fence, LeaseLost
from app.modules.sources.service import SourceService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("doubtdesk.worker")
settings = get_settings()

_running = True


async def maintain_worker_health(session_factory, worker_id):
    while True:
        try:
            async with session_factory() as db:
                await JobService.heartbeat(db, worker_id)
        except Exception as exc:
            logger.error("Worker heartbeat failed with %s.", type(exc).__name__)
        await asyncio.sleep(10)


async def maintain_job_lease(session_factory, job_id, worker_id, owner_task, lost):
    interval=max(0.1,min(10,settings.WORKER_JOB_LEASE_SECONDS/3))
    while True:
        await asyncio.sleep(interval)
        try:
            async with session_factory() as db:
                if await JobService.renew_lease(db,job_id,worker_id,settings.WORKER_JOB_LEASE_SECONDS):
                    continue
                job=await db.get(BackgroundJob,job_id)
                if job and job.status != "running":
                    return
        except Exception as exc:
            logger.error("Job lease renewal failed with %s.",type(exc).__name__)
        lost.set()
        owner_task.cancel()
        return
def handle_shutdown_signal(signum: int, _frame: Any) -> None:
    global _running
    logger.info("Received termination signal (%s); stopping after the current job.", signum)
    _running = False


async def process_next_job(
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    worker_id: str | None = None,
    job_id: uuid.UUID | None = None,
) -> bool:
    """Recover expired leases, claim one job, and run its registered handler."""
    worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    async with session_factory() as db:
        await JobService.recover_expired_leases(db,job_id=job_id)
        job = await JobService.claim_next_job(
            db,
            worker_id=worker_id,
            lease_duration_seconds=settings.WORKER_JOB_LEASE_SECONDS,
            job_id=job_id,
        )
        if job is None:
            return False

        job_id = job.id
        job_type = job.job_type
        logger.info("Claimed background job %s (%s).", job_id, job_type)
        remove_fence=install_job_fence(db,job_id,worker_id)
        lost=asyncio.Event()
        lease_task=asyncio.create_task(maintain_job_lease(session_factory,job_id,worker_id,asyncio.current_task(),lost))

        try:
            if job_type == "extract_source_document":
                result = await SourceService.process_extraction_job(db, job_id)
                logger.info(
                    "Extraction handler returned for job %s: job_status=%s source_outcome=%s chunks=%s assets=%s warnings=%s.",
                    job_id,
                    job.status,
                    result.status,
                    len(result.chunks),
                    len(result.assets),
                    len(result.warnings),
                )
            else:
                await JobService.fail_job(
                    db,
                    job_id,
                    error_code="UNSUPPORTED_JOB_TYPE",
                    safe_error_summary="No worker handler is registered for this job type.",
                    retry=False,
                )
                logger.error("Job %s has unsupported type %s.", job_id, job_type)
        except asyncio.CancelledError:
            await db.rollback()
            if not lost.is_set():
                raise
            logger.error("Stopped job %s after losing its lease.",job_id)
        except LeaseLost:
            await db.rollback()
            logger.error("Discarded stale worker output for job %s.",job_id)
        except Exception as exc:
            # Do not log driver/parser exception text; it can contain secrets or uploaded data.
            await db.rollback()
            current_job = await db.get(BackgroundJob, job_id)
            if current_job and current_job.status == "running" and current_job.lease_owner == worker_id:
                await JobService.fail_job(
                    db,
                    job_id,
                    error_code="JOB_PROCESSING_ERROR",
                    safe_error_summary="An unexpected processing error occurred. The job will be retried when possible.",
                    retry=True,
                )
            logger.error(
                "Background job %s failed with %s.",
                job_id,
                type(exc).__name__,
            )
        finally:
            lease_task.cancel()
            with suppress(asyncio.CancelledError):
                await lease_task
            remove_fence()

        return True


async def run_worker(job_id: uuid.UUID | None = None) -> int:
    """Continuously poll and execute durable jobs until a shutdown signal arrives."""
    global _running
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    logger.info(
        "Worker started in %s mode (poll=%ss, lease=%ss).",
        settings.APP_ENV,
        settings.WORKER_POLL_INTERVAL_SECONDS,
        settings.WORKER_JOB_LEASE_SECONDS,
    )

    health_task=asyncio.create_task(maintain_worker_health(async_session_factory,worker_id))
    try:
        while _running:
            try:
                processed = await process_next_job(worker_id=worker_id,job_id=job_id)
                if job_id is not None:
                    if not processed:
                        logger.warning("Requested job %s is not currently claimable; no other job was processed.",job_id)
                        return 1
                    async with async_session_factory() as db:
                        finished=await db.get(BackgroundJob,job_id)
                        return 0 if finished and finished.status=="succeeded" else 1
                if not processed and _running:
                    await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Worker poll failed with %s; retrying.", type(exc).__name__)
                if job_id is not None:
                    return 1
                if _running:
                    await asyncio.sleep(max(settings.WORKER_POLL_INTERVAL_SECONDS, 1.0))
    finally:
        health_task.cancel()
        with suppress(asyncio.CancelledError):
            await health_task
        try:
            from sqlalchemy import delete
            from app.modules.jobs.models import WorkerHeartbeat
            async with async_session_factory() as db:
                await db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.worker_id==worker_id))
                await db.commit()
        except Exception as exc:
            logger.warning("Worker heartbeat cleanup failed with %s.",type(exc).__name__)
        logger.info("Cleaning up worker database connections.")
        await engine.dispose()
        logger.info("Background worker stopped.")
    return 0


def main() -> None:
    parser=argparse.ArgumentParser(description="Run the ingestion worker or one specific queued job.")
    parser.add_argument("--job-id",type=uuid.UUID,help="Process only this job once, then exit; never claim another job.")
    args=parser.parse_args()
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    try:
        raise SystemExit(asyncio.run(run_worker(job_id=args.job_id)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
