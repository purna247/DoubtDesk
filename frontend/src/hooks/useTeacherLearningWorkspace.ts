import { useQuery } from '@tanstack/react-query';
import { getTeacherLearningWorkspace } from '../api/teacherLearningWorkspace';

const LIVE_GENERATION_STATES = new Set(['queued', 'running', 'retrying']);

export const useTeacherLearningWorkspace = (offeringId: string) => useQuery({
  queryKey: ['teacher-learning-workspace', offeringId],
  queryFn: () => getTeacherLearningWorkspace(offeringId),
  enabled: Boolean(offeringId),
  refetchInterval: (query) => LIVE_GENERATION_STATES.has(query.state.data?.summary.generation_status ?? '') ? 3000 : false,
});
