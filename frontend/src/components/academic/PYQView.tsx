import React from 'react';
import { BookMarked, Filter, HelpCircle } from 'lucide-react';
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
      <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-10 sm:p-14 text-center">
        <div className="w-14 h-14 rounded-full bg-[#F4F7F9] flex items-center justify-center text-[#71808C] mx-auto mb-4 shadow-xs">
          <BookMarked className="w-7 h-7" />
        </div>
        <h2 className="text-lg font-bold text-[#111111] mb-5">
          No Previous Year Papers Archived Yet
        </h2>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F4F7F9] text-xs font-semibold text-[#4D5963]">
          <HelpCircle className="w-4 h-4 text-[#0A8FF5]" />
          <span>Exam archive currently empty for this subject</span>
        </div>
      </div>
    </div>
  );
};
