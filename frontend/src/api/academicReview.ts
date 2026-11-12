import { apiClient } from './client';

export interface AcademicExtractionJob {
  job_id: string;
  status: 'queued' | 'running' | 'retrying';
  already_queued: boolean;
}

export const startAcademicExtraction = (offeringId: string) =>
  apiClient.post<AcademicExtractionJob>(`/api/v1/courses/${offeringId}/academic-review/process`, {});
