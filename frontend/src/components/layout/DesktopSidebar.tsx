import React from 'react';
import {
  LayoutGrid,
  Compass,
} from 'lucide-react';

export interface EnrolledSubjectItem {
  id: string;
  code: string;
  name: string;
}

export interface DesktopSidebarProps {
  selectedSubject?: string;
  onSelectSubject?: (subjectId: string) => void;
  filterMode?: string;
  onSelectFilterMode?: (mode: string) => void;
  activeNavTab?: string;
  enrolledSubjects?: EnrolledSubjectItem[];
}

export const DesktopSidebar: React.FC<DesktopSidebarProps> = ({
  selectedSubject = 'all',
  onSelectSubject = () => {},
  enrolledSubjects = [],
}) => {
  return (
    <aside className="w-[190px] xl:w-[210px] 2xl:w-[220px] shrink-0 hidden md:block">
      <div>
        <h2 className="text-[15px] font-extrabold text-[#111111] mb-3 px-3">
          Subjects
        </h2>

        <div className="flex flex-col gap-0.5">
          {/* All Subjects */}
          <button
            onClick={() => onSelectSubject('all')}
            className={`flex items-center gap-3 w-full h-[42px] px-3 rounded-full transition-colors cursor-pointer text-left ${
              selectedSubject === 'all'
                ? 'bg-[#EBF2F7] text-[#111111] font-bold'
                : 'text-[#1A1A1A] hover:bg-[#F4F7F9] font-medium'
            }`}
          >
            <LayoutGrid className="w-4 h-4 text-[#111111] shrink-0" />
            <span className="text-[13px] xl:text-[14px]">All subjects</span>
          </button>

          {/* Individual Subject Items */}
          {enrolledSubjects.map((subject) => {
            const isActive = selectedSubject === subject.id;
            return (
              <button
                key={subject.id}
                onClick={() => onSelectSubject(subject.id)}
                className={`flex items-center gap-3 w-full h-[40px] px-3 rounded-full transition-colors cursor-pointer text-left ${
                  isActive
                    ? 'bg-[#EBF2F7] text-[#111111] font-bold'
                    : 'text-[#2D3748] hover:bg-[#F4F7F9] font-medium'
                }`}
              >
                <Compass className="w-4 h-4 text-[#111111] shrink-0" />
                <span className="text-[13px] xl:text-[14px] truncate">{subject.name}</span>
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
};
