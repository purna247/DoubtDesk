export interface Option {
  id: string;
  option_key: string;
  display_text: string;
  sequence_no: number;
  is_correct: boolean;
  misconception_id?: string;
}

export interface ConceptAllocation {
  id: string;
  question_part_id: string;
  concept_id: string;
  allocated_marks: number;
  allocation_note?: string;
}

export interface QuestionPart {
  id: string;
  part_key: string;
  part_prompt: string;
  sequence_no: number;
  marks_available: number;
  answer_type: 'mcq' | 'fill_blank' | 'matching_pairs' | 'ordering' | 'classification' | 'key_points_check' | 'descriptive';
  expected_answer_depth?: string;
  options: Option[];
  concept_allocations: ConceptAllocation[];
}

export interface QuestionVersion {
  id: string;
  institution_id: string;
  question_id: string;
  version_number: number;
  prompt_text: string;
  question_type: string;
  command_verb?: string;
  expected_answer_depth?: string;
  marks_total: number;
  difficulty_level: 'very_easy' | 'easy' | 'medium' | 'hard' | 'very_hard' | 'unrated';
  cognitive_level?: 'remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create';
  approval_status: 'draft' | 'pending_review' | 'approved' | 'rejected' | 'superseded';
  created_by_user_id?: string;
  reviewed_by_user_id?: string;
  reviewed_at?: string;
  rejection_reason?: string;
  marking_guidance?: string;
  created_at: string;
  parts: QuestionPart[];
}

export interface Question {
  id: string;
  institution_id: string;
  created_by_user_id?: string;
  origin_type: 'original_exam' | 'teacher_authored' | 'imported' | 'ai_supplementary';
  lifecycle_status: 'draft' | 'pending_review' | 'approved' | 'rejected' | 'archived';
  is_ai_generated: boolean;
  created_at: string;
  updated_at: string;
  latest_version?: QuestionVersion;
}

export interface QuestionRelationship {
  id: string;
  institution_id: string;
  source_question_id: string;
  target_question_id: string;
  relationship_type: 'related' | 'possible_near_duplicate' | 'variant_of' | 'broader_requirement' | 'narrower_requirement' | 'prerequisite_for' | 'same_learning_objective';
  confidence?: number;
  review_status: string;
  created_at: string;
}

export interface CourseQuestionCoverageReport {
  course_offering_id: string;
  total_questions: number;
  extracted_count: number;
  concept_mapped_count: number;
  approved_count: number;
  assessment_included_count: number;
}

