import { useState, useEffect, useMemo, useCallback } from 'react';
import { apiClient } from '../api/client';
import type { DoubtItem } from '../data/doubtsData';
import type { TeacherDoubtSummary } from '../components/sidebar/RightSidebar';

export const formatApiDate = (value?: string): string => {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
};

export const mapApiDoubt = (d: any): DoubtItem => ({
  id: String(d.id),
  studentName: d.author?.is_anonymous ? 'Anonymous Student' : (d.author?.display_name || 'Student'),
  studentAvatar: d.author?.avatar_url || '',
  studentGrade: d.author?.role_label || '',
  subject: d.concept_name || 'Uncategorized',
  topic: d.title,
  syllabusNodeId: d.syllabus_node_id ? String(d.syllabus_node_id) : undefined,
  syllabusNodeTitle: d.syllabus_node_title || undefined,
  semanticMetadata: d.semantic_metadata || undefined,
  askedAt: formatApiDate(d.created_at),
  createdAtTimestamp: d.created_at ? new Date(d.created_at).getTime() : 0,
  rewardPoints: 0,
  doubtQuestion: d.body_markdown,
  viewsCount: 0,
  isBookmarked: false,
  answers: (d.answers || []).map((a: any) => {
    const isTeacher =
      String(a.author?.role_label || '').toLowerCase().includes('teacher') ||
      Boolean(a.is_teacher_verified) ||
      ['dr.', 'prof.', 'dr ', 'prof '].some((p) => String(a.author?.display_name || '').toLowerCase().startsWith(p));
    const roleLabel = isTeacher ? 'Teacher' : (a.author?.role_label || 'Student');
    return {
      id: String(a.id),
      answeredBy: a.author?.is_anonymous ? 'Anonymous Student' : (a.author?.display_name || 'Community Member'),
      authorAvatar: a.author?.avatar_url || '',
      authorRank: roleLabel,
      authorTitle: (a.is_teacher_verified || isTeacher) ? 'Faculty Verified' : roleLabel,
      content: a.body_markdown,
      isVerifiedByTeacher: Boolean(a.is_teacher_verified || isTeacher),
      thanksCount: a.upvote_count ?? 0,
      hasThanked: Boolean(a.has_thanked),
      answeredAt: formatApiDate(a.created_at),
      comments: (a.comments || []).map((c: any) => {
        const isCommentTeacher =
          String(c.author?.role_label || '').toLowerCase().includes('teacher') ||
          ['dr.', 'prof.', 'dr ', 'prof '].some((p) => String(c.author?.display_name || '').toLowerCase().startsWith(p));
        return {
          id: String(c.id),
          author: c.author?.is_anonymous ? 'Anonymous Student' : (c.author?.display_name || 'Community Member'),
          avatar: c.author?.avatar_url || '',
          role: isCommentTeacher ? 'Teacher' : 'Student',
          text: c.body_markdown,
          createdAt: formatApiDate(c.created_at),
          likes: 0,
        };
      }),
    };
  }),
});

export const useDoubtsFeed = () => {
  const [doubts, setDoubts] = useState<DoubtItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const fetchDoubts = useCallback(async () => {
    try {
      const rows = await apiClient.get<any[]>('/api/v1/doubts');
      setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
      setHasError(false);
    } catch {
      setDoubts([]);
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDoubts();
  }, [fetchDoubts]);

  const teacherDoubtSummary: TeacherDoubtSummary = useMemo(() => {
    const unansweredCount = doubts.filter((d) => d.answers.length === 0).length;
    const pendingVerificationCount = doubts.filter(
      (d) => d.answers.length > 0 && !d.answers.some((a) => a.isVerifiedByTeacher)
    ).length;
    const verifiedCount = doubts.filter((d) => d.answers.some((a) => a.isVerifiedByTeacher)).length;
    return {
      unansweredCount,
      pendingVerificationCount,
      verifiedCount,
      totalCount: doubts.length,
    };
  }, [doubts]);

  const toggleBookmark = useCallback((doubtId: string) => {
    setDoubts((prev) =>
      prev.map((d) => {
        if (d.id === doubtId) {
          return { ...d, isBookmarked: !d.isBookmarked };
        }
        return d;
      })
    );
  }, []);

  const toggleThanks = useCallback(async (doubtId: string, answerId: string) => {
    try {
      await apiClient.post(`/api/v1/doubts/${doubtId}/answers/${answerId}/upvote`);
      setDoubts((prev) =>
        prev.map((d) => {
          if (d.id === doubtId) {
            return {
              ...d,
              answers: d.answers.map((a) => {
                if (a.id === answerId) {
                  const nowThanked = !a.hasThanked;
                  return {
                    ...a,
                    hasThanked: nowThanked,
                    thanksCount: nowThanked ? a.thanksCount + 1 : Math.max(0, a.thanksCount - 1),
                  };
                }
                return a;
              }),
            };
          }
          return d;
        })
      );
    } catch {
      // optimistic rollback if needed
    }
  }, []);

  const addComment = useCallback(async (doubtId: string, answerId: string, commentText: string) => {
    await apiClient.post(`/api/v1/doubts/${doubtId}/comments`, {
      answer_id: answerId,
      body_markdown: commentText,
    });
    const rows = await apiClient.get<any[]>('/api/v1/doubts');
    setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
  }, []);

  const addAnswer = useCallback(async (doubtId: string, answerText: string) => {
    await apiClient.post(`/api/v1/doubts/${doubtId}/answers`, { body_markdown: answerText });
    const rows = await apiClient.get<any[]>('/api/v1/doubts');
    setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
  }, []);

  return {
    doubts,
    setDoubts,
    isLoading,
    hasError,
    teacherDoubtSummary,
    fetchDoubts,
    toggleBookmark,
    toggleThanks,
    addComment,
    addAnswer,
  };
};
