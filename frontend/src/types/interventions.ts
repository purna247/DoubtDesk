import type { CourseOffering } from './academics';

export interface StudentInterventionNextAction {
  action_kind:
    | 'start_baseline'
    | 'resume_baseline'
    | 'open_guide'
    | 'acknowledge_guide'
    | 'start_practice'
    | 'resume_practice'
    | 'start_reassessment'
    | 'resume_reassessment'
    | 'view_results'
    | 'retry_progress'
    | 'unavailable';
  intervention_id: string;
  course_offering_id: string;
  assessment_id?: string | null;
  attempt_id?: string | null;
  label: string;
  availability_reason?: string | null;
}

export interface StudentIntervention {
  intervention_id: string;
  title: string;
  description?: string | null;
  current_phase: string;
  phase_a_unlocked: boolean;
  phase_a_completed: boolean;
  phase_a_assessment_id?: string | null;
  phase_a_score?: number | null;
  phase_b_unlocked: boolean;
  phase_b_completed: boolean;
  phase_b_primer_acknowledged: boolean;
  require_primer_acknowledgment: boolean;
  phase_b_primer_content?: string | null;
  phase_b_practice_assessment_id?: string | null;
  phase_b_items_completed: number;
  phase_b_rule_description: string;
  phase_c_unlocked: boolean;
  phase_c_completed: boolean;
  phase_c_assessment_id?: string | null;
  phase_c_score?: number | null;
  observed_score_change?: number | null;
  outcome_status?: string | null;

  baseline_attempt_state?: 'not_started' | 'in_progress' | 'submitted' | 'expired' | 'unavailable';
  baseline_attempt_id?: string | null;
  practice_attempt_state?: string | null;
  practice_attempt_id?: string | null;
  reassessment_attempt_state?: string | null;
  reassessment_attempt_id?: string | null;
  next_action?: StudentInterventionNextAction | null;
  availability_reason?: string | null;

  offering?: CourseOffering;
}

export interface MetricSummary {
  status: 'available' | 'no_content' | 'partial' | 'unsupported';
  reason?: string | null;
  completed_count?: number | null;
  attempted_count?: number | null;
  eligible_count?: number | null;
  correct_count?: number | null;
  percentage?: number | null;
}

export interface RemainingSupportSummary {
  active_count: number;
  completed_count: number;
  status: string;
}

export interface ContinueLearningSummary {
  title: string;
  concept_name?: string | null;
  course_name?: string | null;
  action_kind: string;
  action_label: string;
  destination_url: string;
}

export interface CourseProgressSummary {
  course_offering_id: string;
  curriculum_subject_entry_id: string;
  subject_code: string;
  subject_name: string;
  learning_topics: MetricSummary;
  teacher_material_practice: MetricSummary;
  remaining_support: RemainingSupportSummary;
  catalog_revision?: number | null;
}

export interface StudentProgressSummaryResponse {
  learning_topics: MetricSummary;
  teacher_material_practice: MetricSummary;
  remaining_support: RemainingSupportSummary;
  continue_learning?: ContinueLearningSummary | null;
  per_offering: CourseProgressSummary[];
  updated_at: string;
}
