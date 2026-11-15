import React from 'react';
import { ChevronDown } from 'lucide-react';

interface FeedFiltersProps {
  currentFilter: string;
  onFilterChange: (filter: string) => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
  totalCount: number;
}

export const FeedFilters: React.FC<FeedFiltersProps> = ({
  currentFilter,
  onFilterChange,
  sortBy,
  onSortChange
}) => {
  return (
    <div className="flex items-center justify-between gap-3 mb-5">
      {/* Brainly Clean Dropdown Filter Pills */}
      <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap">
        {/* All levels dropdown pill */}
        <div className="relative inline-flex items-center">
          <select
            defaultValue="all"
            className="h-10 pl-4 pr-9 rounded-full bg-[#EBF2F7] hover:bg-[#E2ECF2] text-[#111111] text-xs sm:text-[13px] font-bold border-none cursor-pointer focus:outline-none appearance-none transition-colors"
          >
            <option value="all">All levels</option>
            <option value="beginner">1st & 2nd Year (Core)</option>
            <option value="advanced">3rd & 4th Year (Advanced)</option>
          </select>
          <ChevronDown className="w-4 h-4 text-[#4D5963] absolute right-3 pointer-events-none" />
        </div>

        {/* Status dropdown pill (Unanswered / All / Verified) */}
        <div className="relative inline-flex items-center">
          <select
            value={currentFilter}
            onChange={(e) => onFilterChange(e.target.value)}
            className="h-10 pl-4 pr-9 rounded-full bg-[#EBF2F7] hover:bg-[#E2ECF2] text-[#111111] text-xs sm:text-[13px] font-bold border-none cursor-pointer focus:outline-none appearance-none transition-colors"
          >
            <option value="all">All questions</option>
            <option value="unanswered">Unanswered</option>
            <option value="needs_verification">Pending Verification</option>
            <option value="verified">Verified by Teacher</option>
            <option value="bookmarked">Saved / Bookmarked</option>
          </select>
          <ChevronDown className="w-4 h-4 text-[#4D5963] absolute right-3 pointer-events-none" />
        </div>
      </div>

      {/* Sort pill dropdown */}
      <div className="relative inline-flex items-center">
        <select
          value={sortBy}
          onChange={(e) => onSortChange(e.target.value)}
          className="h-10 pl-4 pr-8 rounded-full bg-[#F4F7F9] hover:bg-[#EBF0F3] text-[#4D5963] text-xs font-semibold border-none cursor-pointer focus:outline-none appearance-none transition-colors"
        >
          <option value="helpful">Most Helpful</option>
          <option value="recent">Most Recent</option>
          <option value="points">Highest Points</option>
        </select>
        <ChevronDown className="w-3.5 h-3.5 text-[#71808C] absolute right-2.5 pointer-events-none" />
      </div>
    </div>
  );
};

