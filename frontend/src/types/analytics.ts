export type DiagnosticStatus =
  | 'insufficient_evidence'
  | 'candidate_weakness'
  | 'confirmed_weakness'
  | 'not_currently_flagged_as_weak';

export interface CourseAnalyticsPolicy {
  id: string;
  institution_id: string;
  course_offering_id?: string | null;
  min_distinct_questions: number;
  weakness_accuracy_threshold: number;
  diagnostic_attempt_policy: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CohortConceptAnalytics {
  concept_id: string;
  concept_code?: string | null;
  concept_name?: string | null;
  enrolled_count: number;
  assessed_count: number;
  confirmed_weak_count: number;
  candidate_weak_count: number;
  insufficient_evidence_count: number;
  cohort_mean_accuracy?: number | null;
  cohort_pooled_accuracy?: number | null;
  tagged_misconception_count: number;
  computed_at: string;
}

export interface SupportingQuestionEvidence {
  item_id: string;
  question_or_activity_id?: string | null;
  assessment_id: string;
  assessment_title: string;
  attempt_id: string;
  attempt_number: number;
  submitted_at: string;
  marks_awarded: number;
  marks_available: number;
  is_diagnostic: boolean;
}

export interface StudentConceptDetail {
  student_membership_id: string;
  student_name?: string | null;
  student_reg_number?: string | null;
  concept_id: string;
  concept_name?: string | null;
  distinct_question_count: number;
  awarded_marks: number;
  available_marks: number;
  accuracy?: number | null;
  diagnostic_status: DiagnosticStatus;
  computed_at: string;
  supporting_evidence: SupportingQuestionEvidence[];
}

export interface ConceptAnalyticsDetail {
  concept: CohortConceptAnalytics;
  policy: CourseAnalyticsPolicy;
  students: StudentConceptDetail[];
}

export interface MisconceptionFrequencyItem {
  misconception_id: string;
  code: string;
  description: string;
  concept_id: string;
  concept_title?: string | null;
  occurrence_count: number;
}

export interface MisconceptionReport {
  course_offering_id: string;
  total_events: number;
  misconceptions: MisconceptionFrequencyItem[];
}

export interface ConceptMasteryPolicy {
  id: string;
  institution_id: string;
  course_offering_id: string;
  policy_name: string;
  criteria_json: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

