/**
 * DoubtDesk Academic Doubts, Discussion & Peer Learning Types
 */

export interface AuthorPublic {
  user_id?: string | null;
  display_name: string;
  avatar_url?: string | null;
  role_label: string;
  is_anonymous: boolean;
}

export interface DoubtComment {
  id: string;
  doubt_id: string;
  answer_id?: string | null;
  author: AuthorPublic;
  body_markdown: string;
  created_at: string;
}

export interface DoubtAnswer {
  id: string;
  doubt_id: string;
  author: AuthorPublic;
  body_markdown: string;
  is_teacher_verified: boolean;
  verified_at?: string | null;
  upvote_count: number;
  created_at: string;
  comments: DoubtComment[];
}

export interface Doubt {
  id: string;
  institution_id: string;
  course_offering_id?: string | null;
  canonical_subject_id?: string | null;
  concept_id?: string | null;
  concept_name?: string | null;
  title: string;
  body_markdown: string;
  is_anonymous_to_peers: boolean;
  author: AuthorPublic;
  status: 'open' | 'answered' | 'resolved' | 'archived' | 'removed';
  visibility: 'institution' | 'course' | 'restricted';
  upvote_count: number;
  answer_count: number;
  created_at: string;
  updated_at: string;
  answers: DoubtAnswer[];
  comments: DoubtComment[];
}

export interface DoubtCreatePayload {
  course_offering_id?: string | null;
  canonical_subject_id?: string | null;
  concept_id?: string | null;
  question_id?: string | null;
  title: string;
  body_markdown: string;
  is_anonymous_to_peers?: boolean;
  visibility?: 'institution' | 'course' | 'restricted';
}

export interface DoubtAnswerCreatePayload {
  body_markdown: string;
}

export interface DoubtCommentCreatePayload {
  answer_id?: string | null;
  body_markdown: string;
}

export interface DoubtFlag {
  id: string;
  doubt_id: string;
  reported_by_user_id: string;
  reason_code: string;
  details?: string | null;
  status: 'open' | 'reviewing' | 'actioned' | 'dismissed';
  created_at: string;
}

export interface DoubtFlagCreatePayload {
  reason_code: string;
  details?: string | null;
}

export interface DoubtUnmaskRequest {
  reason_code: string;
  reason_text: string;
}

export interface DoubtUnmaskResult {
  doubt_id: string;
  author_user_id: string;
  author_display_name: string;
  author_email?: string | null;
  disclosed_at: string;
  audit_event_id?: string | null;
}

