import asyncio
import logging
from datetime import date, datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.modules.auth.models import (
    User,
    UserIdentifier,
    PasswordCredential,
    MFACredential,
    PlatformRoleAssignment,
    InstitutionMembership,
    InstitutionMembershipRole,
)
from app.modules.auth.security import hash_password
from app.modules.institutions.models import Institution, InstitutionSettings
from app.modules.academics.models import (
    AcademicUnit,
    AcademicYear,
    AcademicTerm,
    DegreeProgramme,
    ProgrammeBranch,
    CurriculumVersion,
    SubjectCategory,
    CanonicalSubject,
    CurriculumSubjectEntry,
    FacultyDesignation,
    FacultyAppointment,
    StudentProgrammeEnrolment,
    StudentSemesterHistory,
    CourseOffering,
    CourseOfferingFaculty,
    CourseOfferingEnrolment,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("doubtdesk.seed")


async def seed_database() -> None:
    settings = get_settings()

    if not settings.SUPERADMIN_EMAIL or not settings.SUPERADMIN_PASSWORD or not settings.SUPERADMIN_TOTP_SECRET:
        raise ValueError(
            "SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, and SUPERADMIN_TOTP_SECRET must be configured in .env"
        )

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        logger.info("Beginning DoubtDesk database seed...")

        # ----------------------------------------------------------------------
        # 1. Super Admin Identity & Platform Role
        # ----------------------------------------------------------------------
        super_email = settings.SUPERADMIN_EMAIL.strip().lower()
        res = await db.execute(select(UserIdentifier).where(UserIdentifier.normalized_value == super_email))
        super_ident = res.scalars().first()

        if not super_ident:
            logger.info("Seeding Super Admin user: %s", super_email)
            super_user = User(
                id=uuid.uuid4(),
                display_name="Platform Super Admin",
                legal_name="DoubtDesk Root Administrator",
                account_status="active",
            )
            db.add(super_user)
            await db.flush()

            db.add(
                UserIdentifier(
                    user_id=super_user.id,
                    identifier_type="email",
                    identifier_value=super_email,
                    normalized_value=super_email,
                    is_login_enabled=True,
                    is_primary=True,
                    verified_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                PasswordCredential(
                    user_id=super_user.id,
                    password_hash=hash_password(settings.SUPERADMIN_PASSWORD),
                )
            )
            db.add(
                MFACredential(
                    user_id=super_user.id,
                    secret_key=settings.SUPERADMIN_TOTP_SECRET,
                    is_enabled=True,
                )
            )
            db.add(
                PlatformRoleAssignment(
                    user_id=super_user.id,
                    role_code="super_admin",
                    reason="Initial platform bootstrap provisioning",
                )
            )
            logger.info("Super Admin created successfully.")
        else:
            logger.info("Super Admin already exists (%s). Skipping.", super_email)

        # ----------------------------------------------------------------------
        # 2. Institutional Tenant: OUTR University
        # ----------------------------------------------------------------------
        inst_res = await db.execute(select(Institution).where(Institution.institution_code == "OUTR"))
        institution = inst_res.scalars().first()

        if not institution:
            logger.info("Seeding Institution: Odisha University of Technology and Research (OUTR)")
            institution = Institution(
                id=uuid.uuid4(),
                institution_code="OUTR",
                legal_name="Odisha University of Technology and Research",
                display_name="OUTR Bhubaneswar",
                primary_domain="outr.ac.in",
                status="active",
                timezone="Asia/Kolkata",
            )
            db.add(institution)
            await db.flush()

            db.add(
                InstitutionSettings(
                    institution_id=institution.id,
                    allow_teacher_view_anonymous=False,
                    min_distinct_questions_for_gap=3,
                    weakness_accuracy_threshold=0.60,
                    default_upload_limit_mb=50,
                )
            )
            await db.flush()
        else:
            logger.info("Institution OUTR already exists.")

        # Helper to provision user + identifier + password + membership + role
        async def ensure_user(email: str, name: str, password: str, role_code: str, reg_no: str = None) -> tuple[User, InstitutionMembership]:
            norm_email = email.strip().lower()
            u_res = await db.execute(select(UserIdentifier).where(UserIdentifier.normalized_value == norm_email))
            ident = u_res.scalars().first()

            if not ident:
                usr = User(
                    id=uuid.uuid4(),
                    display_name=name,
                    account_status="active",
                )
                db.add(usr)
                await db.flush()

                db.add(
                    UserIdentifier(
                        user_id=usr.id,
                        institution_id=institution.id,
                        identifier_type="email",
                        identifier_value=norm_email,
                        normalized_value=norm_email,
                        is_login_enabled=True,
                        is_primary=True,
                        verified_at=datetime.now(timezone.utc),
                    )
                )

                if reg_no:
                    db.add(
                        UserIdentifier(
                            user_id=usr.id,
                            institution_id=institution.id,
                            identifier_type="student_registration_number",
                            identifier_value=reg_no,
                            normalized_value=reg_no.strip().lower(),
                            is_login_enabled=True,
                            is_primary=False,
                            verified_at=datetime.now(timezone.utc),
                        )
                    )

                db.add(
                    PasswordCredential(
                        user_id=usr.id,
                        password_hash=hash_password(password),
                    )
                )

                mem = InstitutionMembership(
                    id=uuid.uuid4(),
                    institution_id=institution.id,
                    user_id=usr.id,
                    membership_status="active",
                )
                db.add(mem)
                await db.flush()

                db.add(
                    InstitutionMembershipRole(
                        institution_id=institution.id,
                        institution_membership_id=mem.id,
                        role_code=role_code,
                    )
                )
                await db.flush()
                logger.info("Created user %s (%s) with role %s", name, email, role_code)
                return usr, mem
            else:
                usr_res = await db.execute(select(User).where(User.id == ident.user_id))
                usr = usr_res.scalars().first()
                mem_res = await db.execute(
                    select(InstitutionMembership).where(
                        InstitutionMembership.institution_id == institution.id,
                        InstitutionMembership.user_id == usr.id,
                    )
                )
                mem = mem_res.scalars().first()
                return usr, mem

        # ----------------------------------------------------------------------
        # 3. Institutional Users (Admin, Teacher, Students)
        # ----------------------------------------------------------------------
        admin_user, admin_mem = await ensure_user(
            "admin@outr.ac.in", "OUTR Administrator", "AdminPass123!", "admin"
        )
        faculty_user, faculty_mem = await ensure_user(
            "faculty.sharma@outr.ac.in", "Dr. R. K. Sharma", "TeacherPass123!", "teacher"
        )
        student1_user, student1_mem = await ensure_user(
            "student1@outr.ac.in", "Aarav Patel", "StudentPass123!", "student", reg_no="2301106001"
        )
        student2_user, student2_mem = await ensure_user(
            "student2@outr.ac.in", "Ananya Sen", "StudentPass123!", "student", reg_no="2301106002"
        )

        # ----------------------------------------------------------------------
        # 4. Academic Structure & Units
        # ----------------------------------------------------------------------
        dept_res = await db.execute(
            select(AcademicUnit).where(
                AcademicUnit.institution_id == institution.id,
                AcademicUnit.code == "CSE",
            )
        )
        dept = dept_res.scalars().first()
        if not dept:
            dept = AcademicUnit(
                id=uuid.uuid4(),
                institution_id=institution.id,
                unit_type="department",
                code="CSE",
                name="Department of Computer Science & Engineering",
                is_active=True,
            )
            db.add(dept)
            await db.flush()

        # Academic Year & Term
        ay_res = await db.execute(
            select(AcademicYear).where(
                AcademicYear.institution_id == institution.id,
                AcademicYear.code == "2026-2027",
            )
        )
        ay = ay_res.scalars().first()
        if not ay:
            ay = AcademicYear(
                id=uuid.uuid4(),
                institution_id=institution.id,
                code="2026-2027",
                display_name="Academic Year 2026-2027",
                starts_on=date(2026, 7, 1),
                ends_on=date(2027, 6, 30),
                status="active",
            )
            db.add(ay)
            await db.flush()

        term_res = await db.execute(
            select(AcademicTerm).where(
                AcademicTerm.institution_id == institution.id,
                AcademicTerm.academic_year_id == ay.id,
                AcademicTerm.term_code == "SEM-5",
            )
        )
        term = term_res.scalars().first()
        if not term:
            term = AcademicTerm(
                id=uuid.uuid4(),
                institution_id=institution.id,
                academic_year_id=ay.id,
                term_code="SEM-5",
                display_name="Odd Semester 2026 (Semester 5)",
                term_sequence=5,
                starts_on=date(2026, 8, 1),
                ends_on=date(2026, 12, 31),
                status="active",
            )
            db.add(term)
            await db.flush()

        # Degree Programme & Branch
        prog_res = await db.execute(
            select(DegreeProgramme).where(
                DegreeProgramme.institution_id == institution.id,
                DegreeProgramme.code == "BTECH-CSE",
            )
        )
        prog = prog_res.scalars().first()
        if not prog:
            prog = DegreeProgramme(
                id=uuid.uuid4(),
                institution_id=institution.id,
                code="BTECH-CSE",
                name="Bachelor of Technology in Computer Science & Engineering",
                degree_level="ug",
                nominal_duration_years=4,
                owning_academic_unit_id=dept.id,
                is_active=True,
            )
            db.add(prog)
            await db.flush()

        branch_res = await db.execute(
            select(ProgrammeBranch).where(
                ProgrammeBranch.institution_id == institution.id,
                ProgrammeBranch.degree_programme_id == prog.id,
                ProgrammeBranch.code == "CSE",
            )
        )
        branch = branch_res.scalars().first()
        if not branch:
            branch = ProgrammeBranch(
                id=uuid.uuid4(),
                institution_id=institution.id,
                degree_programme_id=prog.id,
                code="CSE",
                name="Computer Science & Engineering",
                is_active=True,
            )
            db.add(branch)
            await db.flush()

        # Curriculum Version
        curric_res = await db.execute(
            select(CurriculumVersion).where(
                CurriculumVersion.institution_id == institution.id,
                CurriculumVersion.degree_programme_id == prog.id,
                CurriculumVersion.version_code == "2024-REG",
            )
        )
        curric = curric_res.scalars().first()
        if not curric:
            curric = CurriculumVersion(
                id=uuid.uuid4(),
                institution_id=institution.id,
                degree_programme_id=prog.id,
                programme_branch_id=branch.id,
                version_code="2024-REG",
                display_name="B.Tech CSE 2024 Autonomy Curriculum Regulation",
                effective_from_admission_year=2024,
                status="active",
            )
            db.add(curric)
            await db.flush()

        # Subject Category
        cat_res = await db.execute(
            select(SubjectCategory).where(
                SubjectCategory.institution_id == institution.id,
                SubjectCategory.code == "PC",
            )
        )
        cat = cat_res.scalars().first()
        if not cat:
            cat = SubjectCategory(
                id=uuid.uuid4(),
                institution_id=institution.id,
                code="PC",
                display_name="Program Core",
                is_active=True,
            )
            db.add(cat)
            await db.flush()

        # Canonical Subject & Curriculum Entry
        subj_res = await db.execute(
            select(CanonicalSubject).where(
                CanonicalSubject.institution_id == institution.id,
                CanonicalSubject.canonical_code == "CS301",
            )
        )
        subj = subj_res.scalars().first()
        if not subj:
            subj = CanonicalSubject(
                id=uuid.uuid4(),
                institution_id=institution.id,
                canonical_code="CS301",
                name="Brain Computer Interface (BCI)",
                description="Brain-computer interface systems, neural signal acquisition and processing, feature extraction, and brain-signal classification.",
                status="active",
            )
            db.add(subj)
            await db.flush()
        else:
            # Keep the seeded subject identity and its existing relationships, while
            # allowing deliberate seed-data name corrections to update in place.
            subj.name = "Brain Computer Interface (BCI)"
            subj.description = "Brain-computer interface systems, neural signal acquisition and processing, feature extraction, and brain-signal classification."

        centry_res = await db.execute(
            select(CurriculumSubjectEntry).where(
                CurriculumSubjectEntry.institution_id == institution.id,
                CurriculumSubjectEntry.curriculum_version_id == curric.id,
                CurriculumSubjectEntry.official_subject_code == "CS301",
            )
        )
        centry = centry_res.scalars().first()
        if not centry:
            centry = CurriculumSubjectEntry(
                id=uuid.uuid4(),
                institution_id=institution.id,
                curriculum_version_id=curric.id,
                canonical_subject_id=subj.id,
                subject_category_id=cat.id,
                official_subject_code="CS301",
                display_name_override="Brain Computer Interface (BCI)",
                semester_number=5,
                credits=4.0,
                lecture_hours_per_week=3,
                tutorial_hours_per_week=1,
                practical_hours_per_week=0,
                is_active=True,
            )
            db.add(centry)
            await db.flush()
        else:
            centry.display_name_override = "Brain Computer Interface (BCI)"

        # Faculty Designation & Appointment
        desig_res = await db.execute(
            select(FacultyDesignation).where(
                FacultyDesignation.institution_id == institution.id,
                FacultyDesignation.code == "ASSOC_PROF",
            )
        )
        desig = desig_res.scalars().first()
        if not desig:
            desig = FacultyDesignation(
                id=uuid.uuid4(),
                institution_id=institution.id,
                code="ASSOC_PROF",
                display_name="Associate Professor",
                sort_order=2,
                is_active=True,
            )
            db.add(desig)
            await db.flush()

        appt_res = await db.execute(
            select(FacultyAppointment).where(
                FacultyAppointment.institution_id == institution.id,
                FacultyAppointment.institution_membership_id == faculty_mem.id,
            )
        )
        appt = appt_res.scalars().first()
        if not appt:
            appt = FacultyAppointment(
                id=uuid.uuid4(),
                institution_id=institution.id,
                institution_membership_id=faculty_mem.id,
                academic_unit_id=dept.id,
                designation_id=desig.id,
                appointment_type="permanent",
                is_primary=True,
            )
            db.add(appt)
            await db.flush()

        # Course Offering (Section A)
        off_res = await db.execute(
            select(CourseOffering).where(
                CourseOffering.institution_id == institution.id,
                CourseOffering.curriculum_subject_entry_id == centry.id,
                CourseOffering.academic_term_id == term.id,
                CourseOffering.section_code == "A",
            )
        )
        offering = off_res.scalars().first()
        if not offering:
            offering = CourseOffering(
                id=uuid.uuid4(),
                institution_id=institution.id,
                curriculum_subject_entry_id=centry.id,
                academic_term_id=term.id,
                delivering_academic_unit_id=dept.id,
                section_code="A",
                cohort_label="B.Tech CSE 2024-2028 Section A",
                status="active",
            )
            db.add(offering)
            await db.flush()

            # Assign Dr. Sharma as Primary Instructor
            db.add(
                CourseOfferingFaculty(
                    institution_id=institution.id,
                    course_offering_id=offering.id,
                    faculty_appointment_id=appt.id,
                    institution_membership_id=faculty_mem.id,
                    assignment_role="primary_instructor",
                    can_manage_content=True,
                    status="active",
                )
            )

        # Student Programme Enrolments & Course Enrolments
        async def enroll_student(s_mem: InstitutionMembership, reg: str) -> None:
            spe_res = await db.execute(
                select(StudentProgrammeEnrolment).where(
                    StudentProgrammeEnrolment.institution_id == institution.id,
                    StudentProgrammeEnrolment.registration_number == reg,
                )
            )
            spe = spe_res.scalars().first()
            if not spe:
                spe = StudentProgrammeEnrolment(
                    id=uuid.uuid4(),
                    institution_id=institution.id,
                    institution_membership_id=s_mem.id,
                    degree_programme_id=prog.id,
                    programme_branch_id=branch.id,
                    curriculum_version_id=curric.id,
                    registration_number=reg,
                    admission_year=2024,
                    cohort_code="CSE-2024",
                    status="active",
                    started_on=date(2024, 8, 1),
                )
                db.add(spe)
                await db.flush()

                db.add(
                    StudentSemesterHistory(
                        institution_id=institution.id,
                        student_programme_enrolment_id=spe.id,
                        academic_term_id=term.id,
                        semester_number=5,
                        status="active",
                        recorded_at=datetime.now(timezone.utc),
                    )
                )

                db.add(
                    CourseOfferingEnrolment(
                        institution_id=institution.id,
                        course_offering_id=offering.id,
                        student_programme_enrolment_id=spe.id,
                        institution_membership_id=s_mem.id,
                        section_label="A",
                        enrolment_status="active",
                    )
                )
                await db.flush()

        await enroll_student(student1_mem, "2301106001")
        await enroll_student(student2_mem, "2301106002")

        await db.commit()
        logger.info("DoubtDesk database seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
