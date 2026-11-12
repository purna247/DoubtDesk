import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import (
    get_current_user,
    require_institution_admin,
    require_teacher,
    require_student,
    enforce_tenant_boundary,
)
from app.modules.auth.schemas import UserProfile
from app.modules.academics.schemas import (
    AcademicUnitCreate,
    AcademicUnitOut,
    DegreeProgrammeCreate,
    DegreeProgrammeOut,
    ProgrammeBranchCreate,
    ProgrammeBranchOut,
    CurriculumVersionCreate,
    CurriculumVersionOut,
    AcademicYearCreate,
    AcademicYearOut,
    AcademicTermCreate,
    AcademicTermOut,
    SubjectCategoryCreate,
    SubjectCategoryOut,
    CanonicalSubjectCreate,
    CanonicalSubjectOut,
    CurriculumSubjectEntryCreate,
    CurriculumSubjectEntryOut,
    CourseOfferingCreate,
    CourseOfferingOut,
    AssignFacultyRequest,
    CourseOfferingFacultyOut,
    EnrolStudentRequest,
    BulkEnrolStudentsRequest,
    CourseOfferingEnrolmentOut,
)
from app.modules.academics.service import AcademicService

router = APIRouter(prefix="/academics", tags=["Academic Master Data & Course Management"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


# ------------------------------------------------------------------------------
# Academic Units (/admin/academic/units)
# ------------------------------------------------------------------------------

@router.post("/units", response_model=AcademicUnitOut, status_code=status.HTTP_201_CREATED)
async def create_unit(
    data: AcademicUnitCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> AcademicUnitOut:
    unit = await AcademicService.create_academic_unit(db, _get_tenant_id(user), data)
    return AcademicUnitOut(
        id=str(unit.id),
        institution_id=str(unit.institution_id),
        parent_unit_id=str(unit.parent_unit_id) if unit.parent_unit_id else None,
        unit_type=unit.unit_type,
        code=unit.code,
        name=unit.name,
        is_active=unit.is_active,
        created_at=unit.created_at,
    )


@router.get("/units", response_model=List[AcademicUnitOut])
async def list_units(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AcademicUnitOut]:
    units = await AcademicService.list_academic_units(db, _get_tenant_id(user))
    return [
        AcademicUnitOut(
            id=str(u.id),
            institution_id=str(u.institution_id),
            parent_unit_id=str(u.parent_unit_id) if u.parent_unit_id else None,
            unit_type=u.unit_type,
            code=u.code,
            name=u.name,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in units
    ]


# ------------------------------------------------------------------------------
# Degree Programmes & Branches
# ------------------------------------------------------------------------------

@router.post("/programmes", response_model=DegreeProgrammeOut, status_code=status.HTTP_201_CREATED)
async def create_programme(
    data: DegreeProgrammeCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> DegreeProgrammeOut:
    prog = await AcademicService.create_degree_programme(db, _get_tenant_id(user), data)
    return DegreeProgrammeOut(
        id=str(prog.id),
        institution_id=str(prog.institution_id),
        code=prog.code,
        name=prog.name,
        degree_level=prog.degree_level,
        nominal_duration_years=prog.nominal_duration_years,
        owning_academic_unit_id=str(prog.owning_academic_unit_id) if prog.owning_academic_unit_id else None,
        is_active=prog.is_active,
        created_at=prog.created_at,
    )


@router.get("/programmes", response_model=List[DegreeProgrammeOut])
async def list_programmes(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DegreeProgrammeOut]:
    progs = await AcademicService.list_degree_programmes(db, _get_tenant_id(user))
    return [
        DegreeProgrammeOut(
            id=str(p.id),
            institution_id=str(p.institution_id),
            code=p.code,
            name=p.name,
            degree_level=p.degree_level,
            nominal_duration_years=p.nominal_duration_years,
            owning_academic_unit_id=str(p.owning_academic_unit_id) if p.owning_academic_unit_id else None,
            is_active=p.is_active,
            created_at=p.created_at,
        )
        for p in progs
    ]


@router.post("/programmes/{programme_id}/branches", response_model=ProgrammeBranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(
    programme_id: str,
    data: ProgrammeBranchCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> ProgrammeBranchOut:
    branch = await AcademicService.create_programme_branch(
        db, _get_tenant_id(user), uuid.UUID(programme_id), data
    )
    return ProgrammeBranchOut(
        id=str(branch.id),
        institution_id=str(branch.institution_id),
        degree_programme_id=str(branch.degree_programme_id),
        code=branch.code,
        name=branch.name,
        is_active=branch.is_active,
        created_at=branch.created_at,
    )


@router.get("/programmes/{programme_id}/branches", response_model=List[ProgrammeBranchOut])
async def list_branches(
    programme_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ProgrammeBranchOut]:
    branches = await AcademicService.list_programme_branches(
        db, _get_tenant_id(user), uuid.UUID(programme_id)
    )
    return [
        ProgrammeBranchOut(
            id=str(b.id),
            institution_id=str(b.institution_id),
            degree_programme_id=str(b.degree_programme_id),
            code=b.code,
            name=b.name,
            is_active=b.is_active,
            created_at=b.created_at,
        )
        for b in branches
    ]


# ------------------------------------------------------------------------------
# Curriculum Versions
# ------------------------------------------------------------------------------

@router.post("/curriculum-versions", response_model=CurriculumVersionOut, status_code=status.HTTP_201_CREATED)
async def create_curriculum_version(
    data: CurriculumVersionCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CurriculumVersionOut:
    ver = await AcademicService.create_curriculum_version(db, _get_tenant_id(user), data)
    return CurriculumVersionOut(
        id=str(ver.id),
        institution_id=str(ver.institution_id),
        degree_programme_id=str(ver.degree_programme_id),
        programme_branch_id=str(ver.programme_branch_id) if ver.programme_branch_id else None,
        version_code=ver.version_code,
        display_name=ver.display_name,
        effective_from_admission_year=ver.effective_from_admission_year,
        effective_to_admission_year=ver.effective_to_admission_year,
        status=ver.status,
        created_at=ver.created_at,
    )


@router.get("/curriculum-versions", response_model=List[CurriculumVersionOut])
async def list_curriculum_versions(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CurriculumVersionOut]:
    versions = await AcademicService.list_curriculum_versions(db, _get_tenant_id(user))
    return [
        CurriculumVersionOut(
            id=str(v.id),
            institution_id=str(v.institution_id),
            degree_programme_id=str(v.degree_programme_id),
            programme_branch_id=str(v.programme_branch_id) if v.programme_branch_id else None,
            version_code=v.version_code,
            display_name=v.display_name,
            effective_from_admission_year=v.effective_from_admission_year,
            effective_to_admission_year=v.effective_to_admission_year,
            status=v.status,
            created_at=v.created_at,
        )
        for v in versions
    ]


# ------------------------------------------------------------------------------
# Canonical Subject Catalog (/admin/academic/subjects)
# ------------------------------------------------------------------------------

@router.post("/canonical-subjects", response_model=CanonicalSubjectOut, status_code=status.HTTP_201_CREATED)
async def create_canonical_subject(
    data: CanonicalSubjectCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CanonicalSubjectOut:
    subj = await AcademicService.create_canonical_subject(db, _get_tenant_id(user), data)
    return CanonicalSubjectOut(
        id=str(subj.id),
        institution_id=str(subj.institution_id),
        owning_academic_unit_id=str(subj.owning_academic_unit_id) if subj.owning_academic_unit_id else None,
        canonical_code=subj.canonical_code,
        name=subj.name,
        description=subj.description,
        status=subj.status,
        created_at=subj.created_at,
    )


@router.get("/canonical-subjects", response_model=List[CanonicalSubjectOut])
async def list_canonical_subjects(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CanonicalSubjectOut]:
    subjects = await AcademicService.list_canonical_subjects(db, _get_tenant_id(user))
    return [
        CanonicalSubjectOut(
            id=str(s.id),
            institution_id=str(s.institution_id),
            owning_academic_unit_id=str(s.owning_academic_unit_id) if s.owning_academic_unit_id else None,
            canonical_code=s.canonical_code,
            name=s.name,
            description=s.description,
            status=s.status,
            created_at=s.created_at,
        )
        for s in subjects
    ]


# ------------------------------------------------------------------------------
# Curriculum Subject Entries (/admin/curriculum/subjects)
# ------------------------------------------------------------------------------

@router.post("/curriculum-subjects", response_model=CurriculumSubjectEntryOut, status_code=status.HTTP_201_CREATED)
async def create_curriculum_subject(
    data: CurriculumSubjectEntryCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CurriculumSubjectEntryOut:
    entry = await AcademicService.create_curriculum_subject_entry(db, _get_tenant_id(user), data)
    return CurriculumSubjectEntryOut(
        id=str(entry.id),
        institution_id=str(entry.institution_id),
        curriculum_version_id=str(entry.curriculum_version_id),
        canonical_subject_id=str(entry.canonical_subject_id),
        subject_category_id=str(entry.subject_category_id),
        official_subject_code=entry.official_subject_code,
        display_name_override=entry.display_name_override,
        semester_number=entry.semester_number,
        credits=float(entry.credits) if entry.credits is not None else None,
        lecture_hours_per_week=float(entry.lecture_hours_per_week),
        tutorial_hours_per_week=float(entry.tutorial_hours_per_week),
        practical_hours_per_week=float(entry.practical_hours_per_week),
        marks_scheme_status=entry.marks_scheme_status,
        is_active=entry.is_active,
        created_at=entry.created_at,
    )


@router.get("/curriculum-subjects", response_model=List[CurriculumSubjectEntryOut])
async def list_curriculum_subjects(
    curriculum_version_id: Optional[str] = None,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CurriculumSubjectEntryOut]:
    ver_id = uuid.UUID(curriculum_version_id) if curriculum_version_id else None
    entries = await AcademicService.list_curriculum_subject_entries(db, _get_tenant_id(user), ver_id)
    return [
        CurriculumSubjectEntryOut(
            id=str(e.id),
            institution_id=str(e.institution_id),
            curriculum_version_id=str(e.curriculum_version_id),
            canonical_subject_id=str(e.canonical_subject_id),
            subject_category_id=str(e.subject_category_id),
            official_subject_code=e.official_subject_code,
            display_name_override=e.display_name_override,
            semester_number=e.semester_number,
            credits=float(e.credits) if e.credits is not None else None,
            lecture_hours_per_week=float(e.lecture_hours_per_week),
            tutorial_hours_per_week=float(e.tutorial_hours_per_week),
            practical_hours_per_week=float(e.practical_hours_per_week),
            marks_scheme_status=e.marks_scheme_status,
            is_active=e.is_active,
            created_at=e.created_at,
            canonical_name=e.canonical_subject.name if e.canonical_subject else None,
        )
        for e in entries
    ]


# ------------------------------------------------------------------------------
# Academic Terms & Categories
# ------------------------------------------------------------------------------

@router.post("/terms", response_model=AcademicTermOut, status_code=status.HTTP_201_CREATED)
async def create_term(
    data: AcademicTermCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> AcademicTermOut:
    term = await AcademicService.create_academic_term(db, _get_tenant_id(user), data)
    return AcademicTermOut(
        id=str(term.id),
        institution_id=str(term.institution_id),
        academic_year_id=str(term.academic_year_id),
        term_code=term.term_code,
        display_name=term.display_name,
        term_sequence=term.term_sequence,
        starts_on=term.starts_on,
        ends_on=term.ends_on,
        status=term.status,
        created_at=term.created_at,
    )


@router.get("/terms", response_model=List[AcademicTermOut])
async def list_terms(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AcademicTermOut]:
    terms = await AcademicService.list_academic_terms(db, _get_tenant_id(user))
    return [
        AcademicTermOut(
            id=str(t.id),
            institution_id=str(t.institution_id),
            academic_year_id=str(t.academic_year_id),
            term_code=t.term_code,
            display_name=t.display_name,
            term_sequence=t.term_sequence,
            starts_on=t.starts_on,
            ends_on=t.ends_on,
            status=t.status,
            created_at=t.created_at,
        )
        for t in terms
    ]


@router.post("/categories", response_model=SubjectCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: SubjectCategoryCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> SubjectCategoryOut:
    cat = await AcademicService.create_subject_category(db, _get_tenant_id(user), data)
    return SubjectCategoryOut(
        id=str(cat.id),
        institution_id=str(cat.institution_id),
        code=cat.code,
        display_name=cat.display_name,
        description=cat.description,
        is_active=cat.is_active,
    )


@router.get("/categories", response_model=List[SubjectCategoryOut])
async def list_categories(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SubjectCategoryOut]:
    cats = await AcademicService.list_subject_categories(db, _get_tenant_id(user))
    return [
        SubjectCategoryOut(
            id=str(c.id),
            institution_id=str(c.institution_id),
            code=c.code,
            display_name=c.display_name,
            description=c.description,
            is_active=c.is_active,
        )
        for c in cats
    ]


# ------------------------------------------------------------------------------
# Course Offerings (/admin/academic/offerings)
# ------------------------------------------------------------------------------

@router.post("/offerings", response_model=CourseOfferingOut, status_code=status.HTTP_201_CREATED)
async def create_offering(
    data: CourseOfferingCreate,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    offering = await AcademicService.create_course_offering(db, _get_tenant_id(user), data)
    return CourseOfferingOut(
        id=str(offering.id),
        institution_id=str(offering.institution_id),
        curriculum_subject_entry_id=str(offering.curriculum_subject_entry_id),
        academic_term_id=str(offering.academic_term_id),
        delivering_academic_unit_id=str(offering.delivering_academic_unit_id),
        section_code=offering.section_code,
        cohort_label=offering.cohort_label,
        delivery_mode=offering.delivery_mode,
        status=offering.status,
        created_at=offering.created_at,
    )


# ------------------------------------------------------------------------------
# Direct Role Workspaces Offering Aliases
# ------------------------------------------------------------------------------

offerings_router = APIRouter(tags=["Role Workspaces"])


@offerings_router.get("/teacher/offerings", response_model=List[CourseOfferingOut])
async def get_teacher_offerings_workspace(
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    return await get_teacher_offerings(user, db)


@offerings_router.get("/teacher/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_teacher_offering_detail_workspace(
    offering_id: str,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    return await get_teacher_offering_detail(offering_id, user, db)


@offerings_router.get("/student/offerings", response_model=List[CourseOfferingOut])
@offerings_router.get("/courses", response_model=List[CourseOfferingOut])
async def get_student_offerings_workspace(
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    return await get_student_offerings(user, db)


@offerings_router.get("/student/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_student_offering_detail_workspace(
    offering_id: str,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    return await get_student_offering_detail(offering_id, user, db)





@router.get("/offerings", response_model=List[CourseOfferingOut])
async def list_offerings(
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    offerings = await AcademicService.list_course_offerings(db, _get_tenant_id(user))
    return [
        CourseOfferingOut(
            id=str(o.id),
            institution_id=str(o.institution_id),
            curriculum_subject_entry_id=str(o.curriculum_subject_entry_id),
            academic_term_id=str(o.academic_term_id),
            delivering_academic_unit_id=str(o.delivering_academic_unit_id),
            section_code=o.section_code,
            cohort_label=o.cohort_label,
            delivery_mode=o.delivery_mode,
            status=o.status,
            created_at=o.created_at,
            official_subject_code=o.curriculum_subject_entry.official_subject_code if o.curriculum_subject_entry else None,
            subject_name=o.curriculum_subject_entry.canonical_subject.name if o.curriculum_subject_entry and o.curriculum_subject_entry.canonical_subject else None,
            term_code=o.academic_term.term_code if o.academic_term else None,
            delivering_unit_name=o.delivering_academic_unit.name if o.delivering_academic_unit else None,
        )
        for o in offerings
    ]


# ------------------------------------------------------------------------------
# Faculty Assignments
# ------------------------------------------------------------------------------

@router.post("/offerings/{offering_id}/faculty", response_model=CourseOfferingFacultyOut)
async def assign_faculty(
    offering_id: str,
    data: AssignFacultyRequest,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingFacultyOut:
    assignment = await AcademicService.assign_faculty(
        db=db,
        institution_id=_get_tenant_id(user),
        offering_id=uuid.UUID(offering_id),
        data=data,
        assigned_by_user_id=uuid.UUID(user.id),
    )
    return CourseOfferingFacultyOut(
        id=str(assignment.id),
        course_offering_id=str(assignment.course_offering_id),
        institution_membership_id=str(assignment.institution_membership_id),
        assignment_role=assignment.assignment_role,
        can_manage_content=assignment.can_manage_content,
        status=assignment.status,
        created_at=assignment.created_at,
    )


@router.get("/offerings/{offering_id}/faculty", response_model=List[CourseOfferingFacultyOut])
async def list_offering_faculty(
    offering_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingFacultyOut]:
    assignments = await AcademicService.list_faculty_assignments(db, uuid.UUID(offering_id))
    return [
        CourseOfferingFacultyOut(
            id=str(a.id),
            course_offering_id=str(a.course_offering_id),
            institution_membership_id=str(a.institution_membership_id),
            faculty_name=a.membership.user.display_name if a.membership and a.membership.user else None,
            assignment_role=a.assignment_role,
            can_manage_content=a.can_manage_content,
            status=a.status,
            created_at=a.created_at,
        )
        for a in assignments
    ]


# ------------------------------------------------------------------------------
# Student Enrolments (Admin-Managed Only; Self-Enrolment Rejected)
# ------------------------------------------------------------------------------

@router.post("/offerings/{offering_id}/enrolments", response_model=CourseOfferingEnrolmentOut)
async def enrol_student(
    offering_id: str,
    data: EnrolStudentRequest,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingEnrolmentOut:
    enr = await AcademicService.enrol_student(
        db=db,
        institution_id=_get_tenant_id(user),
        offering_id=uuid.UUID(offering_id),
        data=data,
        created_by_user_id=uuid.UUID(user.id),
    )
    return CourseOfferingEnrolmentOut(
        id=str(enr.id),
        course_offering_id=str(enr.course_offering_id),
        student_membership_id=str(enr.institution_membership_id),
        section_label=enr.section_label,
        enrolment_status=enr.enrolment_status,
        enrolled_at=enr.enrolled_at,
    )


@router.post("/offerings/{offering_id}/enrolments/bulk")
async def bulk_enrol_students(
    offering_id: str,
    data: BulkEnrolStudentsRequest,
    user: UserProfile = Depends(require_institution_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await AcademicService.bulk_enrol_students(
        db=db,
        institution_id=_get_tenant_id(user),
        offering_id=uuid.UUID(offering_id),
        data=data,
        created_by_user_id=uuid.UUID(user.id),
    )


# ------------------------------------------------------------------------------
# Teacher Offering Views (/teacher/offerings)
# ------------------------------------------------------------------------------

@router.get("/teacher/offerings", response_model=List[CourseOfferingOut])
async def get_teacher_offerings(
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    offerings = await AcademicService.get_teacher_offerings(
        db=db,
        institution_id=_get_tenant_id(user),
        user_id=uuid.UUID(user.id),
    )
    return [
        CourseOfferingOut(
            id=str(o.id),
            institution_id=str(o.institution_id),
            curriculum_subject_entry_id=str(o.curriculum_subject_entry_id),
            academic_term_id=str(o.academic_term_id),
            delivering_academic_unit_id=str(o.delivering_academic_unit_id),
            section_code=o.section_code,
            cohort_label=o.cohort_label,
            delivery_mode=o.delivery_mode,
            status=o.status,
            created_at=o.created_at,
            official_subject_code=o.curriculum_subject_entry.official_subject_code if o.curriculum_subject_entry else None,
            subject_name=o.curriculum_subject_entry.canonical_subject.name if o.curriculum_subject_entry and o.curriculum_subject_entry.canonical_subject else None,
            term_code=o.academic_term.term_code if o.academic_term else None,
            delivering_unit_name=o.delivering_academic_unit.name if o.delivering_academic_unit else None,
        )
        for o in offerings
    ]


@router.get("/teacher/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_teacher_offering_detail(
    offering_id: str,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    offering = await AcademicService.verify_course_access(
        db=db,
        offering_id=uuid.UUID(offering_id),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        institution_id=user.institution_id,
    )
    return CourseOfferingOut(
        id=str(offering.id),
        institution_id=str(offering.institution_id),
        curriculum_subject_entry_id=str(offering.curriculum_subject_entry_id),
        academic_term_id=str(offering.academic_term_id),
        delivering_academic_unit_id=str(offering.delivering_academic_unit_id),
        section_code=offering.section_code,
        cohort_label=offering.cohort_label,
        delivery_mode=offering.delivery_mode,
        status=offering.status,
        created_at=offering.created_at,
    )


# ------------------------------------------------------------------------------
# Student Enrolled Offerings (/student/offerings)
# ------------------------------------------------------------------------------

@router.get("/student/offerings", response_model=List[CourseOfferingOut])
async def get_student_offerings(
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    offerings = await AcademicService.get_student_offerings(
        db=db,
        institution_id=_get_tenant_id(user),
        user_id=uuid.UUID(user.id),
    )
    return [
        CourseOfferingOut(
            id=str(o.id),
            institution_id=str(o.institution_id),
            curriculum_subject_entry_id=str(o.curriculum_subject_entry_id),
            academic_term_id=str(o.academic_term_id),
            delivering_academic_unit_id=str(o.delivering_academic_unit_id),
            section_code=o.section_code,
            cohort_label=o.cohort_label,
            delivery_mode=o.delivery_mode,
            status=o.status,
            created_at=o.created_at,
            official_subject_code=o.curriculum_subject_entry.official_subject_code if o.curriculum_subject_entry else None,
            subject_name=o.curriculum_subject_entry.canonical_subject.name if o.curriculum_subject_entry and o.curriculum_subject_entry.canonical_subject else None,
            term_code=o.academic_term.term_code if o.academic_term else None,
            delivering_unit_name=o.delivering_academic_unit.name if o.delivering_academic_unit else None,
        )
        for o in offerings
    ]


@router.get("/student/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_student_offering_detail(
    offering_id: str,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    offering = await AcademicService.verify_course_access(
        db=db,
        offering_id=uuid.UUID(offering_id),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        institution_id=user.institution_id,
    )
    return CourseOfferingOut(
        id=str(offering.id),
        institution_id=str(offering.institution_id),
        curriculum_subject_entry_id=str(offering.curriculum_subject_entry_id),
        academic_term_id=str(offering.academic_term_id),
        delivering_academic_unit_id=str(offering.delivering_academic_unit_id),
        section_code=offering.section_code,
        cohort_label=offering.cohort_label,
        delivery_mode=offering.delivery_mode,
        status=offering.status,
        created_at=offering.created_at,
    )


# ------------------------------------------------------------------------------
# Direct Role Workspaces Offering Aliases
# ------------------------------------------------------------------------------

offerings_router = APIRouter(tags=["Role Workspaces"])


@offerings_router.get("/teacher/offerings", response_model=List[CourseOfferingOut])
async def get_teacher_offerings_workspace(
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    return await get_teacher_offerings(user, db)


@offerings_router.get("/teacher/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_teacher_offering_detail_workspace(
    offering_id: str,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    return await get_teacher_offering_detail(offering_id, user, db)


@offerings_router.get("/student/offerings", response_model=List[CourseOfferingOut])
@offerings_router.get("/courses", response_model=List[CourseOfferingOut])
async def get_student_offerings_workspace(
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[CourseOfferingOut]:
    return await get_student_offerings(user, db)


@offerings_router.get("/student/offerings/{offering_id}", response_model=CourseOfferingOut)
async def get_student_offering_detail_workspace(
    offering_id: str,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> CourseOfferingOut:
    return await get_student_offering_detail(offering_id, user, db)



