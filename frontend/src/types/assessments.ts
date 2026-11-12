export type AssessmentType =
  | 'node_practice'
  | 'boss'
  | 'intervention_baseline'
  | 'intervention_practice'
  | 'intervention_post';

export type ResponseState = 'empty' | 'draft' | 'answered' | 'marked_for_review';
export type AttemptStatus = 'in_progress' | 'submitted' | 'expired' | 'abandoned';
export type ScoringStatus = 'not_scored' | 'scoring_pending' | 'scored' | 'manual_review_required';

export interface ConceptAllocation {
  concept_id: string;
  marks_available: number;
}

export interface AssessmentItem {
  id: string;
  sequence_no: number;
  marks_available: number;
  is_required: boolean;
  question_version_id?: string | null;
  activity_version_id?: string | null;
  activity_type?: string | null;
  title?: string | null;
  student_payload_json?: Record<string, unknown> | null;
  answer_key_json?: Record<string, unknown> | null;
  question_prompt?: string | null;
  question_parts?: { id: string; part_key: string; part_prompt: string; marks_available: number; answer_type: string; options: { id: string; option_key: string; display_text: string }[] }[];
  concept_allocations: ConceptAllocation[];
}

export interface AssessmentVersion {
  id: string;
  assessment_id: string;
  version_number: number;
  status: string;
  duration_seconds?: number | null;
  max_attempts?: number | null;
  published_at?: string | null;
  created_at: string;
  items: AssessmentItem[];
}

export interface Assessment {
  id: string;
  institution_id: string;
  course_offering_id: string;
  learning_node_id?: string | null;
  assessment_type: AssessmentType;
  title: string;
  description?: string | null;
  status: string;
  created_at: string;
  latest_version?: AssessmentVersion | null;
}

export interface StartAttemptResponse {
  attempt_id: string;
  assessment_version_id: string;
  attempt_number: number;
  status: AttemptStatus;
  started_at: string;
  expires_at?: string | null;
  duration_seconds?: number | null;
  items: AssessmentItem[];
  saved_responses: Record<string, Record<string, unknown>>;
}

export interface SaveResponseRequest {
  item_id: string;
  response_payload: Record<string, unknown>;
  response_state?: ResponseState;
  client_event_id?: string | null;
}

export interface ItemScore {
  item_id: string;
  sequence_no: number;
  marks_awarded: number;
  marks_available: number;
  result_status: string;
  selected_option_id?: string | null;
  correct_option_id?: string | null;
  explanation?: string | null;
}

export interface QuizQuestionInput {
  statement: string;
  options: string[];
  correct_index: number;
  explanation?: string;
  marks: number;
  source_chunk_ids?: string[];
  concept_ids?: string[];
  origin_type?: 'teacher_authored' | 'ai_supplementary';
}

export interface QuizAiGenerateResponse {
  title: string;
  description: string;
  questions: QuizQuestionInput[];
  sources: {
    source_document_id: string;
    source_chunk_id: string;
    filename: string;
    page_number?: number | null;
    slide_number?: number | null;
  }[];
}

export interface ConceptScore {
  concept_id: string;
  marks_awarded: number;
  marks_available: number;
}

export interface AttemptSummary {
  attempt_id: string;
  assessment_version_id: string;
  attempt_number: number;
  status: AttemptStatus;
  scoring_status: ScoringStatus;
  is_valid: boolean;
  started_at: string;
  expires_at?: string | null;
  submitted_at?: string | null;
  finalized_at?: string | null;
  marks_awarded?: number | null;
  marks_available?: number | null;
  score_fraction?: number | null;
  item_scores: ItemScore[];
  concept_scores: ConceptScore[];
}

