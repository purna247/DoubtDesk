export type InterventionStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'published'
  | 'active'
  | 'completed'
  | 'archived'
  | 'cancelled';

export type PhaseBCompletionRule =
  | 'all_required_items'
  | 'designated_core_items'
  | 'minimum_count';

export interface InterventionConcept {
  concept_id: string;
  canonical_name?: string | null;
  concept_code?: string | null;
  target_notes?: string | null;
}

export interface Intervention {
  id: string;
  institution_id: string;
  course_offering_id: string;
  title: string;
  description?: string | null;
  status: InterventionStatus;
  phase_a_assessment_id?: string | null;
  phase_b_primer_content?: string | null;
  phase_b_practice_assessment_id?: string | null;
  phase_b_completion_rule: PhaseBCompletionRule;
  phase_b_required_count?: number | null;
  phase_c_assessment_id?: string | null;
  approved_at?: string | null;
  published_at?: string | null;
  created_at: string;
  updated_at: string;
  target_concepts: InterventionConcept[];
  assigned_students_count: number;
}

export interface InterventionAssignment {
  id: string;
  intervention_id: string;
  student_membership_id: string;
  student_name?: string | null;
  target_evidence_status: string;
  assignment_status: string;
  phase_a_completed_at?: string | null;
  phase_a_score?: number | null;
  phase_b_completed_at?: string | null;
  phase_b_items_completed_count: number;
  phase_c_completed_at?: string | null;
  phase_c_score?: number | null;
  observed_score_change?: number | null;
  outcome_status?: 'improved' | 'unchanged' | 'declined' | 'incomplete' | null;
  assigned_at: string;
}

export interface StudentInterventionView {
  intervention_id: string;
  title: string;
  description?: string | null;
  current_phase: 'phase_a' | 'phase_b' | 'phase_c' | 'completed';
  phase_a_unlocked: boolean;
  phase_a_completed: boolean;
  phase_a_assessment_id?: string | null;
  phase_a_score?: number | null;
  phase_b_unlocked: boolean;
  phase_b_completed: boolean;
  phase_b_primer_content?: string | null;
  phase_b_practice_assessment_id?: string | null;
  phase_b_items_completed: number;
  phase_b_rule_description: string;
  phase_c_unlocked: boolean;
  phase_c_completed: boolean;
  phase_c_assessment_id?: string | null;
  phase_c_score?: number | null;
  observed_score_change?: number | null;
  outcome_status?: 'improved' | 'unchanged' | 'declined' | 'incomplete' | null;
}

export interface InterventionReport {
  intervention_id: string;
  title: string;
  status: InterventionStatus;
  total_assigned_count: number;
  phase_a_completed_count: number;
  phase_b_completed_count: number;
  phase_c_completed_count: number;
  matched_completed_count: number;
  improved_count: number;
  unchanged_count: number;
  declined_count: number;
  incomplete_count: number;
  average_phase_a_score?: number | null;
  average_phase_c_score?: number | null;
  average_observed_change?: number | null;
  disclaimer: string;
  assignments: InterventionAssignment[];
}

