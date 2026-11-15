import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import type { CourseOffering } from '../types/academics';
import type { EnrolledSubjectItem } from '../components/layout/DesktopSidebar';

export const toSubjectItems = (offerings: CourseOffering[]): EnrolledSubjectItem[] => {
  const subjects = new Map<string, EnrolledSubjectItem>();
  for (const offering of offerings) {
    const id = offering.curriculum_subject_entry_id;
    const code = offering.official_subject_code?.trim() ?? '';
    const name = offering.subject_name?.trim() || code;
    if (id && name && !subjects.has(id)) {
      subjects.set(id, { id, code, name });
    }
  }
  return [...subjects.values()];
};

export const useAcademicOfferings = (role?: string | null) => {
  const [offerings, setOfferings] = useState<CourseOffering[]>([]);
  const [enrolledSubjects, setEnrolledSubjects] = useState<EnrolledSubjectItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchOfferings = useCallback(async () => {
    setIsLoading(true);
    const endpoint =
      role === 'TEACHER'
        ? '/api/v1/academics/teacher/offerings'
        : role === 'STUDENT'
        ? '/api/v1/academics/student/offerings'
        : null;

    if (!endpoint) {
      setOfferings([]);
      setEnrolledSubjects([]);
      setIsLoading(false);
      return;
    }

    try {
      const rows = await apiClient.get<CourseOffering[]>(endpoint);
      const list = Array.isArray(rows) ? rows : [];
      setOfferings(list);
      setEnrolledSubjects(toSubjectItems(list));
    } catch {
      setOfferings([]);
      setEnrolledSubjects([]);
    } finally {
      setIsLoading(false);
    }
  }, [role]);

  useEffect(() => {
    fetchOfferings();
  }, [fetchOfferings]);

  return { offerings, enrolledSubjects, isLoading, refetchOfferings: fetchOfferings };
};
