export interface CommentItem {
  id: string;
  author: string;
  avatar: string;
  role: 'Student' | 'Teacher' | 'Moderator';
  text: string;
  createdAt: string;
  likes: number;
}

export interface AnswerItem {
  id: string;
  answeredBy: string;
  authorAvatar: string;
  authorRank: string;
  authorTitle: string;
  content: string;
  points?: {
    title: string;
    description: string;
  }[];
  summary?: string;
  intro?: string;
  isVerifiedByTeacher: boolean;
  teacherName?: string;
  teacherTitle?: string;
  verifiedAt?: string;
  verificationNote?: string;
  thanksCount: number;
  hasThanked?: boolean;
  answeredAt: string;
  comments: CommentItem[];
}

export interface DoubtItem {
  id: string;
  studentName: string;
  studentAvatar: string;
  studentGrade: string;
  subject: string;
  topic: string;
  syllabusNodeId?: string;
  syllabusNodeTitle?: string;
  semanticMetadata?: Record<string, any>;
  askedAt: string;
  createdAtTimestamp?: number;
  rewardPoints: number;
  doubtQuestion: string;
  answers: AnswerItem[];
  viewsCount: number;
  isBookmarked?: boolean;
}

/**
 * Sorts answers so that:
 * 1. Teacher-verified answers ALWAYS appear 1st.
 * 2. Remaining community answers appear below, ordered by helpfulness/thanks.
 */
export function getSortedAnswers(answers: AnswerItem[]): AnswerItem[] {
  return [...answers].sort((a, b) => {
    if (a.isVerifiedByTeacher && !b.isVerifiedByTeacher) return -1;
    if (!a.isVerifiedByTeacher && b.isVerifiedByTeacher) return 1;
    return b.thanksCount - a.thanksCount;
  });
}

export const SUBJECTS_LIST = [
  { id: 'os', name: 'Operating Systems', count: 48 },
  { id: 'c-lang', name: 'C & Systems Programming', count: 35 },
  { id: 'cs', name: 'Computer Science', count: 86 },
  { id: 'dsa', name: 'Data Structures & Algorithms', count: 62 },
  { id: 'networks', name: 'Computer Networks', count: 29 },
  { id: 'dbms', name: 'Database Systems', count: 31 },
  { id: 'math', name: 'Discrete Mathematics', count: 44 },
];
