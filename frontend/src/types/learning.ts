export interface LearningNodePrerequisite {
  id: string;
  learning_node_id: string;
  prerequisite_node_id: string;
  prerequisite_type: 'required' | 'recommended';
  created_at: string;
}

export interface LearningNode {
  id: string;
  institution_id: string;
  course_offering_id: string;
  course_content_version_id: string;
  node_code?: string;
  module_title?: string;
  difficulty_rank?: number;
  title: string;
  description?: string;
  sequence_no: number;
  revision: number;
  status: 'draft' | 'published' | 'archived';
  completion_rule_json?: Record<string, any>;
  created_by_user_id?: string;
  published_at?: string;
  created_at: string;
  updated_at: string;
  concept_ids: string[];
  prerequisite_node_ids: string[];
  is_unlocked?: boolean;
}

export interface ActivityVersion {
  id: string;
  institution_id: string;
  activity_id: string;
  version_number: number;
  activity_type: 'mcq' | 'fill_blank' | 'matching_pairs' | 'ordering' | 'classification' | 'key_points_check';
  schema_version: number;
  title: string;
  instructions?: string;
  student_payload_json: Record<string, any>;
  answer_key_json?: Record<string, any>;
  scoring_config_json: Record<string, any>;
  approval_status: 'draft' | 'approved' | 'rejected' | 'superseded';
  created_at: string;
}

export interface Activity {
  id: string;
  institution_id: string;
  learning_node_id: string;
  question_id?: string;
  status: 'draft' | 'active' | 'archived';
  created_at: string;
  latest_version?: ActivityVersion;
}

export interface ActivityEvaluationResult {
  is_correct: boolean;
  marks_awarded: number;
  max_marks: number;
  percentage: number;
  misconception_hit?: string;
  details: Record<string, any>;
}

export interface CourseLearningMapResponse {
  course_offering_id: string;
  course_content_version_id: string;
  nodes: LearningNode[];
}

