"""Institutional academics, canonical subjects, curriculum, course offerings and enrolments.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Academic Units
    op.create_table(
        'academic_units',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('unit_type', sa.String(length=40), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_academic_unit_code'),
        sa.CheckConstraint('parent_unit_id IS NULL OR parent_unit_id <> id', name='chk_unit_not_self_parent'),
    )
    op.create_index('ix_academic_units_inst_parent', 'academic_units', ['institution_id', 'parent_unit_id'])

    # 2. Degree Programmes
    op.create_table(
        'degree_programmes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('degree_level', sa.String(length=30), server_default='ug', nullable=False),
        sa.Column('nominal_duration_years', sa.Integer(), server_default='4', nullable=False),
        sa.Column('owning_academic_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_degree_programme_code'),
    )

    # 3. Programme Branches
    op.create_table(
        'programme_branches',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('degree_programme_id', UUID(as_uuid=True), sa.ForeignKey('degree_programmes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'degree_programme_id', 'code', name='uq_programme_branch_code'),
    )

    # 4. Curriculum Versions
    op.create_table(
        'curriculum_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('degree_programme_id', UUID(as_uuid=True), sa.ForeignKey('degree_programmes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('programme_branch_id', UUID(as_uuid=True), sa.ForeignKey('programme_branches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('version_code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('effective_from_admission_year', sa.Integer(), nullable=True),
        sa.Column('effective_to_admission_year', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 5. Academic Years & Terms
    op.create_table(
        'academic_years',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_academic_year_code'),
        sa.CheckConstraint('ends_on >= starts_on', name='chk_academic_year_dates'),
    )

    op.create_table(
        'academic_terms',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('academic_year_id', UUID(as_uuid=True), sa.ForeignKey('academic_years.id', ondelete='CASCADE'), nullable=False),
        sa.Column('term_code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('term_sequence', sa.Integer(), server_default='1', nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'academic_year_id', 'term_code', name='uq_academic_term_code'),
        sa.CheckConstraint('ends_on >= starts_on', name='chk_academic_term_dates'),
    )

    # 6. Subject Categories
    op.create_table(
        'subject_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_subject_category_code'),
    )

    # 7. Canonical Subjects (Catalog)
    op.create_table(
        'canonical_subjects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('owning_academic_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('canonical_code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'canonical_code', name='uq_canonical_subject_code'),
    )

    # 8. Curriculum Subject Entries
    op.create_table(
        'curriculum_subject_entries',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('curriculum_version_id', UUID(as_uuid=True), sa.ForeignKey('curriculum_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('canonical_subject_id', UUID(as_uuid=True), sa.ForeignKey('canonical_subjects.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('subject_category_id', UUID(as_uuid=True), sa.ForeignKey('subject_categories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('official_subject_code', sa.String(length=50), nullable=False),
        sa.Column('display_name_override', sa.Text(), nullable=True),
        sa.Column('semester_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('credits', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('lecture_hours_per_week', sa.Numeric(precision=4, scale=1), server_default='0', nullable=False),
        sa.Column('tutorial_hours_per_week', sa.Numeric(precision=4, scale=1), server_default='0', nullable=False),
        sa.Column('practical_hours_per_week', sa.Numeric(precision=4, scale=1), server_default='0', nullable=False),
        sa.Column('marks_scheme_status', sa.String(length=20), server_default='not_configured', nullable=False),
        sa.Column('marks_scheme_notes', sa.Text(), nullable=True),
        sa.Column('responsible_academic_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'curriculum_version_id', 'official_subject_code', name='uq_curriculum_official_subject_code'),
    )

    # 9. Mark Components
    op.create_table(
        'curriculum_subject_mark_components',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('curriculum_subject_entry_id', UUID(as_uuid=True), sa.ForeignKey('curriculum_subject_entries.id', ondelete='CASCADE'), nullable=False),
        sa.Column('component_code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('assessment_kind', sa.String(length=30), server_default='internal_assessment', nullable=False),
        sa.Column('maximum_marks', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('weight_percent', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('curriculum_subject_entry_id', 'component_code', name='uq_curriculum_mark_component_code'),
        sa.CheckConstraint('maximum_marks >= 0', name='chk_mark_comp_max_positive'),
    )

    # 10. Faculty Designations & Appointments
    op.create_table(
        'faculty_designations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_faculty_designation_code'),
    )

    op.create_table(
        'faculty_appointments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('academic_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='CASCADE'), nullable=False),
        sa.Column('designation_id', UUID(as_uuid=True), sa.ForeignKey('faculty_designations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('appointment_type', sa.String(length=30), server_default='permanent', nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 11. Faculty and Student Profiles
    op.create_table(
        'faculty_profiles',
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('employee_identifier', sa.String(length=50), nullable=True),
        sa.Column('profile_metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'student_profiles',
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('preferred_name', sa.Text(), nullable=True),
        sa.Column('profile_metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 12. Student Programme Enrolments & Semester History
    op.create_table(
        'student_programme_enrolments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('degree_programme_id', UUID(as_uuid=True), sa.ForeignKey('degree_programmes.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('programme_branch_id', UUID(as_uuid=True), sa.ForeignKey('programme_branches.id', ondelete='SET NULL'), nullable=True),
        sa.Column('curriculum_version_id', UUID(as_uuid=True), sa.ForeignKey('curriculum_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('registration_number', sa.String(length=50), nullable=False),
        sa.Column('admission_year', sa.Integer(), nullable=False),
        sa.Column('admission_route', sa.String(length=50), nullable=True),
        sa.Column('cohort_code', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('started_on', sa.Date(), nullable=False),
        sa.Column('ended_on', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'registration_number', name='uq_student_prog_registration_number'),
    )

    op.create_table(
        'student_semester_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_programme_enrolment_id', UUID(as_uuid=True), sa.ForeignKey('student_programme_enrolments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('academic_term_id', UUID(as_uuid=True), sa.ForeignKey('academic_terms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('semester_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('student_programme_enrolment_id', 'academic_term_id', name='uq_student_term_history'),
    )

    # 13. Course Offerings
    op.create_table(
        'course_offerings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('curriculum_subject_entry_id', UUID(as_uuid=True), sa.ForeignKey('curriculum_subject_entries.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('academic_term_id', UUID(as_uuid=True), sa.ForeignKey('academic_terms.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('delivering_academic_unit_id', UUID(as_uuid=True), sa.ForeignKey('academic_units.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('section_code', sa.String(length=20), server_default='A', nullable=False),
        sa.Column('cohort_label', sa.Text(), nullable=True),
        sa.Column('delivery_mode', sa.String(length=20), server_default='in_person', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('starts_at', sa.Date(), nullable=True),
        sa.Column('ends_at', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'curriculum_subject_entry_id', 'academic_term_id', 'section_code', name='uq_course_offering_delivery'),
    )

    # 14. Course Offering Faculty
    op.create_table(
        'course_offering_faculty',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('faculty_appointment_id', UUID(as_uuid=True), sa.ForeignKey('faculty_appointments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assignment_role', sa.String(length=30), server_default='primary_instructor', nullable=False),
        sa.Column('can_manage_content', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('assigned_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('course_offering_id', 'institution_membership_id', 'assignment_role', name='uq_course_offering_faculty_assignment'),
    )

    # 15. Course Offering Enrolments
    op.create_table(
        'course_offering_enrolments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_programme_enrolment_id', UUID(as_uuid=True), sa.ForeignKey('student_programme_enrolments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('section_label', sa.String(length=20), nullable=True),
        sa.Column('enrolment_status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('course_offering_id', 'student_programme_enrolment_id', name='uq_course_offering_student_enrolment'),
    )


def downgrade() -> None:
    op.drop_table('course_offering_enrolments')
    op.drop_table('course_offering_faculty')
    op.drop_table('course_offerings')
    op.drop_table('student_semester_history')
    op.drop_table('student_programme_enrolments')
    op.drop_table('student_profiles')
    op.drop_table('faculty_profiles')
    op.drop_table('faculty_appointments')
    op.drop_table('faculty_designations')
    op.drop_table('curriculum_subject_mark_components')
    op.drop_table('curriculum_subject_entries')
    op.drop_table('canonical_subjects')
    op.drop_table('subject_categories')
    op.drop_table('academic_terms')
    op.drop_table('academic_years')
    op.drop_table('curriculum_versions')
    op.drop_table('programme_branches')
    op.drop_table('degree_programmes')
    op.drop_table('academic_units')

