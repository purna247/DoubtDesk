import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException, AuthorizationError
from app.modules.academics.models import (
    AcademicUnit,
    DegreeProgramme,
    ProgrammeBranch,
    CurriculumVersion,
    AcademicYear,
    AcademicTerm,
    SubjectCategory,
    CanonicalSubject,
    CurriculumSubjectEntry,
    CurriculumSubjectMarkComponent,
    CourseOffering,
    CourseOfferingFaculty,
    CourseOfferingEnrolment,
    StudentProgrammeEnrolment,
)
from app.modules.auth.models import (
    InstitutionMembership,
    InstitutionMembershipRole,
    User,
    UserIdentifier,
)
from app.modules.academics.schemas import (
    AcademicUnitCreate,
    DegreeProgrammeCreate,
    ProgrammeBranchCreate,
    CurriculumVersionCreate,
    AcademicYearCreate,
    AcademicTermCreate,
    SubjectCategoryCreate,
    CanonicalSubjectCreate,
    CurriculumSubjectEntryCreate,
    CourseOfferingCreate,
    AssignFacultyRequest,
    EnrolStudentRequest,
    BulkEnrolStudentsRequest,
)


class AcademicService:
    """Core academic hierarchy, canonical catalog, curriculum, offerings, and enrolments."""

    # --------------------------------------------------------------------------
    # Academic Units
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_academic_unit(
        db: AsyncSession, institution_id: uuid.UUID, data: AcademicUnitCreate
    ) -> AcademicUnit:
        parent_id = uuid.UUID(data.parent_unit_id) if data.parent_unit_id else None

        if parent_id:
            parent = await db.get(AcademicUnit, parent_id)
            if not parent or parent.institution_id != institution_id:
                raise AppException(
                    code="INVALID_PARENT_UNIT",
                    message="Parent academic unit does not exist in this institution.",
                    status_code=400,
                )

        # Check unique code within institution
        if data.code:
            existing_stmt = select(AcademicUnit).where(
                and_(AcademicUnit.institution_id == institution_id, AcademicUnit.code == data.code)
            )
            res = await db.execute(existing_stmt)
            if res.scalars().first():
                raise AppException(
                    code="DUPLICATE_UNIT_CODE",
                    message=f"Academic unit with code '{data.code}' already exists.",
                    status_code=400,
                )

        unit = AcademicUnit(
            id=uuid.uuid4(),
            institution_id=institution_id,
            parent_unit_id=parent_id,
            unit_type=data.unit_type,
            code=data.code,
            name=data.name,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
        )
        db.add(unit)
        await db.commit()
        await db.refresh(unit)
        return unit

    @staticmethod
    async def list_academic_units(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[AcademicUnit]:
        stmt = select(AcademicUnit).where(AcademicUnit.institution_id == institution_id).order_by(AcademicUnit.name)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Degree Programmes & Branches
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_degree_programme(
        db: AsyncSession, institution_id: uuid.UUID, data: DegreeProgrammeCreate
    ) -> DegreeProgramme:
        owning_unit_id = uuid.UUID(data.owning_academic_unit_id) if data.owning_academic_unit_id else None
        if owning_unit_id:
            unit = await db.get(AcademicUnit, owning_unit_id)
            if not unit or unit.institution_id != institution_id:
                raise AppException(
                    code="INVALID_ACADEMIC_UNIT",
                    message="Owning academic unit does not belong to this institution.",
                    status_code=400,
                )

        existing_stmt = select(DegreeProgramme).where(
            and_(DegreeProgramme.institution_id == institution_id, DegreeProgramme.code == data.code)
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_PROGRAMME_CODE",
                message=f"Programme with code '{data.code}' already exists.",
                status_code=400,
            )

        prog = DegreeProgramme(
            id=uuid.uuid4(),
            institution_id=institution_id,
            code=data.code,
            name=data.name,
            degree_level=data.degree_level,
            nominal_duration_years=data.nominal_duration_years,
            owning_academic_unit_id=owning_unit_id,
        )
        db.add(prog)
        await db.commit()
        await db.refresh(prog)
        return prog

    @staticmethod
    async def list_degree_programmes(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[DegreeProgramme]:
        stmt = select(DegreeProgramme).where(DegreeProgramme.institution_id == institution_id).order_by(DegreeProgramme.code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_programme_branch(
        db: AsyncSession, institution_id: uuid.UUID, programme_id: uuid.UUID, data: ProgrammeBranchCreate
    ) -> ProgrammeBranch:
        prog = await db.get(DegreeProgramme, programme_id)
        if not prog or prog.institution_id != institution_id:
            raise AppException(
                code="PROGRAMME_NOT_FOUND",
                message="Degree programme not found in this institution.",
                status_code=404,
            )

        existing_stmt = select(ProgrammeBranch).where(
            and_(
                ProgrammeBranch.institution_id == institution_id,
                ProgrammeBranch.degree_programme_id == programme_id,
                ProgrammeBranch.code == data.code,
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_BRANCH_CODE",
                message=f"Branch with code '{data.code}' already exists in this programme.",
                status_code=400,
            )

        branch = ProgrammeBranch(
            id=uuid.uuid4(),
            institution_id=institution_id,
            degree_programme_id=programme_id,
            code=data.code,
            name=data.name,
        )
        db.add(branch)
        await db.commit()
        await db.refresh(branch)
        return branch

    @staticmethod
    async def list_programme_branches(
        db: AsyncSession, institution_id: uuid.UUID, programme_id: uuid.UUID
    ) -> List[ProgrammeBranch]:
        stmt = select(ProgrammeBranch).where(
            and_(
                ProgrammeBranch.institution_id == institution_id,
                ProgrammeBranch.degree_programme_id == programme_id,
            )
        ).order_by(ProgrammeBranch.code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Curriculum Versions
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_curriculum_version(
        db: AsyncSession, institution_id: uuid.UUID, data: CurriculumVersionCreate
    ) -> CurriculumVersion:
        prog_id = uuid.UUID(data.degree_programme_id)
        prog = await db.get(DegreeProgramme, prog_id)
        if not prog or prog.institution_id != institution_id:
            raise AppException(
                code="PROGRAMME_NOT_FOUND",
                message="Degree programme not found in this institution.",
                status_code=404,
            )

        branch_id = uuid.UUID(data.programme_branch_id) if data.programme_branch_id else None
        if branch_id:
            branch = await db.get(ProgrammeBranch, branch_id)
            if not branch or branch.degree_programme_id != prog_id or branch.institution_id != institution_id:
                raise AppException(
                    code="INVALID_BRANCH",
                    message="Programme branch does not belong to the selected degree programme.",
                    status_code=400,
                )

        ver = CurriculumVersion(
            id=uuid.uuid4(),
            institution_id=institution_id,
            degree_programme_id=prog_id,
            programme_branch_id=branch_id,
            version_code=data.version_code,
            display_name=data.display_name,
            effective_from_admission_year=data.effective_from_admission_year,
            effective_to_admission_year=data.effective_to_admission_year,
            status="active",
        )
        db.add(ver)
        await db.commit()
        await db.refresh(ver)
        return ver

    @staticmethod
    async def list_curriculum_versions(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[CurriculumVersion]:
        stmt = select(CurriculumVersion).where(CurriculumVersion.institution_id == institution_id).order_by(CurriculumVersion.version_code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Academic Years & Terms
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_academic_year(
        db: AsyncSession, institution_id: uuid.UUID, data: AcademicYearCreate
    ) -> AcademicYear:
        if data.ends_on < data.starts_on:
            raise AppException(
                code="INVALID_DATES",
                message="Academic year end date must be on or after start date.",
                status_code=400,
            )

        existing_stmt = select(AcademicYear).where(
            and_(AcademicYear.institution_id == institution_id, AcademicYear.code == data.code)
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_ACADEMIC_YEAR",
                message=f"Academic year with code '{data.code}' already exists.",
                status_code=400,
            )

        year = AcademicYear(
            id=uuid.uuid4(),
            institution_id=institution_id,
            code=data.code,
            display_name=data.display_name,
            starts_on=data.starts_on,
            ends_on=data.ends_on,
            status="active",
        )
        db.add(year)
        await db.commit()
        await db.refresh(year)
        return year

    @staticmethod
    async def create_academic_term(
        db: AsyncSession, institution_id: uuid.UUID, data: AcademicTermCreate
    ) -> AcademicTerm:
        year_id = uuid.UUID(data.academic_year_id)
        year = await db.get(AcademicYear, year_id)
        if not year or year.institution_id != institution_id:
            raise AppException(
                code="YEAR_NOT_FOUND",
                message="Academic year not found in this institution.",
                status_code=404,
            )

        if data.ends_on < data.starts_on:
            raise AppException(
                code="INVALID_DATES",
                message="Term end date must be on or after start date.",
                status_code=400,
            )

        existing_stmt = select(AcademicTerm).where(
            and_(
                AcademicTerm.institution_id == institution_id,
                AcademicTerm.academic_year_id == year_id,
                AcademicTerm.term_code == data.term_code,
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_TERM",
                message=f"Term code '{data.term_code}' already exists in this academic year.",
                status_code=400,
            )

        term = AcademicTerm(
            id=uuid.uuid4(),
            institution_id=institution_id,
            academic_year_id=year_id,
            term_code=data.term_code,
            display_name=data.display_name,
            term_sequence=data.term_sequence,
            starts_on=data.starts_on,
            ends_on=data.ends_on,
            status="active",
        )
        db.add(term)
        await db.commit()
        await db.refresh(term)
        return term

    @staticmethod
    async def list_academic_terms(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[AcademicTerm]:
        stmt = select(AcademicTerm).where(AcademicTerm.institution_id == institution_id).order_by(AcademicTerm.starts_on.desc())
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Subject Categories
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_subject_category(
        db: AsyncSession, institution_id: uuid.UUID, data: SubjectCategoryCreate
    ) -> SubjectCategory:
        existing_stmt = select(SubjectCategory).where(
            and_(SubjectCategory.institution_id == institution_id, SubjectCategory.code == data.code)
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_CATEGORY",
                message=f"Category with code '{data.code}' already exists.",
                status_code=400,
            )

        cat = SubjectCategory(
            id=uuid.uuid4(),
            institution_id=institution_id,
            code=data.code,
            display_name=data.display_name,
            description=data.description,
            is_active=True,
        )
        db.add(cat)
        await db.commit()
        await db.refresh(cat)
        return cat

    @staticmethod
    async def list_subject_categories(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[SubjectCategory]:
        stmt = select(SubjectCategory).where(SubjectCategory.institution_id == institution_id).order_by(SubjectCategory.code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Canonical Subject Catalog (/admin/academic/subjects)
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_canonical_subject(
        db: AsyncSession, institution_id: uuid.UUID, data: CanonicalSubjectCreate
    ) -> CanonicalSubject:
        owning_unit_id = uuid.UUID(data.owning_academic_unit_id) if data.owning_academic_unit_id else None
        if owning_unit_id:
            unit = await db.get(AcademicUnit, owning_unit_id)
            if not unit or unit.institution_id != institution_id:
                raise AppException(
                    code="INVALID_ACADEMIC_UNIT",
                    message="Owning academic unit does not belong to this institution.",
                    status_code=400,
                )

        if data.canonical_code:
            existing_stmt = select(CanonicalSubject).where(
                and_(
                    CanonicalSubject.institution_id == institution_id,
                    CanonicalSubject.canonical_code == data.canonical_code,
                )
            )
            if (await db.execute(existing_stmt)).scalars().first():
                raise AppException(
                    code="DUPLICATE_CANONICAL_CODE",
                    message=f"Canonical subject with code '{data.canonical_code}' already exists.",
                    status_code=400,
                )

        subj = CanonicalSubject(
            id=uuid.uuid4(),
            institution_id=institution_id,
            owning_academic_unit_id=owning_unit_id,
            canonical_code=data.canonical_code,
            name=data.name,
            description=data.description,
            status="active",
        )
        db.add(subj)
        await db.commit()
        await db.refresh(subj)
        return subj

    @staticmethod
    async def list_canonical_subjects(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[CanonicalSubject]:
        stmt = select(CanonicalSubject).where(CanonicalSubject.institution_id == institution_id).order_by(CanonicalSubject.name)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Curriculum Subject Entries (/admin/curriculum/subjects)
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_curriculum_subject_entry(
        db: AsyncSession, institution_id: uuid.UUID, data: CurriculumSubjectEntryCreate
    ) -> CurriculumSubjectEntry:
        ver_id = uuid.UUID(data.curriculum_version_id)
        ver = await db.get(CurriculumVersion, ver_id)
        if not ver or ver.institution_id != institution_id:
            raise AppException(
                code="CURRICULUM_VERSION_NOT_FOUND",
                message="Curriculum version not found in this institution.",
                status_code=404,
            )

        canon_id = uuid.UUID(data.canonical_subject_id)
        canon = await db.get(CanonicalSubject, canon_id)
        if not canon or canon.institution_id != institution_id:
            raise AppException(
                code="CANONICAL_SUBJECT_NOT_FOUND",
                message="Canonical subject not found in this institution.",
                status_code=404,
            )

        cat_id = uuid.UUID(data.subject_category_id)
        cat = await db.get(SubjectCategory, cat_id)
        if not cat or cat.institution_id != institution_id:
            raise AppException(
                code="CATEGORY_NOT_FOUND",
                message="Subject category not found in this institution.",
                status_code=404,
            )

        resp_unit_id = uuid.UUID(data.responsible_academic_unit_id) if data.responsible_academic_unit_id else None
        if resp_unit_id:
            unit = await db.get(AcademicUnit, resp_unit_id)
            if not unit or unit.institution_id != institution_id:
                raise AppException(
                    code="INVALID_ACADEMIC_UNIT",
                    message="Responsible unit does not belong to this institution.",
                    status_code=400,
                )

        existing_stmt = select(CurriculumSubjectEntry).where(
            and_(
                CurriculumSubjectEntry.institution_id == institution_id,
                CurriculumSubjectEntry.curriculum_version_id == ver_id,
                CurriculumSubjectEntry.official_subject_code == data.official_subject_code,
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_OFFICIAL_CODE",
                message=f"Official subject code '{data.official_subject_code}' already exists in this curriculum version.",
                status_code=400,
            )

        marks_status = "configured" if data.mark_components else "not_configured"

        entry = CurriculumSubjectEntry(
            id=uuid.uuid4(),
            institution_id=institution_id,
            curriculum_version_id=ver_id,
            canonical_subject_id=canon_id,
            subject_category_id=cat_id,
            official_subject_code=data.official_subject_code,
            display_name_override=data.display_name_override,
            semester_number=data.semester_number,
            credits=data.credits,
            lecture_hours_per_week=data.lecture_hours_per_week,
            tutorial_hours_per_week=data.tutorial_hours_per_week,
            practical_hours_per_week=data.practical_hours_per_week,
            responsible_academic_unit_id=resp_unit_id,
            marks_scheme_status=marks_status,
            is_active=True,
        )
        db.add(entry)
        await db.flush()

        # Add mark components if provided
        if data.mark_components:
            for comp in data.mark_components:
                db.add(
                    CurriculumSubjectMarkComponent(
                        id=uuid.uuid4(),
                        institution_id=institution_id,
                        curriculum_subject_entry_id=entry.id,
                        component_code=comp.component_code,
                        display_name=comp.display_name,
                        assessment_kind=comp.assessment_kind,
                        maximum_marks=comp.maximum_marks,
                        weight_percent=comp.weight_percent,
                        sequence_no=comp.sequence_no,
                    )
                )

        await db.commit()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def list_curriculum_subject_entries(
        db: AsyncSession, institution_id: uuid.UUID, curriculum_version_id: Optional[uuid.UUID] = None
    ) -> List[CurriculumSubjectEntry]:
        stmt = (
            select(CurriculumSubjectEntry)
            .where(CurriculumSubjectEntry.institution_id == institution_id)
            .options(selectinload(CurriculumSubjectEntry.canonical_subject))
        )
        if curriculum_version_id:
            stmt = stmt.where(CurriculumSubjectEntry.curriculum_version_id == curriculum_version_id)
        stmt = stmt.order_by(CurriculumSubjectEntry.semester_number, CurriculumSubjectEntry.official_subject_code)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Course Offerings
    # --------------------------------------------------------------------------

    @staticmethod
    async def create_course_offering(
        db: AsyncSession, institution_id: uuid.UUID, data: CourseOfferingCreate
    ) -> CourseOffering:
        entry_id = uuid.UUID(data.curriculum_subject_entry_id)
        entry = await db.get(CurriculumSubjectEntry, entry_id)
        if not entry or entry.institution_id != institution_id:
            raise AppException(
                code="ENTRY_NOT_FOUND",
                message="Curriculum subject entry not found in this institution.",
                status_code=404,
            )

        term_id = uuid.UUID(data.academic_term_id)
        term = await db.get(AcademicTerm, term_id)
        if not term or term.institution_id != institution_id:
            raise AppException(
                code="TERM_NOT_FOUND",
                message="Academic term not found in this institution.",
                status_code=404,
            )

        delivering_unit_id = uuid.UUID(data.delivering_academic_unit_id)
        unit = await db.get(AcademicUnit, delivering_unit_id)
        if not unit or unit.institution_id != institution_id:
            raise AppException(
                code="UNIT_NOT_FOUND",
                message="Delivering academic unit not found in this institution.",
                status_code=404,
            )

        existing_stmt = select(CourseOffering).where(
            and_(
                CourseOffering.institution_id == institution_id,
                CourseOffering.curriculum_subject_entry_id == entry_id,
                CourseOffering.academic_term_id == term_id,
                CourseOffering.section_code == data.section_code,
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_OFFERING",
                message=f"Course offering for section '{data.section_code}' already exists for this subject and term.",
                status_code=400,
            )

        offering = CourseOffering(
            id=uuid.uuid4(),
            institution_id=institution_id,
            curriculum_subject_entry_id=entry_id,
            academic_term_id=term_id,
            delivering_academic_unit_id=delivering_unit_id,
            section_code=data.section_code,
            cohort_label=data.cohort_label,
            delivery_mode=data.delivery_mode,
            status="active",
        )
        db.add(offering)
        await db.commit()
        await db.refresh(offering)
        return offering

    @staticmethod
    async def list_course_offerings(
        db: AsyncSession, institution_id: uuid.UUID
    ) -> List[CourseOffering]:
        stmt = (
            select(CourseOffering)
            .where(CourseOffering.institution_id == institution_id)
            .options(
                selectinload(CourseOffering.curriculum_subject_entry).selectinload(CurriculumSubjectEntry.canonical_subject),
                selectinload(CourseOffering.academic_term),
                selectinload(CourseOffering.delivering_academic_unit),
            )
            .order_by(CourseOffering.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Faculty Assignment
    # --------------------------------------------------------------------------

    @staticmethod
    async def assign_faculty(
        db: AsyncSession,
        institution_id: uuid.UUID,
        offering_id: uuid.UUID,
        data: AssignFacultyRequest,
        assigned_by_user_id: Optional[uuid.UUID] = None,
    ) -> CourseOfferingFaculty:
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != institution_id:
            raise AppException(
                code="OFFERING_NOT_FOUND",
                message="Course offering not found in this institution.",
                status_code=404,
            )

        member_id = uuid.UUID(data.faculty_membership_id)
        member = await db.get(InstitutionMembership, member_id)
        if not member or member.institution_id != institution_id or member.membership_status != "active":
            raise AppException(
                code="FACULTY_NOT_FOUND",
                message="Faculty member not found or inactive in this institution.",
                status_code=404,
            )

        # Check existing assignment
        existing_stmt = select(CourseOfferingFaculty).where(
            and_(
                CourseOfferingFaculty.course_offering_id == offering_id,
                CourseOfferingFaculty.institution_membership_id == member_id,
                CourseOfferingFaculty.assignment_role == data.assignment_role,
                CourseOfferingFaculty.status == "active",
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_FACULTY_ASSIGNMENT",
                message="Faculty member is already actively assigned to this offering in this role.",
                status_code=400,
            )

        assignment = CourseOfferingFaculty(
            id=uuid.uuid4(),
            institution_id=institution_id,
            course_offering_id=offering_id,
            institution_membership_id=member_id,
            assignment_role=data.assignment_role,
            can_manage_content=data.can_manage_content,
            status="active",
            assigned_by_user_id=assigned_by_user_id,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)
        return assignment

    @staticmethod
    async def list_faculty_assignments(
        db: AsyncSession, offering_id: uuid.UUID
    ) -> List[CourseOfferingFaculty]:
        stmt = (
            select(CourseOfferingFaculty)
            .where(and_(CourseOfferingFaculty.course_offering_id == offering_id, CourseOfferingFaculty.status == "active"))
            .options(
                selectinload(CourseOfferingFaculty.membership).selectinload(InstitutionMembership.user),
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    # --------------------------------------------------------------------------
    # Student Enrolment (Admin-Managed Only)
    # --------------------------------------------------------------------------

    @staticmethod
    async def enrol_student(
        db: AsyncSession,
        institution_id: uuid.UUID,
        offering_id: uuid.UUID,
        data: EnrolStudentRequest,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> CourseOfferingEnrolment:
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != institution_id:
            raise AppException(
                code="OFFERING_NOT_FOUND",
                message="Course offering not found in this institution.",
                status_code=404,
            )

        member_id = uuid.UUID(data.student_membership_id)
        member = await db.get(InstitutionMembership, member_id)
        if not member or member.institution_id != institution_id or member.membership_status != "active":
            raise AppException(
                code="STUDENT_NOT_FOUND",
                message="Student not found or inactive in this institution.",
                status_code=404,
            )

        # Ensure student has a student_programme_enrolment
        spe_stmt = select(StudentProgrammeEnrolment).where(
            and_(
                StudentProgrammeEnrolment.institution_membership_id == member_id,
                StudentProgrammeEnrolment.status == "active",
            )
        )
        spe = (await db.execute(spe_stmt)).scalars().first()

        if not spe:
            # Look up curriculum entry programme to create default programme enrolment if needed
            entry = await db.get(CurriculumSubjectEntry, offering.curriculum_subject_entry_id)
            ver = await db.get(CurriculumVersion, entry.curriculum_version_id) if entry else None

            spe = StudentProgrammeEnrolment(
                id=uuid.uuid4(),
                institution_id=institution_id,
                institution_membership_id=member_id,
                degree_programme_id=ver.degree_programme_id if ver else offering.delivering_academic_unit_id,
                curriculum_version_id=ver.id if ver else None,
                registration_number=f"REG-{str(member_id)[:8]}",
                admission_year=2025,
                status="active",
                started_on=offering.starts_at or offering.created_at.date(),
            )
            db.add(spe)
            await db.flush()

        # Check existing active enrolment
        existing_stmt = select(CourseOfferingEnrolment).where(
            and_(
                CourseOfferingEnrolment.course_offering_id == offering_id,
                CourseOfferingEnrolment.student_programme_enrolment_id == spe.id,
                CourseOfferingEnrolment.enrolment_status == "active",
            )
        )
        if (await db.execute(existing_stmt)).scalars().first():
            raise AppException(
                code="DUPLICATE_ENROLMENT",
                message="Student is already actively enrolled in this course offering.",
                status_code=400,
            )

        enrolment = CourseOfferingEnrolment(
            id=uuid.uuid4(),
            institution_id=institution_id,
            course_offering_id=offering_id,
            student_programme_enrolment_id=spe.id,
            institution_membership_id=member_id,
            section_label=data.section_label,
            enrolment_status="active",
            created_by_user_id=created_by_user_id,
        )
        db.add(enrolment)
        await db.commit()
        await db.refresh(enrolment)
        return enrolment

    @staticmethod
    async def bulk_enrol_students(
        db: AsyncSession,
        institution_id: uuid.UUID,
        offering_id: uuid.UUID,
        data: BulkEnrolStudentsRequest,
        created_by_user_id: Optional[uuid.UUID] = None,
    ) -> dict:
        success_count = 0
        skipped_count = 0

        for mid in data.student_membership_ids:
            try:
                await AcademicService.enrol_student(
                    db=db,
                    institution_id=institution_id,
                    offering_id=offering_id,
                    data=EnrolStudentRequest(student_membership_id=mid, section_label=data.section_label),
                    created_by_user_id=created_by_user_id,
                )
                success_count += 1
            except Exception:
                skipped_count += 1

        return {
            "offering_id": str(offering_id),
            "enrolled_count": success_count,
            "skipped_count": skipped_count,
            "total_requested": len(data.student_membership_ids),
        }

    # --------------------------------------------------------------------------
    # Role-Based Course Scope Resolution
    # --------------------------------------------------------------------------

    @staticmethod
    async def get_teacher_offerings(
        db: AsyncSession, institution_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[CourseOffering]:
        """Resolve all course offerings actively assigned to this teacher."""
        # Get membership
        mem_stmt = select(InstitutionMembership).where(
            and_(
                InstitutionMembership.institution_id == institution_id,
                InstitutionMembership.user_id == user_id,
                InstitutionMembership.membership_status == "active",
            )
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if not mem:
            return []

        # Find assigned offerings
        stmt = (
            select(CourseOffering)
            .join(CourseOfferingFaculty, CourseOfferingFaculty.course_offering_id == CourseOffering.id)
            .where(
                and_(
                    CourseOfferingFaculty.institution_membership_id == mem.id,
                    CourseOfferingFaculty.status == "active",
                    CourseOffering.institution_id == institution_id,
                    CourseOffering.status == "active",
                )
            )
            .options(
                selectinload(CourseOffering.curriculum_subject_entry).selectinload(CurriculumSubjectEntry.canonical_subject),
                selectinload(CourseOffering.academic_term),
                selectinload(CourseOffering.delivering_academic_unit),
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_student_offerings(
        db: AsyncSession, institution_id: uuid.UUID, user_id: uuid.UUID
    ) -> List[CourseOffering]:
        """Resolve all course offerings actively enrolled by this student."""
        mem_stmt = select(InstitutionMembership).where(
            and_(
                InstitutionMembership.institution_id == institution_id,
                InstitutionMembership.user_id == user_id,
                InstitutionMembership.membership_status == "active",
            )
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if not mem:
            return []

        stmt = (
            select(CourseOffering)
            .join(CourseOfferingEnrolment, CourseOfferingEnrolment.course_offering_id == CourseOffering.id)
            .where(
                and_(
                    CourseOfferingEnrolment.institution_membership_id == mem.id,
                    CourseOfferingEnrolment.enrolment_status == "active",
                    CourseOffering.institution_id == institution_id,
                    CourseOffering.status == "active",
                )
            )
            .options(
                selectinload(CourseOffering.curriculum_subject_entry).selectinload(CurriculumSubjectEntry.canonical_subject),
                selectinload(CourseOffering.academic_term),
                selectinload(CourseOffering.delivering_academic_unit),
            )
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def verify_course_access(
        db: AsyncSession,
        offering_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        institution_id: Optional[str] = None,
    ) -> CourseOffering:
        """
        Verify authoritative access to a course offering:
        - SUPER_ADMIN: platform access granted.
        - ADMIN: access granted if same institution.
        - TEACHER: access granted ONLY if explicitly assigned in course_offering_faculty.
        - STUDENT: access granted ONLY if explicitly enrolled in course_offering_enrolments.
        """
        offering = await db.get(CourseOffering, offering_id)
        if not offering:
            raise AppException(code="OFFERING_NOT_FOUND", message="Course offering not found.", status_code=404)

        if user_role == "SUPER_ADMIN":
            return offering

        if user_role == "ADMIN":
            if institution_id and str(offering.institution_id) != institution_id:
                raise AuthorizationError("Access forbidden: course belongs to another institution.")
            return offering

        # Resolve user's membership
        mem_stmt = select(InstitutionMembership).where(
            and_(
                InstitutionMembership.institution_id == offering.institution_id,
                InstitutionMembership.user_id == user_id,
                InstitutionMembership.membership_status == "active",
            )
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if not mem:
            raise AuthorizationError("Access forbidden: You are not an active member of this institution.")

        if user_role == "TEACHER":
            fac_stmt = select(CourseOfferingFaculty).where(
                and_(
                    CourseOfferingFaculty.course_offering_id == offering_id,
                    CourseOfferingFaculty.institution_membership_id == mem.id,
                    CourseOfferingFaculty.status == "active",
                )
            )
            if not (await db.execute(fac_stmt)).scalars().first():
                raise AuthorizationError(
                    "Access forbidden: You are not an assigned instructor for this course offering."
                )
            return offering

        if user_role == "STUDENT":
            enr_stmt = select(CourseOfferingEnrolment).where(
                and_(
                    CourseOfferingEnrolment.course_offering_id == offering_id,
                    CourseOfferingEnrolment.institution_membership_id == mem.id,
                    CourseOfferingEnrolment.enrolment_status == "active",
                )
            )
            if not (await db.execute(enr_stmt)).scalars().first():
                raise AuthorizationError(
                    "Access forbidden: You are not enrolled in this course offering."
                )
            return offering

        raise AuthorizationError("Access forbidden: Unsupported role for course access.")

