from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ------------------------------------------------------------------------------
# Academic Units
# ------------------------------------------------------------------------------

class AcademicUnitCreate(BaseModel):
    unit_type: str = Field(..., description="school, department, center, etc.")
    name: str = Field(..., min_length=2, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    parent_unit_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class AcademicUnitOut(BaseModel):
    id: str
    institution_id: str
    parent_unit_id: Optional[str] = None
    unit_type: str
    code: Optional[str] = None
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Degree Programmes & Branches
# ------------------------------------------------------------------------------

class DegreeProgrammeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    degree_level: str = Field(default="ug", description="ug | pg | integrated | doctoral | other")
    nominal_duration_years: int = Field(default=4, ge=1, le=10)
    owning_academic_unit_id: Optional[str] = None


class DegreeProgrammeOut(BaseModel):
    id: str
    institution_id: str
    code: str
    name: str
    degree_level: str
    nominal_duration_years: int
    owning_academic_unit_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProgrammeBranchCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)


class ProgrammeBranchOut(BaseModel):
    id: str
    institution_id: str
    degree_programme_id: str
    code: str
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Curriculum Versions
# ------------------------------------------------------------------------------

class CurriculumVersionCreate(BaseModel):
    degree_programme_id: str
    programme_branch_id: Optional[str] = None
    version_code: str = Field(..., min_length=2, max_length=50, description="Scheme identifier, e.g. 2021-scheme")
    display_name: str = Field(..., min_length=2, max_length=200)
    effective_from_admission_year: Optional[int] = None
    effective_to_admission_year: Optional[int] = None


class CurriculumVersionOut(BaseModel):
    id: str
    institution_id: str
    degree_programme_id: str
    programme_branch_id: Optional[str] = None
    version_code: str
    display_name: str
    effective_from_admission_year: Optional[int] = None
    effective_to_admission_year: Optional[int] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Academic Years & Terms
# ------------------------------------------------------------------------------

class AcademicYearCreate(BaseModel):
    code: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    starts_on: date
    ends_on: date


class AcademicYearOut(BaseModel):
    id: str
    institution_id: str
    code: str
    display_name: str
    starts_on: date
    ends_on: date
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AcademicTermCreate(BaseModel):
    academic_year_id: str
    term_code: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    term_sequence: int = Field(default=1)
    starts_on: date
    ends_on: date


class AcademicTermOut(BaseModel):
    id: str
    institution_id: str
    academic_year_id: str
    term_code: str
    display_name: str
    term_sequence: int
    starts_on: date
    ends_on: date
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Subject Categories
# ------------------------------------------------------------------------------

class SubjectCategoryCreate(BaseModel):
    code: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None


class SubjectCategoryOut(BaseModel):
    id: str
    institution_id: str
    code: str
    display_name: str
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Canonical Subjects (Central Catalog)
# ------------------------------------------------------------------------------

class CanonicalSubjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    canonical_code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    owning_academic_unit_id: Optional[str] = None


class CanonicalSubjectOut(BaseModel):
    id: str
    institution_id: str
    owning_academic_unit_id: Optional[str] = None
    canonical_code: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Curriculum Subject Entries
# ------------------------------------------------------------------------------

class MarkComponentIn(BaseModel):
    component_code: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    assessment_kind: str = Field(
        default="internal_assessment",
        description="internal_assessment | end_semester | continuous_lab | practical_exam | other",
    )
    maximum_marks: float = Field(..., ge=0)
    weight_percent: Optional[float] = None
    sequence_no: int = Field(default=1)


class MarkComponentOut(BaseModel):
    id: str
    component_code: str
    display_name: str
    assessment_kind: str
    maximum_marks: float
    weight_percent: Optional[float] = None
    sequence_no: int

    model_config = {"from_attributes": True}


class CurriculumSubjectEntryCreate(BaseModel):
    curriculum_version_id: str
    canonical_subject_id: str
    subject_category_id: str
    official_subject_code: str = Field(..., min_length=1, max_length=50)
    display_name_override: Optional[str] = None
    semester_number: int = Field(default=1, ge=1)
    credits: Optional[float] = None
    lecture_hours_per_week: float = 0.0
    tutorial_hours_per_week: float = 0.0
    practical_hours_per_week: float = 0.0
    responsible_academic_unit_id: Optional[str] = None
    mark_components: Optional[List[MarkComponentIn]] = None


class CurriculumSubjectEntryOut(BaseModel):
    id: str
    institution_id: str
    curriculum_version_id: str
    canonical_subject_id: str
    subject_category_id: str
    official_subject_code: str
    display_name_override: Optional[str] = None
    semester_number: int
    credits: Optional[float] = None
    lecture_hours_per_week: float
    tutorial_hours_per_week: float
    practical_hours_per_week: float
    marks_scheme_status: str
    is_active: bool
    created_at: datetime
    canonical_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Course Offerings
# ------------------------------------------------------------------------------

class CourseOfferingCreate(BaseModel):
    curriculum_subject_entry_id: str
    academic_term_id: str
    delivering_academic_unit_id: str
    section_code: str = Field(default="A", max_length=20)
    cohort_label: Optional[str] = None
    delivery_mode: str = Field(default="in_person", description="in_person | online | hybrid | other")


class CourseOfferingOut(BaseModel):
    id: str
    institution_id: str
    curriculum_subject_entry_id: str
    academic_term_id: str
    delivering_academic_unit_id: str
    section_code: str
    cohort_label: Optional[str] = None
    delivery_mode: str
    status: str
    created_at: datetime
    official_subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    term_code: Optional[str] = None
    delivering_unit_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Faculty Assignments
# ------------------------------------------------------------------------------

class AssignFacultyRequest(BaseModel):
    faculty_membership_id: str
    assignment_role: str = Field(
        default="primary_instructor",
        description="primary_instructor | co_instructor | teaching_assistant | content_curator | grader",
    )
    can_manage_content: bool = True


class CourseOfferingFacultyOut(BaseModel):
    id: str
    course_offering_id: str
    institution_membership_id: str
    faculty_name: Optional[str] = None
    faculty_email: Optional[str] = None
    assignment_role: str
    can_manage_content: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ------------------------------------------------------------------------------
# Student Enrolments
# ------------------------------------------------------------------------------

class EnrolStudentRequest(BaseModel):
    student_membership_id: str
    section_label: Optional[str] = None


class BulkEnrolStudentsRequest(BaseModel):
    student_membership_ids: List[str]
    section_label: Optional[str] = None


class CourseOfferingEnrolmentOut(BaseModel):
    id: str
    course_offering_id: str
    student_membership_id: str
    student_name: Optional[str] = None
    registration_number: Optional[str] = None
    section_label: Optional[str] = None
    enrolment_status: str
    enrolled_at: datetime

    model_config = {"from_attributes": True}

