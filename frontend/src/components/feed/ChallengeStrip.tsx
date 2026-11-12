import React from 'react';
import { Clock, LayoutGrid } from 'lucide-react';

interface ChallengeStripProps {
  onChallengeClick: () => void;
}

export const ChallengeStrip: React.FC<ChallengeStripProps> = ({ onChallengeClick }) => {
  return (
    <div className="border border-[#DCE7EE] rounded-[14px] bg-white p-5 sm:p-6 mb-5">
      {/* Top Header: Icon + Goal */}
      <div className="flex items-center gap-3.5 mb-4">
        <div className="w-10 h-10 rounded-2xl bg-[#FFEFEF] border border-[#FFD8D8] flex items-center justify-center shrink-0">
          <LayoutGrid className="w-5 h-5 text-[#E64980]" />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm sm:text-base font-bold text-[#111111]">
            Answer 5 questions from any subject to get
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#111111] text-white text-xs font-bold shrink-0">
            <span>50 pts</span>
          </span>
        </div>
      </div>

      {/* Bottom Progress Row */}
      <div className="flex items-center gap-4 sm:gap-6 flex-wrap sm:flex-nowrap">
        {/* Progress count */}
        <div className="flex items-center gap-1.5 text-xs font-bold text-[#71808C] shrink-0">
          <span className="text-sm">▦</span>
          <span>1/5</span>
        </div>

        {/* Progress bar */}
        <div className="flex-1 min-w-[120px] h-2 rounded-full bg-[#EBF0F5] overflow-hidden">
          <div
            className="h-full bg-[#0A8FF5] rounded-full transition-all duration-300"
            style={{ width: '20%' }}
          />
        </div>

        {/* Time remaining */}
        <div className="flex items-center gap-1.5 text-xs text-[#71808C] font-semibold shrink-0">
          <Clock className="w-3.5 h-3.5" />
          <span>2d : 00h</span>
        </div>

        {/* Brainly Start Pill Button */}
        <button
          onClick={onChallengeClick}
          className="h-9 px-6 rounded-full border border-[#111111] hover:bg-[#111111] hover:text-white text-[#111111] font-extrabold text-xs tracking-wider uppercase transition cursor-pointer shrink-0"
        >
          Start
        </button>
      </div>
    </div>
  );
};

