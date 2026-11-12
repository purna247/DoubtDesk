import { useMutation, useQueryClient } from '@tanstack/react-query';
import { startAcademicExtraction } from '../api/academicReview';

export const useStartAcademicExtraction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: startAcademicExtraction,
    onSuccess: (_result, offeringId) => queryClient.invalidateQueries({ queryKey: ['teacher-learning-workspace', offeringId] }),
  });
};
