import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import app.modules.auth.models  # noqa: F401


class AcademicUnit(Base):
    """
    Flexible hierarchical organizational unit (School, Department, Center).
    Supports optional parent-child nesting without cycles.
    """
    __tablename__ = "academic_units"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_academic_unit_code"),
        CheckConstraint("parent_unit_id IS NULL OR parent_unit_id <> id", name="chk_unit_not_self_parent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    unit_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # school | department | center | institution_defined
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    parent_unit: Mapped[Optional["AcademicUnit"]] = relationship(
        "AcademicUnit", remote_side=[id], back_populates="child_units"
    )
    child_units: Mapped[List["AcademicUnit"]] = relationship(
        "AcademicUnit", back_populates="parent_unit"
    )
    programmes: Mapped[List["DegreeProgramme"]] = relationship(
        "DegreeProgramme", back_populates="owning_academic_unit"
    )
    canonical_subjects: Mapped[List["CanonicalSubject"]] = relationship(
        "CanonicalSubject", back_populates="owning_academic_unit"
    )
    delivering_offerings: Mapped[List["CourseOffering"]] = relationship(
        "CourseOffering", back_populates="delivering_academic_unit"
    )


class DegreeProgramme(Base):
    """Academic degree offering (e.g. B.Tech, M.Tech, MCA, Ph.D)."""
    __tablename__ = "degree_programmes"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_degree_programme_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    degree_level: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # ug | pg | integrated | doctoral | other
    nominal_duration_years: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    owning_academic_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    owning_academic_unit: Mapped[Optional["AcademicUnit"]] = relationship(
        "AcademicUnit", back_populates="programmes"
    )
    branches: Mapped[List["ProgrammeBranch"]] = relationship(
        "ProgrammeBranch", back_populates="programme", cascade="all, delete-orphan"
    )
    curriculum_versions: Mapped[List["CurriculumVersion"]] = relationship(
        "CurriculumVersion", back_populates="programme"
    )


class ProgrammeBranch(Base):
    """Discipline specialization or branch under a Degree Programme (e.g. CSE, ECE)."""
    __tablename__ = "programme_branches"
    __table_args__ = (
        UniqueConstraint("institution_id", "degree_programme_id", "code", name="uq_programme_branch_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    degree_programme_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("degree_programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    programme: Mapped["DegreeProgramme"] = relationship(
        "DegreeProgramme", back_populates="branches"
    )
    curriculum_versions: Mapped[List["CurriculumVersion"]] = relationship(
        "CurriculumVersion", back_populates="branch"
    )


class CurriculumVersion(Base):
    """Regulation or curriculum scheme governing a programme or branch (e.g. 2021 Regulation)."""
    __tablename__ = "curriculum_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    degree_programme_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("degree_programmes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    programme_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("programme_branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. 2021-scheme
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from_admission_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    effective_to_admission_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # draft | active | superseded | archived

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    programme: Mapped["DegreeProgramme"] = relationship(
        "DegreeProgramme", back_populates="curriculum_versions"
    )
    branch: Mapped[Optional["ProgrammeBranch"]] = relationship(
        "ProgrammeBranch", back_populates="curriculum_versions"
    )
    subject_entries: Mapped[List["CurriculumSubjectEntry"]] = relationship(
        "CurriculumSubjectEntry", back_populates="curriculum_version", cascade="all, delete-orphan"
    )


class AcademicYear(Base):
    """Institutional academic year cycle (e.g. 2025-2026)."""
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_academic_year_code"),
        CheckConstraint("ends_on >= starts_on", name="chk_academic_year_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # planning | active | completed | archived

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    terms: Mapped[List["AcademicTerm"]] = relationship(
        "AcademicTerm", back_populates="academic_year", cascade="all, delete-orphan"
    )


class AcademicTerm(Base):
    """Operational semester or term schedule (e.g. Autumn 2025 / Odd Semester)."""
    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint("institution_id", "academic_year_id", "term_code", name="uq_academic_term_code"),
        CheckConstraint("ends_on >= starts_on", name="chk_academic_term_dates"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True
    )
    term_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    term_sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # planning | active | completed | archived

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear", back_populates="terms"
    )
    course_offerings: Mapped[List["CourseOffering"]] = relationship(
        "CourseOffering", back_populates="academic_term"
    )


class SubjectCategory(Base):
    """Configurable subject category taxonomy (PC, PE, OE, MC, LAB, etc.)."""
    __tablename__ = "subject_categories"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_subject_category_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    curriculum_entries: Mapped[List["CurriculumSubjectEntry"]] = relationship(
        "CurriculumSubjectEntry", back_populates="subject_category"
    )


class CanonicalSubject(Base):
    """
    Institution-wide canonical subject identity in the central catalog.
    Exists independently of specific curriculum versions and degree schemes.
    """
    __tablename__ = "canonical_subjects"
    __table_args__ = (
        UniqueConstraint("institution_id", "canonical_code", name="uq_canonical_subject_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owning_academic_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | inactive | retired

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    owning_academic_unit: Mapped[Optional["AcademicUnit"]] = relationship(
        "AcademicUnit", back_populates="canonical_subjects"
    )
    curriculum_entries: Mapped[List["CurriculumSubjectEntry"]] = relationship(
        "CurriculumSubjectEntry", back_populates="canonical_subject"
    )


class CurriculumSubjectEntry(Base):
    """
    Inclusion of a Canonical Subject in a Curriculum Version.
    Binds official subject code, semester, credits, L/T/P, and mark scheme.
    """
    __tablename__ = "curriculum_subject_entries"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "curriculum_version_id",
            "official_subject_code",
            name="uq_curriculum_official_subject_code",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("curriculum_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_subject_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("canonical_subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject_category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("subject_categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    official_subject_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name_override: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    semester_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    credits: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    lecture_hours_per_week: Mapped[float] = mapped_column(Numeric(4, 1), default=0.0, nullable=False)
    tutorial_hours_per_week: Mapped[float] = mapped_column(Numeric(4, 1), default=0.0, nullable=False)
    practical_hours_per_week: Mapped[float] = mapped_column(Numeric(4, 1), default=0.0, nullable=False)
    marks_scheme_status: Mapped[str] = mapped_column(
        String(20), default="not_configured", nullable=False
    )  # not_configured | configured | verified
    marks_scheme_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsible_academic_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    curriculum_version: Mapped["CurriculumVersion"] = relationship(
        "CurriculumVersion", back_populates="subject_entries"
    )
    canonical_subject: Mapped["CanonicalSubject"] = relationship(
        "CanonicalSubject", back_populates="curriculum_entries"
    )
    subject_category: Mapped["SubjectCategory"] = relationship(
        "SubjectCategory", back_populates="curriculum_entries"
    )
    responsible_academic_unit: Mapped[Optional["AcademicUnit"]] = relationship("AcademicUnit")
    mark_components: Mapped[List["CurriculumSubjectMarkComponent"]] = relationship(
        "CurriculumSubjectMarkComponent", back_populates="curriculum_subject_entry", cascade="all, delete-orphan"
    )
    course_offerings: Mapped[List["CourseOffering"]] = relationship(
        "CourseOffering", back_populates="curriculum_subject_entry"
    )


class CurriculumSubjectMarkComponent(Base):
    """Structured evaluation breakdown (IA, End Exam, Practical, etc.)."""
    __tablename__ = "curriculum_subject_mark_components"
    __table_args__ = (
        UniqueConstraint(
            "curriculum_subject_entry_id", "component_code", name="uq_curriculum_mark_component_code"
        ),
        CheckConstraint("maximum_marks >= 0", name="chk_mark_comp_max_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    curriculum_subject_entry_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("curriculum_subject_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_code: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    assessment_kind: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # internal_assessment | end_semester | continuous_lab | practical_exam | other
    maximum_marks: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    weight_percent: Mapped[Optional[float]] = mapped_column(Numeric(6, 3), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    curriculum_subject_entry: Mapped["CurriculumSubjectEntry"] = relationship(
        "CurriculumSubjectEntry", back_populates="mark_components"
    )


class FacultyDesignation(Base):
    """Configurable faculty titles (Professor, Associate Professor, Assistant Professor, etc.)."""
    __tablename__ = "faculty_designations"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_faculty_designation_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FacultyAppointment(Base):
    """Academic department affiliation over time."""
    __tablename__ = "faculty_appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_unit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    designation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("faculty_designations.id", ondelete="RESTRICT"), nullable=False
    )
    appointment_type: Mapped[str] = mapped_column(
        String(30), default="permanent", nullable=False
    )  # permanent | visiting | adjunct | contract
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    academic_unit: Mapped["AcademicUnit"] = relationship("AcademicUnit")
    designation: Mapped["FacultyDesignation"] = relationship("FacultyDesignation")


class FacultyProfile(Base):
    """Institutional faculty member profile details."""
    __tablename__ = "faculty_profiles"

    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    employee_identifier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    profile_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StudentProfile(Base):
    """Institutional student profile details."""
    __tablename__ = "student_profiles"

    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    profile_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StudentProgrammeEnrolment(Base):
    """Student admission and programme progression record."""
    __tablename__ = "student_programme_enrolments"
    __table_args__ = (
        UniqueConstraint("institution_id", "registration_number", name="uq_student_prog_registration_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    degree_programme_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("degree_programmes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    programme_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("programme_branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    curriculum_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("curriculum_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    admission_route: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    cohort_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | completed | withdrawn | transferred | suspended
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    degree_programme: Mapped["DegreeProgramme"] = relationship("DegreeProgramme")
    programme_branch: Mapped[Optional["ProgrammeBranch"]] = relationship("ProgrammeBranch")
    curriculum_version: Mapped[Optional["CurriculumVersion"]] = relationship("CurriculumVersion")
    semester_history: Mapped[List["StudentSemesterHistory"]] = relationship(
        "StudentSemesterHistory", back_populates="student_programme_enrolment", cascade="all, delete-orphan"
    )
    course_enrolments: Mapped[List["CourseOfferingEnrolment"]] = relationship(
        "CourseOfferingEnrolment", back_populates="student_programme_enrolment"
    )


class StudentSemesterHistory(Base):
    """Historical record of student terms/semesters attended."""
    __tablename__ = "student_semester_history"
    __table_args__ = (
        UniqueConstraint(
            "student_programme_enrolment_id", "academic_term_id", name="uq_student_term_history"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_programme_enrolment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("student_programme_enrolments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # planned | active | completed | interrupted | withdrawn
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student_programme_enrolment: Mapped["StudentProgrammeEnrolment"] = relationship(
        "StudentProgrammeEnrolment", back_populates="semester_history"
    )
    academic_term: Mapped["AcademicTerm"] = relationship("AcademicTerm")


class CourseOffering(Base):
    """
    Delivery instance of a Curriculum Subject Entry in a specific academic term and section.
    Delivering unit may differ from the subject's owning unit.
    """
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "curriculum_subject_entry_id",
            "academic_term_id",
            "section_code",
            name="uq_course_offering_delivery",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    curriculum_subject_entry_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("curriculum_subject_entries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_terms.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    delivering_academic_unit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("academic_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    section_code: Mapped[str] = mapped_column(String(20), default="A", nullable=False)
    cohort_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivery_mode: Mapped[str] = mapped_column(
        String(20), default="in_person", nullable=False
    )  # in_person | online | hybrid | other
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # draft | active | completed | cancelled | archived
    starts_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ends_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    curriculum_subject_entry: Mapped["CurriculumSubjectEntry"] = relationship(
        "CurriculumSubjectEntry", back_populates="course_offerings"
    )
    academic_term: Mapped["AcademicTerm"] = relationship(
        "AcademicTerm", back_populates="course_offerings"
    )
    delivering_academic_unit: Mapped["AcademicUnit"] = relationship(
        "AcademicUnit", back_populates="delivering_offerings"
    )
    faculty_assignments: Mapped[List["CourseOfferingFaculty"]] = relationship(
        "CourseOfferingFaculty", back_populates="offering", cascade="all, delete-orphan"
    )
    enrolments: Mapped[List["CourseOfferingEnrolment"]] = relationship(
        "CourseOfferingEnrolment", back_populates="offering", cascade="all, delete-orphan"
    )


class CourseOfferingFaculty(Base):
    """
    Teacher assignment binding a faculty member to a Course Offering.
    Cross-department assignments are permitted.
    """
    __tablename__ = "course_offering_faculty"
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id",
            "institution_membership_id",
            "assignment_role",
            name="uq_course_offering_faculty_assignment",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    faculty_appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("faculty_appointments.id", ondelete="SET NULL"), nullable=True
    )
    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_role: Mapped[str] = mapped_column(
        String(30), default="primary_instructor", nullable=False
    )  # primary_instructor | co_instructor | teaching_assistant | content_curator | grader
    can_manage_content: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | ended | revoked
    assigned_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offering: Mapped["CourseOffering"] = relationship(
        "CourseOffering", back_populates="faculty_assignments"
    )
    membership: Mapped["app.modules.auth.models.InstitutionMembership"] = relationship("app.modules.auth.models.InstitutionMembership")


class CourseOfferingEnrolment(Base):
    """
    Student course enrolment record.
    Admin-managed only; self-enrolment is strictly out of scope for v1.
    """
    __tablename__ = "course_offering_enrolments"
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id",
            "student_programme_enrolment_id",
            name="uq_course_offering_student_enrolment",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_programme_enrolment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("student_programme_enrolments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    institution_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    enrolment_status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | completed | withdrawn | suspended
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    offering: Mapped["CourseOffering"] = relationship(
        "CourseOffering", back_populates="enrolments"
    )
    student_programme_enrolment: Mapped["StudentProgrammeEnrolment"] = relationship(
        "StudentProgrammeEnrolment", back_populates="course_enrolments"
    )
    membership: Mapped["app.modules.auth.models.InstitutionMembership"] = relationship("app.modules.auth.models.InstitutionMembership")

