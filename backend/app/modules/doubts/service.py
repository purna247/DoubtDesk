from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.auth.models import (
    User,
    UserIdentifier,
    InstitutionMembership,
    InstitutionMembershipRole,
    PlatformRoleAssignment,
)
from app.modules.audit.models import AuditEvent
from app.modules.knowledge.models import Concept
from app.modules.doubts.models import (
    Doubt,
    DoubtAnswer,
    DoubtComment,
    DoubtVote,
    DoubtAnswerVote,
    DoubtFlag,
    DoubtIdentityDisclosureEvent,
)
from app.modules.doubts.schemas import (
    DoubtCreate,
    DoubtOut,
    AuthorPublicOut,
    DoubtAnswerCreate,
    DoubtAnswerOut,
    DoubtCommentCreate,
    DoubtCommentOut,
    DoubtFlagCreate,
    DoubtFlagOut,
    DoubtUnmaskRequest,
    DoubtUnmaskOut,
    InfluencePeriodStats,
    MyDoubtStatsOut,
)


class DoubtService:

    @staticmethod
    def _resolve_user_role_label(author_user: Optional[User]) -> str:
        if not author_user:
            return "User"

        # Check loaded platform_roles in __dict__ without triggering async IO
        platform_roles = author_user.__dict__.get("platform_roles")
        if platform_roles:
            for pr in platform_roles:
                if getattr(pr, "revoked_at", None) is None and getattr(pr, "role_code", "") == "super_admin":
                    return "Super Admin"

        # Check loaded institution_memberships in __dict__ without triggering async IO
        memberships = author_user.__dict__.get("institution_memberships")
        if memberships:
            for mem in memberships:
                if getattr(mem, "membership_status", "") == "active":
                    roles = mem.__dict__.get("roles")
                    if roles:
                        codes = [getattr(r, "role_code", "").lower() for r in roles if getattr(r, "revoked_at", None) is None]
                        if "teacher" in codes:
                            return "Teacher"
                        if "admin" in codes:
                            return "Admin"
                        if "student" in codes:
                            return "Student"

        # Check display_name for faculty title prefixes
        display_name = getattr(author_user, "display_name", "") or ""
        if any(display_name.strip().startswith(prefix) for prefix in ("Dr.", "Prof.", "Dr ", "Prof ")):
            return "Teacher"

        return "Student"

    @staticmethod
    def _build_author_out(
        author_user: Optional[User],
        is_anonymous_to_peers: bool,
        caller_user_id: uuid.UUID,
        caller_role: str,
        was_unmasked: bool = False,
    ) -> AuthorPublicOut:
        """
        Build public author representation respecting peer-anonymity safeguards.
        Omits author identity from peers when is_anonymous_to_peers=True.
        """
        if not author_user:
            return AuthorPublicOut(
                user_id=None,
                display_name="Unknown Author",
                role_label="User",
                is_anonymous=False,
            )

        is_owner = (author_user.id == caller_user_id)
        is_admin_or_unmasked = (caller_role in ("ADMIN", "SUPER_ADMIN") and was_unmasked)

        if is_anonymous_to_peers and not is_owner and not is_admin_or_unmasked:
            return AuthorPublicOut(
                user_id=None,
                display_name="Anonymous Student",
                avatar_url=None,
                role_label="Student",
                is_anonymous=True,
            )

        role_label = DoubtService._resolve_user_role_label(author_user)

        return AuthorPublicOut(
            user_id=author_user.id,
            display_name=author_user.display_name,
            avatar_url=None,
            role_label=role_label,
            is_anonymous=is_anonymous_to_peers,
        )

    @staticmethod
    def _serialize_answer(
        ans: DoubtAnswer,
        caller_user_id: uuid.UUID,
        caller_role: str,
    ) -> DoubtAnswerOut:
        ans_author = DoubtService._build_author_out(
            ans.author,
            False,
            caller_user_id,
            caller_role,
        )
        comments_out: List[DoubtCommentOut] = []
        for c in (ans.comments or []):
            if c.status == "published":
                c_author = DoubtService._build_author_out(
                    c.author,
                    False,
                    caller_user_id,
                    caller_role,
                )
                comments_out.append(
                    DoubtCommentOut(
                        id=c.id,
                        doubt_id=c.doubt_id,
                        answer_id=c.answer_id,
                        author=c_author,
                        body_markdown=c.body_markdown,
                        created_at=c.created_at,
                    )
                )
        votes_loaded = ans.__dict__.get("votes") or []
        has_thanked = any(
            getattr(v, "user_id", None) == caller_user_id and getattr(v, "vote_type", "thanks") == "thanks"
            for v in votes_loaded
        )
        return DoubtAnswerOut(
            id=ans.id,
            doubt_id=ans.doubt_id,
            author=ans_author,
            body_markdown=ans.body_markdown,
            is_teacher_verified=ans.is_teacher_verified,
            verified_at=ans.verified_at,
            upvote_count=ans.upvote_count,
            has_thanked=has_thanked,
            created_at=ans.created_at,
            comments=comments_out,
        )

    @staticmethod
    def _serialize_comment(
        c: DoubtComment,
        caller_user_id: uuid.UUID,
        caller_role: str,
    ) -> DoubtCommentOut:
        c_author = DoubtService._build_author_out(
            c.author,
            False,
            caller_user_id,
            caller_role,
        )
        return DoubtCommentOut(
            id=c.id,
            doubt_id=c.doubt_id,
            answer_id=c.answer_id,
            author=c_author,
            body_markdown=c.body_markdown,
            created_at=c.created_at,
        )

    @staticmethod
    def _serialize_doubt(
        doubt: Doubt,
        caller_user_id: uuid.UUID,
        caller_role: str,
    ) -> DoubtOut:
        """Serialize a doubt into DoubtOut, applying anonymity masking on the thread and its comments."""
        author_out = DoubtService._build_author_out(
            doubt.author,
            doubt.is_anonymous_to_peers,
            caller_user_id,
            caller_role,
        )

        answers_out: List[DoubtAnswerOut] = [
            DoubtService._serialize_answer(ans, caller_user_id, caller_role)
            for ans in (doubt.answers or [])
            if ans.status == "published"
        ]

        root_comments_out: List[DoubtCommentOut] = [
            DoubtService._serialize_comment(c, caller_user_id, caller_role)
            for c in (doubt.comments or [])
            if c.answer_id is None and c.status == "published"
        ]

        return DoubtOut(
            id=doubt.id,
            institution_id=doubt.institution_id,
            course_offering_id=doubt.course_offering_id,
            canonical_subject_id=doubt.canonical_subject_id,
            concept_id=doubt.concept_id,
            concept_name=doubt.concept.canonical_name if doubt.concept else None,
            title=doubt.title,
            body_markdown=doubt.body_markdown,
            is_anonymous_to_peers=doubt.is_anonymous_to_peers,
            author=author_out,
            status=doubt.status,
            visibility=doubt.visibility,
            upvote_count=doubt.upvote_count,
            answer_count=doubt.answer_count,
            created_at=doubt.created_at,
            updated_at=doubt.updated_at,
            answers=answers_out,
            comments=root_comments_out,
        )

    @staticmethod
    async def create_doubt(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        req: DoubtCreate,
    ) -> Doubt:
        """Create a new doubt thread. Anonymous authors remain recorded in backend for safety."""
        doubt = Doubt(
            institution_id=tenant_id,
            author_user_id=user_id,
            course_offering_id=req.course_offering_id,
            canonical_subject_id=req.canonical_subject_id,
            concept_id=req.concept_id,
            question_id=req.question_id,
            title=req.title,
            body_markdown=req.body_markdown,
            is_anonymous_to_peers=req.is_anonymous_to_peers,
            status="open",
            visibility=req.visibility,
        )
        db.add(doubt)
        await db.commit()
        await db.refresh(doubt)
        return doubt

    @staticmethod
    async def get_doubt_detail(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        caller_user_id: uuid.UUID,
        caller_role: str,
    ) -> DoubtOut:
        """Fetch doubt detail with strict privacy safeguards."""
        stmt = (
            select(Doubt)
            .options(
                selectinload(Doubt.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(Doubt.author).selectinload(User.platform_roles),
                selectinload(Doubt.concept),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.author).selectinload(User.platform_roles),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.comments).selectinload(DoubtComment.author),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.votes),
                selectinload(Doubt.comments).selectinload(DoubtComment.author),
            )
            .where(
                Doubt.id == doubt_id,
                Doubt.institution_id == tenant_id,
            )
        )
        res = await db.execute(stmt)
        doubt = res.scalars().first()
        if not doubt or doubt.status == "removed":
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        return DoubtService._serialize_doubt(doubt, caller_user_id, caller_role)

    @staticmethod
    async def list_doubts(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        caller_user_id: uuid.UUID,
        caller_role: str,
        course_offering_id: Optional[uuid.UUID] = None,
        concept_id: Optional[uuid.UUID] = None,
    ) -> List[DoubtOut]:
        """List campus/course doubts respecting privacy safeguards."""
        stmt = (
            select(Doubt)
            .options(
                selectinload(Doubt.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(Doubt.author).selectinload(User.platform_roles),
                selectinload(Doubt.concept),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.author).selectinload(User.platform_roles),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.comments).selectinload(DoubtComment.author),
                selectinload(Doubt.answers).selectinload(DoubtAnswer.votes),
                selectinload(Doubt.comments).selectinload(DoubtComment.author),
            )
            .where(
                Doubt.institution_id == tenant_id,
                Doubt.status != "removed",
            )
        )
        if course_offering_id:
            stmt = stmt.where(
                or_(
                    Doubt.course_offering_id == course_offering_id,
                    Doubt.visibility == "institution",
                )
            )
        if concept_id:
            stmt = stmt.where(Doubt.concept_id == concept_id)

        stmt = stmt.order_by(Doubt.created_at.desc())
        items = (await db.execute(stmt)).scalars().all()
        return [DoubtService._serialize_doubt(d, caller_user_id, caller_role) for d in items]

    @staticmethod
    async def add_answer(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        user_id: uuid.UUID,
        req: DoubtAnswerCreate,
        caller_role: str = "STUDENT",
    ) -> DoubtAnswerOut:
        """Add peer or teacher response to a doubt."""
        doubt = (await db.execute(select(Doubt).where(Doubt.id == doubt_id, Doubt.institution_id == tenant_id))).scalars().first()
        if not doubt or doubt.status == "removed":
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        now = datetime.now(timezone.utc)
        is_faculty = caller_role in ("TEACHER", "ADMIN", "SUPER_ADMIN")
        ans = DoubtAnswer(
            institution_id=tenant_id,
            doubt_id=doubt_id,
            author_user_id=user_id,
            body_markdown=req.body_markdown,
            is_teacher_verified=is_faculty,
            verified_by_user_id=user_id if is_faculty else None,
            verified_at=now if is_faculty else None,
            status="published",
        )
        db.add(ans)
        doubt.answer_count += 1
        if doubt.status in ("open", "answered"):
            doubt.status = "resolved" if is_faculty else "answered"
        doubt.updated_at = now

        await db.commit()
        stmt = (
            select(DoubtAnswer)
            .options(
                selectinload(DoubtAnswer.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(DoubtAnswer.author).selectinload(User.platform_roles),
                selectinload(DoubtAnswer.comments).selectinload(DoubtComment.author),
                selectinload(DoubtAnswer.votes),
            )
            .where(DoubtAnswer.id == ans.id)
        )
        loaded = (await db.execute(stmt)).scalars().first()
        return DoubtService._serialize_answer(loaded, user_id, caller_role)

    @staticmethod
    async def verify_answer(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        answer_id: uuid.UUID,
        user_id: uuid.UUID,
        caller_role: str = "TEACHER",
    ) -> DoubtAnswerOut:
        """Instructor endorses/verifies an answer as academically correct."""
        stmt = (
            select(DoubtAnswer)
            .options(
                selectinload(DoubtAnswer.doubt),
                selectinload(DoubtAnswer.author).selectinload(User.institution_memberships).selectinload(InstitutionMembership.roles),
                selectinload(DoubtAnswer.author).selectinload(User.platform_roles),
                selectinload(DoubtAnswer.comments).selectinload(DoubtComment.author),
                selectinload(DoubtAnswer.votes),
            )
            .where(DoubtAnswer.id == answer_id, DoubtAnswer.institution_id == tenant_id)
        )
        ans = (await db.execute(stmt)).scalars().first()
        if not ans:
            raise AppException(status_code=404, code="ANSWER_NOT_FOUND", message="Answer not found.")

        now = datetime.now(timezone.utc)
        ans.is_teacher_verified = True
        ans.verified_by_user_id = user_id
        ans.verified_at = now
        ans.updated_at = now

        # Mark parent doubt resolved
        if ans.doubt:
            ans.doubt.status = "resolved"
            ans.doubt.updated_at = now

        await db.commit()
        return DoubtService._serialize_answer(ans, user_id, caller_role)

    @staticmethod
    async def add_comment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        user_id: uuid.UUID,
        req: DoubtCommentCreate,
        caller_role: str = "STUDENT",
    ) -> DoubtCommentOut:
        """Post a comment on a doubt or answer."""
        doubt = (await db.execute(select(Doubt).where(Doubt.id == doubt_id, Doubt.institution_id == tenant_id))).scalars().first()
        if not doubt or doubt.status == "removed":
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        c = DoubtComment(
            institution_id=tenant_id,
            doubt_id=doubt_id,
            answer_id=req.answer_id,
            author_user_id=user_id,
            body_markdown=req.body_markdown,
            status="published",
        )
        db.add(c)
        doubt.updated_at = datetime.now(timezone.utc)
        await db.commit()

        stmt = select(DoubtComment).options(selectinload(DoubtComment.author)).where(DoubtComment.id == c.id)
        loaded = (await db.execute(stmt)).scalars().first()
        return DoubtService._serialize_comment(loaded, user_id, caller_role)

    @staticmethod
    async def vote_doubt(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Upvote a doubt thread. Idempotent: repeated upvotes are safely handled."""
        doubt = (await db.execute(select(Doubt).where(Doubt.id == doubt_id, Doubt.institution_id == tenant_id))).scalars().first()
        if not doubt:
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        vote_stmt = select(DoubtVote).where(
            DoubtVote.doubt_id == doubt_id,
            DoubtVote.user_id == user_id,
            DoubtVote.vote_type == "upvote",
        )
        existing_vote = (await db.execute(vote_stmt)).scalars().first()
        if not existing_vote:
            db.add(
                DoubtVote(
                    institution_id=tenant_id,
                    doubt_id=doubt_id,
                    user_id=user_id,
                    vote_type="upvote",
                )
            )
            doubt.upvote_count += 1
            await db.commit()

        return doubt.upvote_count

    @staticmethod
    async def thank_answer(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        answer_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Thank an answer once per user. Idempotent: repeated presses do not increment count."""
        ans = (
            await db.execute(
                select(DoubtAnswer).where(
                    DoubtAnswer.id == answer_id,
                    DoubtAnswer.institution_id == tenant_id,
                    DoubtAnswer.status == "published",
                )
            )
        ).scalars().first()
        if not ans:
            raise AppException(status_code=404, code="ANSWER_NOT_FOUND", message="Answer not found.")

        vote_stmt = select(DoubtAnswerVote).where(
            DoubtAnswerVote.answer_id == answer_id,
            DoubtAnswerVote.user_id == user_id,
            DoubtAnswerVote.vote_type == "thanks",
        )
        existing_vote = (await db.execute(vote_stmt)).scalars().first()
        if existing_vote:
            return {
                "answer_id": ans.id,
                "upvote_count": ans.upvote_count,
                "has_thanked": True,
                "already_thanked": True,
            }

        db.add(
            DoubtAnswerVote(
                institution_id=tenant_id,
                answer_id=answer_id,
                user_id=user_id,
                vote_type="thanks",
            )
        )
        ans.upvote_count += 1
        await db.commit()
        return {
            "answer_id": ans.id,
            "upvote_count": ans.upvote_count,
            "has_thanked": True,
            "already_thanked": False,
        }

    @staticmethod
    async def flag_doubt(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        user_id: uuid.UUID,
        req: DoubtFlagCreate,
    ) -> DoubtFlag:
        """Raise a moderation flag against a doubt."""
        doubt = (await db.execute(select(Doubt).where(Doubt.id == doubt_id, Doubt.institution_id == tenant_id))).scalars().first()
        if not doubt:
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        flag = DoubtFlag(
            institution_id=tenant_id,
            doubt_id=doubt_id,
            reported_by_user_id=user_id,
            reason_code=req.reason_code,
            details=req.details,
            status="open",
        )
        db.add(flag)
        await db.commit()
        await db.refresh(flag)
        return flag

    @staticmethod
    async def unmask_anonymous_author(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        doubt_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_role: str,
        req: DoubtUnmaskRequest,
    ) -> DoubtUnmaskOut:
        """
        Audited identity disclosure for anonymous doubt authors.
        Requires Admin or Super Admin role.
        Atomically records an AuditEvent and DoubtIdentityDisclosureEvent.
        """
        if actor_role not in ("ADMIN", "SUPER_ADMIN"):
            raise AppException(
                status_code=403,
                code="UNAUTHORIZED_UNMASKING",
                message="Only administrators may resolve anonymous author identity.",
            )

        stmt = select(Doubt).options(selectinload(Doubt.author)).where(Doubt.id == doubt_id, Doubt.institution_id == tenant_id)
        doubt = (await db.execute(stmt)).scalars().first()
        if not doubt:
            raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")

        if not doubt.is_anonymous_to_peers:
            raise AppException(
                status_code=400,
                code="DOUBT_NOT_ANONYMOUS",
                message="This doubt is not anonymous.",
            )

        now = datetime.now(timezone.utc)

        # 1. Create audit event
        audit = AuditEvent(
            institution_id=tenant_id,
            actor_user_id=actor_user_id,
            event_code="ANONYMOUS_IDENTITY_DISCLOSED",
            target_type="doubt",
            target_id=str(doubt_id),
            payload_json={
                "doubt_id": str(doubt_id),
                "author_user_id": str(doubt.author_user_id),
                "reason_code": req.reason_code,
                "reason_text": req.reason_text,
            },
        )
        db.add(audit)
        await db.flush()

        # 2. Create immutable disclosure event
        disc = DoubtIdentityDisclosureEvent(
            institution_id=tenant_id,
            doubt_id=doubt_id,
            author_user_id=doubt.author_user_id,
            actor_user_id=actor_user_id,
            reason_code=req.reason_code,
            reason_text=req.reason_text,
            policy_basis="moderation_investigation",
            disclosed_at=now,
            audit_event_id=audit.id,
        )
        db.add(disc)

        # 3. Retrieve author email if available
        id_stmt = select(UserIdentifier).where(
            UserIdentifier.user_id == doubt.author_user_id,
            UserIdentifier.identifier_type == "email",
        )
        ident = (await db.execute(id_stmt)).scalars().first()
        email_str = ident.identifier_value if ident else None

        await db.commit()

        return DoubtUnmaskOut(
            doubt_id=doubt.id,
            author_user_id=doubt.author_user_id,
            author_display_name=doubt.author.display_name,
            author_email=email_str,
            disclosed_at=now,
            audit_event_id=audit.id,
        )

    @staticmethod
    async def list_flags(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        status_filter: Optional[str] = None,
    ) -> List[DoubtFlag]:
        stmt = select(DoubtFlag).where(DoubtFlag.institution_id == tenant_id)
        if status_filter:
            stmt = stmt.where(DoubtFlag.status == status_filter)
        stmt = stmt.order_by(DoubtFlag.created_at.desc())
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def resolve_flag(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        flag_id: uuid.UUID,
        user_id: uuid.UUID,
        new_status: str,
    ) -> DoubtFlag:
        stmt = select(DoubtFlag).where(DoubtFlag.id == flag_id, DoubtFlag.institution_id == tenant_id)
        flag = (await db.execute(stmt)).scalars().first()
        if not flag:
            raise AppException(status_code=404, code="FLAG_NOT_FOUND", message="Flag not found.")
        now = datetime.now(timezone.utc)
        flag.status = new_status
        flag.resolved_by_user_id = user_id
        flag.resolved_at = now
        flag.updated_at = now
        await db.commit()
        await db.refresh(flag)
        return flag

    @staticmethod
    def _calc_delta_pct(current: int, previous: int) -> Optional[int]:
        if previous <= 0:
            return None
        return round(((current - previous) / previous) * 100)

    @staticmethod
    async def _compute_window_metrics(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        start_dt: Optional[datetime],
        end_dt: Optional[datetime],
    ) -> Dict[str, int]:
        # 1. Best answers: teacher-verified answers authored by user_id
        best_filters = [
            DoubtAnswer.institution_id == tenant_id,
            DoubtAnswer.author_user_id == user_id,
            DoubtAnswer.status == "published",
            DoubtAnswer.is_teacher_verified.is_(True),
        ]
        if start_dt is not None:
            best_filters.append(func.coalesce(DoubtAnswer.verified_at, DoubtAnswer.created_at) >= start_dt)
        if end_dt is not None:
            best_filters.append(func.coalesce(DoubtAnswer.verified_at, DoubtAnswer.created_at) < end_dt)
        best_answers = int(
            (await db.execute(select(func.count(DoubtAnswer.id)).where(*best_filters))).scalar() or 0
        )

        # 2. Thanks / appreciations: answer upvotes received + peer doubt votes received
        ans_upvote_filters = [
            DoubtAnswer.institution_id == tenant_id,
            DoubtAnswer.author_user_id == user_id,
            DoubtAnswer.status == "published",
        ]
        if start_dt is not None:
            ans_upvote_filters.append(DoubtAnswer.created_at >= start_dt)
        if end_dt is not None:
            ans_upvote_filters.append(DoubtAnswer.created_at < end_dt)
        answer_upvotes = int(
            (await db.execute(select(func.coalesce(func.sum(DoubtAnswer.upvote_count), 0)).where(*ans_upvote_filters))).scalar()
            or 0
        )

        vote_filters = [
            Doubt.institution_id == tenant_id,
            Doubt.author_user_id == user_id,
            Doubt.status.notin_(["removed", "archived"]),
            DoubtVote.user_id != user_id,
        ]
        if start_dt is not None:
            vote_filters.append(DoubtVote.created_at >= start_dt)
        if end_dt is not None:
            vote_filters.append(DoubtVote.created_at < end_dt)
        doubt_voter_rows = (
            await db.execute(
                select(DoubtVote.user_id).join(Doubt, Doubt.id == DoubtVote.doubt_id).where(*vote_filters)
            )
        ).scalars().all()
        thanks = answer_upvotes + len(doubt_voter_rows)

        # 3. Popularity: distinct peers interacting with user's doubts or answers
        ans_peer_filters = [
            Doubt.institution_id == tenant_id,
            Doubt.author_user_id == user_id,
            Doubt.status.notin_(["removed", "archived"]),
            DoubtAnswer.status == "published",
            DoubtAnswer.author_user_id != user_id,
        ]
        if start_dt is not None:
            ans_peer_filters.append(DoubtAnswer.created_at >= start_dt)
        if end_dt is not None:
            ans_peer_filters.append(DoubtAnswer.created_at < end_dt)
        ans_peers = (
            await db.execute(
                select(DoubtAnswer.author_user_id)
                .join(Doubt, Doubt.id == DoubtAnswer.doubt_id)
                .where(*ans_peer_filters)
            )
        ).scalars().all()

        my_answer_ids_subq = select(DoubtAnswer.id).where(
            DoubtAnswer.institution_id == tenant_id,
            DoubtAnswer.author_user_id == user_id,
        )
        my_doubt_ids_subq = select(Doubt.id).where(
            Doubt.institution_id == tenant_id,
            Doubt.author_user_id == user_id,
            Doubt.status.notin_(["removed", "archived"]),
        )
        comment_filters = [
            DoubtComment.institution_id == tenant_id,
            DoubtComment.status == "published",
            DoubtComment.author_user_id != user_id,
            or_(
                DoubtComment.doubt_id.in_(my_doubt_ids_subq),
                DoubtComment.answer_id.in_(my_answer_ids_subq),
            ),
        ]
        if start_dt is not None:
            comment_filters.append(DoubtComment.created_at >= start_dt)
        if end_dt is not None:
            comment_filters.append(DoubtComment.created_at < end_dt)
        comment_peers = (await db.execute(select(DoubtComment.author_user_id).where(*comment_filters))).scalars().all()

        distinct_peers = set(doubt_voter_rows) | set(ans_peers) | set(comment_peers)
        return {
            "popularity": len(distinct_peers),
            "best_answers": best_answers,
            "thanks": thanks,
        }

    @staticmethod
    async def get_my_stats(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MyDoubtStatsOut:
        asked_count = int(
            (
                await db.execute(
                    select(func.count(Doubt.id)).where(
                        Doubt.institution_id == tenant_id,
                        Doubt.author_user_id == user_id,
                        Doubt.status.notin_(["removed", "archived"]),
                    )
                )
            ).scalar()
            or 0
        )
        answered_count = int(
            (
                await db.execute(
                    select(func.count(DoubtAnswer.id)).where(
                        DoubtAnswer.institution_id == tenant_id,
                        DoubtAnswer.author_user_id == user_id,
                        DoubtAnswer.status == "published",
                    )
                )
            ).scalar()
            or 0
        )

        now = datetime.now(timezone.utc)
        w7 = now - timedelta(days=7)
        w14 = now - timedelta(days=14)

        curr_7 = await DoubtService._compute_window_metrics(db, tenant_id, user_id, w7, None)
        prev_7 = await DoubtService._compute_window_metrics(db, tenant_id, user_id, w14, w7)
        overall = await DoubtService._compute_window_metrics(db, tenant_id, user_id, None, None)

        return MyDoubtStatsOut(
            asked_count=asked_count,
            answered_count=answered_count,
            verified_answers_count=overall["best_answers"],
            thanks_count=overall["thanks"],
            last_7_days=InfluencePeriodStats(
                popularity=curr_7["popularity"],
                popularity_delta_pct=DoubtService._calc_delta_pct(curr_7["popularity"], prev_7["popularity"]),
                best_answers=curr_7["best_answers"],
                best_answers_delta_pct=DoubtService._calc_delta_pct(curr_7["best_answers"], prev_7["best_answers"]),
                thanks=curr_7["thanks"],
                thanks_delta_pct=DoubtService._calc_delta_pct(curr_7["thanks"], prev_7["thanks"]),
            ),
            overall=InfluencePeriodStats(
                popularity=overall["popularity"],
                best_answers=overall["best_answers"],
                thanks=overall["thanks"],
            ),
        )
