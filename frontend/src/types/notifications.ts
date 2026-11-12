/**
 * DoubtDesk In-App Notifications Types
 */

export type NotificationType =
  | 'intervention_assigned'
  | 'phase_unlocked'
  | 'doubt_answered'
  | 'answer_verified'
  | 'moderation_alert'
  | 'system_notice';

export interface NotificationItem {
  id: string;
  institution_id: string;
  user_id: string;
  actor_user_id?: string | null;
  notification_type: NotificationType;
  title: string;
  message: string;
  target_type?: string | null;
  target_id?: string | null;
  is_read: boolean;
  read_at?: string | null;
  created_at: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}

