import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import type { MisconceptionReport } from '../types/analytics';

export const useCourseMisconceptions = (offeringId: string) => useQuery({
  queryKey: ['course-misconceptions', offeringId],
  queryFn: () => apiClient.get<MisconceptionReport>(`/api/v1/courses/${offeringId}/analytics/misconceptions`),
  enabled: Boolean(offeringId),
});
