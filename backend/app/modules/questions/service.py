from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.questions.models import (
    Question,
    QuestionVersion,
    QuestionPart,
    QuestionPartOption,
    QuestionPartConceptAllocation,
    QuestionVersionLearningObjective,
    QuestionVersionSource,
    QuestionRelationship,
    QuestionCoverageEvent,
    Misconception,
)
from app.modules.questions.schemas import (
    QuestionCreate,
    QuestionVersionCreate,
    QuestionReviewRequest,
    QuestionRelationshipCreate,
    CourseQuestionCoverageReport,
    QuestionOut,
    QuestionVersionOut,
    QuestionPartOut,
    OptionOut,
    ConceptAllocationOut,
    MisconceptionCreate,
)
from app.modules.knowledge.models import Concept


class QuestionService:

    @staticmethod
    async def list_course_questions(
        db: AsyncSession, offering_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> List[QuestionOut]:
        """Return persisted question records connected to this course's review history."""
        question_ids = select(QuestionCoverageEvent.question_id).where(
            QuestionCoverageEvent.course_offering_id == offering_id,
            QuestionCoverageEvent.institution_id == tenant_id,
        ).distinct()
        ids_stmt = (
            select(Question.id)
            .where(Question.institution_id == tenant_id, Question.id.in_(question_ids))
            .order_by(Question.created_at.desc())
        )
        ids = (await db.execute(ids_stmt)).scalars().all()
        return [await QuestionService.get_question(db, question_id, tenant_id) for question_id in ids]

    @staticmethod
    async def create_misconception(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        req: MisconceptionCreate,
    ) -> Misconception:
        misc = Misconception(
            institution_id=tenant_id,
            concept_id=req.concept_id,
            code=req.code,
            label=req.label,
            description=req.description,
        )
        db.add(misc)
        await db.commit()
        await db.refresh(misc)
        return misc

    @staticmethod
    async def create_question(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: QuestionCreate,
    ) -> Question:
        v_data = data.version

        # 1. Validate version parts sum
        if v_data.parts:
            parts_sum = sum(p.marks_available for p in v_data.parts)
            if round(parts_sum, 2) != round(v_data.marks_total, 2):
                raise AppException(
                    status_code=400,
                    code="MARKS_MISMATCH",
                    message=f"Sum of part marks ({parts_sum}) must equal question marks total ({v_data.marks_total})",
                )
            for part in v_data.parts:
                if part.concept_allocations:
                    alloc_sum = sum(a.allocated_marks for a in part.concept_allocations)
                    if round(alloc_sum, 2) != round(part.marks_available, 2):
                        raise AppException(
                            status_code=400,
                            code="CONCEPT_ALLOCATION_MISMATCH",
                            message=f"Sum of concept allocations ({alloc_sum}) must equal part marks ({part.marks_available})",
                        )

        # 2. Create parent Question
        question = Question(
            institution_id=tenant_id,
            created_by_user_id=user_id,
            origin_type=data.origin_type,
            lifecycle_status="draft",
            is_ai_generated=data.is_ai_generated,
        )
        db.add(question)
        await db.flush()

        # 3. Create QuestionVersion 1
        version = QuestionVersion(
            institution_id=tenant_id,
            question_id=question.id,
            version_number=1,
            prompt_text=v_data.prompt_text,
            question_type=v_data.question_type,
            command_verb=v_data.command_verb,
            expected_answer_depth=v_data.expected_answer_depth,
            marks_total=v_data.marks_total,
            difficulty_level=v_data.difficulty_level,
            cognitive_level=v_data.cognitive_level,
            approval_status="draft",
            created_by_user_id=user_id,
            marking_guidance=v_data.marking_guidance,
        )
        db.add(version)
        await db.flush()

        has_concept_mapping = False

        # 4. Create Parts, Options, and Concept Allocations
        if not v_data.parts:
            # Default single part if none supplied
            part = QuestionPart(
                institution_id=tenant_id,
                question_version_id=version.id,
                part_key="A",
                part_prompt=v_data.prompt_text,
                sequence_no=1,
                marks_available=v_data.marks_total,
                answer_type=v_data.question_type,
            )
            db.add(part)
        else:
            for part_in in v_data.parts:
                part = QuestionPart(
                    institution_id=tenant_id,
                    question_version_id=version.id,
                    part_key=part_in.part_key,
                    part_prompt=part_in.part_prompt,
                    sequence_no=part_in.sequence_no,
                    marks_available=part_in.marks_available,
                    answer_type=part_in.answer_type,
                    expected_answer_depth=part_in.expected_answer_depth,
                )
                db.add(part)
                await db.flush()

                for opt_in in part_in.options:
                    opt = QuestionPartOption(
                        institution_id=tenant_id,
                        question_part_id=part.id,
                        option_key=opt_in.option_key,
                        display_text=opt_in.display_text,
                        sequence_no=opt_in.sequence_no,
                        is_correct=opt_in.is_correct,
                        misconception_id=opt_in.misconception_id,
                    )
                    db.add(opt)

                for alloc_in in part_in.concept_allocations:
                    has_concept_mapping = True
                    concept = await db.get(Concept, alloc_in.concept_id)
                    if not concept or concept.institution_id != tenant_id:
                        raise AppException(
                            status_code=400,
                            code="CONCEPT_NOT_FOUND",
                            message=f"Concept {alloc_in.concept_id} not found in this institution.",
                        )
                    alloc = QuestionPartConceptAllocation(
                        institution_id=tenant_id,
                        question_part_id=part.id,
                        concept_id=alloc_in.concept_id,
                        allocated_marks=alloc_in.allocated_marks,
                        allocation_note=alloc_in.allocation_note,
                    )
                    db.add(alloc)

        # 5. Learning Objectives
        for lo_id in v_data.learning_objective_ids:
            db.add(
                QuestionVersionLearningObjective(
                    institution_id=tenant_id,
                    question_version_id=version.id,
                    learning_objective_id=lo_id,
                )
            )

        # 6. Source provenance
        if v_data.source_chunk_id:
            db.add(
                QuestionVersionSource(
                    institution_id=tenant_id,
                    question_version_id=version.id,
                    source_chunk_id=v_data.source_chunk_id,
                    reference_role="origin",
                )
            )

        # 7. Coverage events if linked to an offering
        if data.course_offering_id:
            db.add(
                QuestionCoverageEvent(
                    institution_id=tenant_id,
                    course_offering_id=data.course_offering_id,
                    question_id=question.id,
                    question_version_id=version.id,
                    event_type="extracted" if data.origin_type == "original_exam" else "classified",
                    actor_user_id=user_id,
                )
            )
            if has_concept_mapping:
                db.add(
                    QuestionCoverageEvent(
                        institution_id=tenant_id,
                        course_offering_id=data.course_offering_id,
                        question_id=question.id,
                        question_version_id=version.id,
                        event_type="concept_mapped",
                        actor_user_id=user_id,
                    )
                )

        await db.commit()
        await db.refresh(question)
        return question

    @staticmethod
    async def create_question_version(
        db: AsyncSession,
        question_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: QuestionVersionCreate,
    ) -> QuestionVersion:
        question = await db.get(Question, question_id)
        if not question or question.institution_id != tenant_id:
            raise AppException(status_code=404, code="QUESTION_NOT_FOUND", message="Question not found.")

        # Validate parts sum
        if data.parts:
            parts_sum = sum(p.marks_available for p in data.parts)
            if round(parts_sum, 2) != round(data.marks_total, 2):
                raise AppException(status_code=400, code="MARKS_MISMATCH", message="Part marks sum mismatch.")
            for part in data.parts:
                if part.concept_allocations:
                    alloc_sum = sum(a.allocated_marks for a in part.concept_allocations)
                    if round(alloc_sum, 2) != round(part.marks_available, 2):
                        raise AppException(status_code=400, code="CONCEPT_ALLOCATION_MISMATCH", message="Allocations mismatch.")

        v_stmt = select(func.max(QuestionVersion.version_number)).where(
            QuestionVersion.question_id == question_id
        )
        current_max = (await db.execute(v_stmt)).scalar() or 0

        new_version = QuestionVersion(
            institution_id=tenant_id,
            question_id=question_id,
            version_number=current_max + 1,
            prompt_text=data.prompt_text,
            question_type=data.question_type,
            command_verb=data.command_verb,
            expected_answer_depth=data.expected_answer_depth,
            marks_total=data.marks_total,
            difficulty_level=data.difficulty_level,
            cognitive_level=data.cognitive_level,
            approval_status="draft",
            created_by_user_id=user_id,
            marking_guidance=data.marking_guidance,
        )
        db.add(new_version)
        await db.flush()

        for part_in in data.parts:
            part = QuestionPart(
                institution_id=tenant_id,
                question_version_id=new_version.id,
                part_key=part_in.part_key,
                part_prompt=part_in.part_prompt,
                sequence_no=part_in.sequence_no,
                marks_available=part_in.marks_available,
                answer_type=part_in.answer_type,
                expected_answer_depth=part_in.expected_answer_depth,
            )
            db.add(part)
            await db.flush()

            for opt_in in part_in.options:
                opt = QuestionPartOption(
                    institution_id=tenant_id,
                    question_part_id=part.id,
                    option_key=opt_in.option_key,
                    display_text=opt_in.display_text,
                    sequence_no=opt_in.sequence_no,
                    is_correct=opt_in.is_correct,
                    misconception_id=opt_in.misconception_id,
                )
                db.add(opt)

            for alloc_in in part_in.concept_allocations:
                alloc = QuestionPartConceptAllocation(
                    institution_id=tenant_id,
                    question_part_id=part.id,
                    concept_id=alloc_in.concept_id,
                    allocated_marks=alloc_in.allocated_marks,
                    allocation_note=alloc_in.allocation_note,
                )
                db.add(alloc)

        await db.commit()
        await db.refresh(new_version)
        return new_version

    @staticmethod
    async def review_question_version(
        db: AsyncSession,
        version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: QuestionReviewRequest,
        course_offering_id: Optional[uuid.UUID] = None,
    ) -> QuestionVersion:
        stmt = (
            select(QuestionVersion)
            .options(
                selectinload(QuestionVersion.parts).selectinload(QuestionPart.concept_allocations),
                selectinload(QuestionVersion.question),
            )
            .where(
                QuestionVersion.id == version_id,
                QuestionVersion.institution_id == tenant_id,
            )
        )
        res = await db.execute(stmt)
        version = res.scalars().first()
        if not version:
            raise AppException(status_code=404, code="VERSION_NOT_FOUND", message="Question version not found.")

        now = datetime.now(timezone.utc)

        if data.approval_status == "approved":
            # Strict academic validation before approval:
            # 1. Total marks match sum of parts
            parts = version.parts
            if not parts:
                raise AppException(
                    status_code=400,
                    code="EMPTY_QUESTION_PARTS",
                    message="Cannot approve question version with no question parts.",
                )
            parts_sum = sum(float(p.marks_available) for p in parts)
            if round(parts_sum, 2) != round(float(version.marks_total), 2):
                raise AppException(
                    status_code=400,
                    code="MARKS_MISMATCH",
                    message=f"Sum of parts ({parts_sum}) does not equal total marks ({version.marks_total}).",
                )

            # 2. For any parts with concept allocations, sum must equal part marks
            for p in parts:
                if p.concept_allocations:
                    alloc_sum = sum(float(a.allocated_marks) for a in p.concept_allocations)
                    if round(alloc_sum, 2) != round(float(p.marks_available), 2):
                        raise AppException(
                            status_code=400,
                            code="CONCEPT_ALLOCATION_MISMATCH",
                            message=f"Concept allocation sum ({alloc_sum}) does not match part marks ({p.marks_available}) for part {p.part_key}.",
                        )

            version.approval_status = "approved"
            version.reviewed_by_user_id = user_id
            version.reviewed_at = now
            version.question.lifecycle_status = "approved"

            if course_offering_id:
                db.add(
                    QuestionCoverageEvent(
                        institution_id=tenant_id,
                        course_offering_id=course_offering_id,
                        question_id=version.question_id,
                        question_version_id=version.id,
                        event_type="teacher_approved",
                        actor_user_id=user_id,
                    )
                )

        elif data.approval_status == "rejected":
            version.approval_status = "rejected"
            version.reviewed_by_user_id = user_id
            version.reviewed_at = now
            version.rejection_reason = data.rejection_reason
            version.question.lifecycle_status = "rejected"

        await db.commit()
        await db.refresh(version)
        return version

    @staticmethod
    async def create_relationship(
        db: AsyncSession,
        source_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: QuestionRelationshipCreate,
    ) -> QuestionRelationship:
        if source_id == data.target_question_id:
            raise AppException(status_code=400, code="SELF_RELATIONSHIP", message="A question cannot relate to itself.")

        source = await db.get(Question, source_id)
        target = await db.get(Question, data.target_question_id)
        if not source or source.institution_id != tenant_id or not target or target.institution_id != tenant_id:
            raise AppException(status_code=404, code="QUESTION_NOT_FOUND", message="Question not found in institution.")

        rel = QuestionRelationship(
            institution_id=tenant_id,
            source_question_id=source_id,
            target_question_id=data.target_question_id,
            relationship_type=data.relationship_type,
            confidence=data.confidence,
            review_status="teacher_approved",
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
        )
        db.add(rel)
        await db.commit()
        await db.refresh(rel)
        return rel

    @staticmethod
    async def get_question(
        db: AsyncSession,
        question_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> QuestionOut:
        stmt = (
            select(Question)
            .where(Question.id == question_id, Question.institution_id == tenant_id)
        )
        res = await db.execute(stmt)
        question = res.scalars().first()
        if not question:
            raise AppException(status_code=404, code="QUESTION_NOT_FOUND", message="Question not found.")

        # Fetch latest version
        v_stmt = (
            select(QuestionVersion)
            .options(
                selectinload(QuestionVersion.parts).selectinload(QuestionPart.options),
                selectinload(QuestionVersion.parts).selectinload(QuestionPart.concept_allocations),
                selectinload(QuestionVersion.source_links),
            )
            .where(QuestionVersion.question_id == question_id)
            .order_by(QuestionVersion.version_number.desc())
            .limit(1)
        )
        v_res = await db.execute(v_stmt)
        latest_v = v_res.scalars().first()

        latest_out = None
        if latest_v:
            parts_out = []
            for p in latest_v.parts:
                opts_out = [
                    OptionOut(
                        id=o.id,
                        option_key=o.option_key,
                        display_text=o.display_text,
                        sequence_no=o.sequence_no,
                        is_correct=o.is_correct,
                        misconception_id=o.misconception_id,
                    )
                    for o in p.options
                ]
                allocs_out = [
                    ConceptAllocationOut(
                        id=a.id,
                        question_part_id=a.question_part_id,
                        concept_id=a.concept_id,
                        allocated_marks=float(a.allocated_marks),
                        allocation_note=a.allocation_note,
                    )
                    for a in p.concept_allocations
                ]
                parts_out.append(
                    QuestionPartOut(
                        id=p.id,
                        part_key=p.part_key,
                        part_prompt=p.part_prompt,
                        sequence_no=p.sequence_no,
                        marks_available=float(p.marks_available),
                        answer_type=p.answer_type,
                        expected_answer_depth=p.expected_answer_depth,
                        options=opts_out,
                        concept_allocations=allocs_out,
                    )
                )

            latest_out = QuestionVersionOut(
                id=latest_v.id,
                institution_id=latest_v.institution_id,
                question_id=latest_v.question_id,
                version_number=latest_v.version_number,
                prompt_text=latest_v.prompt_text,
                question_type=latest_v.question_type,
                command_verb=latest_v.command_verb,
                expected_answer_depth=latest_v.expected_answer_depth,
                marks_total=float(latest_v.marks_total),
                difficulty_level=latest_v.difficulty_level,
                cognitive_level=latest_v.cognitive_level,
                approval_status=latest_v.approval_status,
                created_by_user_id=latest_v.created_by_user_id,
                reviewed_by_user_id=latest_v.reviewed_by_user_id,
                reviewed_at=latest_v.reviewed_at,
                rejection_reason=latest_v.rejection_reason,
                marking_guidance=latest_v.marking_guidance,
                source_chunk_ids=[link.source_chunk_id for link in latest_v.source_links if link.source_chunk_id],
                created_at=latest_v.created_at,
                parts=parts_out,
            )

        return QuestionOut(
            id=question.id,
            institution_id=question.institution_id,
            created_by_user_id=question.created_by_user_id,
            origin_type=question.origin_type,
            lifecycle_status=question.lifecycle_status,
            is_ai_generated=question.is_ai_generated,
            created_at=question.created_at,
            updated_at=question.updated_at,
            latest_version=latest_out,
        )

    @staticmethod
    async def get_course_coverage(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> CourseQuestionCoverageReport:
        stmt = select(QuestionCoverageEvent).where(
            QuestionCoverageEvent.course_offering_id == offering_id,
            QuestionCoverageEvent.institution_id == tenant_id,
        )
        events = (await db.execute(stmt)).scalars().all()

        distinct_questions = set(e.question_id for e in events)
        extracted = set(e.question_id for e in events if e.event_type == "extracted")
        concept_mapped = set(e.question_id for e in events if e.event_type == "concept_mapped")
        approved = set(e.question_id for e in events if e.event_type == "teacher_approved")
        assessment_included = set(e.question_id for e in events if e.event_type == "included_in_assessment")

        return CourseQuestionCoverageReport(
            course_offering_id=offering_id,
            total_questions=len(distinct_questions),
            extracted_count=len(extracted),
            concept_mapped_count=len(concept_mapped),
            approved_count=len(approved),
            assessment_included_count=len(assessment_included),
        )

