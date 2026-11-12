export interface AcademicUnit {
  id: string;
  institution_id: string;
  parent_unit_id?: string | null;
  unit_type: string;
  code?: string | null;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface CanonicalSubject {
  id: string;
  institution_id: string;
  owning_academic_unit_id?: string | null;
  canonical_code?: string | null;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
}

export interface CurriculumSubjectEntry {
  id: string;
  institution_id: string;
  curriculum_version_id: string;
  canonical_subject_id: string;
  subject_category_id: string;
  official_subject_code: string;
  display_name_override?: string | null;
  semester_number: number;
  credits?: number | null;
  lecture_hours_per_week: number;
  tutorial_hours_per_week: number;
  practical_hours_per_week: number;
  marks_scheme_status: string;
  is_active: boolean;
  created_at: string;
  canonical_name?: string | null;
}

export interface CourseOffering {
  id: string;
  institution_id: string;
  curriculum_subject_entry_id: string;
  academic_term_id: string;
  delivering_academic_unit_id: string;
  section_code: string;
  cohort_label?: string | null;
  delivery_mode: string;
  status: string;
  created_at: string;
  official_subject_code?: string | null;
  subject_name?: string | null;
  term_code?: string | null;
  delivering_unit_name?: string | null;
}
