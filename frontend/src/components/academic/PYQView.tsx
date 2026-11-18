import React from 'react';
import { BookMarked, Filter, HelpCircle } from 'lucide-react';
import { EmptyStateCard } from '../ui/EmptyStateCard';
import { SUBJECTS_LIST } from '../../data/doubtsData';

interface PYQViewProps {
  selectedSubject?: string;
}

export const PYQView: React.FC<PYQViewProps> = ({ selectedSubject = 'all' }) => {
  const activeSubjectLabel = SUBJECTS_LIST.find((s) => s.id === selectedSubject)?.name;

  return (
    <div className="space-y-6">
      {/* Subject Filter Banner */}
      {activeSubjectLabel && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#EAF5FF] border border-[#B8D9F5]">
          <Filter className="w-3.5 h-3.5 text-[#0A8FF5] shrink-0" />
          <span className="text-xs font-semibold text-[#0A8FF5]">Filtered by subject:</span>
          <span className="text-xs font-bold text-[#111111]">{activeSubjectLabel}</span>
        </div>
      )}

      {/* Empty State: No PYQs Uploaded Yet */}
      <EmptyStateCard
        icon={BookMarked}
        title="No Previous Year Papers Archived Yet"
        badgeIcon={HelpCircle}
        badgeText="Exam archive currently empty for this subject"
      />
    </div>
  );
};
