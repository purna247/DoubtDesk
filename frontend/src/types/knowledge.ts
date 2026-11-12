export interface CourseContentVersion {
  id: string;
  institution_id: string;
  course_offering_id: string;
  version_number: number;
  status: 'draft' | 'in_review' | 'approved' | 'published' | 'superseded' | 'archived';
  created_by_user_id?: string;
  reviewed_by_user_id?: string;
  approved_at?: string;
  published_at?: string;
  change_summary?: string;
  created_at: string;
  updated_at: string;
}

export interface LearningObjective {
  id: string;
  institution_id: string;
  course_content_version_id: string;
  syllabus_node_id?: string;
  concept_id?: string;
  objective_code: string;
  description: string;
  bloom_level: 'remember' | 'understand' | 'apply' | 'analyze' | 'evaluate' | 'create';
  sequence_no: number;
  created_at: string;
}

export interface SyllabusNode {
  id: string;
  institution_id: string;
  course_content_version_id: string;
  parent_node_id?: string;
  node_type: 'module' | 'topic' | 'subtopic';
  title: string;
  description?: string;
  sequence_no: number;
  source_chunk_id?: string;
  review_status: 'extracted' | 'needs_review' | 'approved' | 'rejected';
  created_at: string;
  updated_at: string;
}

export interface SyllabusNodeTree extends SyllabusNode {
  children: SyllabusNodeTree[];
  learning_objectives: LearningObjective[];
}

export interface ConceptVersion {
  id: string;
  institution_id: string;
  concept_id: string;
  version_number: number;
  definition: string;
  explanation?: string;
  review_status: 'provisional' | 'teacher_approved' | 'rejected';
  created_by_user_id?: string;
  approved_by_user_id?: string;
  approved_at?: string;
  created_at: string;
}

export interface Concept {
  id: string;
  institution_id: string;
  concept_code?: string;
  canonical_name: string;
  status: 'active' | 'retired';
  created_at: string;
  updated_at: string;
  latest_version?: ConceptVersion;
}

export interface ConceptSummary {
  id: string;
  concept_code?: string;
  canonical_name: string;
  definition: string;
  importance_weight?: number;
}

export interface SyllabusTreeResponse {
  version: CourseContentVersion;
  nodes: SyllabusNodeTree[];
  concepts: ConceptSummary[];
}

