/**
 * DoubtDesk Security & Workflow Audit Event Types
 */

export interface AuditEventItem {
  id: string;
  institution_id?: string | null;
  actor_user_id?: string | null;
  event_code: string;
  target_type?: string | null;
  target_id?: string | null;
  payload_json?: Record<string, unknown> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

export interface AuditQueryResponse {
  events: AuditEventItem[];
  total_count: number;
}

