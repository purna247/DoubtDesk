import { apiClient } from './client';
import type { LearningNode } from '../types/learning';

export interface FlaggedItem { kind: string; label: string; confidence?: number; source_chunk_ids?: string[] }
export interface FlaggedBatch { id: string; stage: string; message?: string; item_count: number; source_chunk_count: number; items: FlaggedItem[] }
export interface ConceptOption { id: string; canonical_name: string }
export interface ReviewSummary {
  course_content_version_id?: string | null;
  run_status: string;
  generation_status: string;
  generation_stage?: string | null;
  generation_message?: string | null;
  sources_ready: boolean;
  publish_ready: boolean;
  approved_syllabus_count: number;
  has_warnings: boolean;
  warnings_count: number;
  modules_count: number;
  topics_count: number;
  concepts_count: number;
  approved_concepts_count: number;
  questions_count: number;
  draft_nodes_count: number;
  approved_concepts: ConceptOption[];
  flagged_items: FlaggedBatch[];
}

export interface TeacherLearningWorkspaceData {
  nodes: LearningNode[];
  summary: ReviewSummary;
}

export const getTeacherLearningWorkspace = async (offeringId: string): Promise<TeacherLearningWorkspaceData> => {
  const [nodes, summary] = await Promise.all([
    apiClient.get<LearningNode[]>(`/api/v1/courses/${offeringId}/learning-nodes`),
    apiClient.get<ReviewSummary>(`/api/v1/courses/${offeringId}/academic-review/summary`),
  ]);
  return { nodes: Array.isArray(nodes) ? nodes : [], summary };
};
