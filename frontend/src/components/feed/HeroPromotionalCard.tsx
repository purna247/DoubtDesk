import React from 'react';

interface HeroPromotionalCardProps {
  onOpenAskModal: () => void;
  studentsOnlineCount?: number;
}

export const HeroPromotionalCard: React.FC<HeroPromotionalCardProps> = ({
  onOpenAskModal,
  studentsOnlineCount = 1842,
}) => {
  return (
    <div className="hero-card border border-[#DCE7EE] rounded-[14px] bg-white p-5 sm:p-7 lg:p-8 mb-5 relative">
      <div className="w-full">
        {/* Brainly style top tag badge */}
        <div className="flex items-center gap-2 mb-3.5">
          <div className="w-6 h-6 rounded-full bg-[#EBF4FC] flex items-center justify-center text-sm shadow-xs">
            🧠
          </div>
          <span className="text-xs sm:text-sm font-bold text-[#111111]">
            DoubtDesk <span className="text-[#71808C] font-normal">· Answerer</span>
          </span>
          <span className="text-slate-300 hidden sm:inline" aria-hidden="true">·</span>
          <div className="hidden sm:inline-flex items-center gap-1.5 text-xs text-[#18754E] font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22A06B] animate-pulse shrink-0" />
            <span className="text-[#4D5963]"><strong className="text-[#111111]">{studentsOnlineCount.toLocaleString()}</strong> students active</span>
          </div>
        </div>

        {/* Hero heading */}
        <h1 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-[#111111] leading-[1.1] tracking-tight mb-6">
          Get Answers for FREE
        </h1>

        {/* Primary Black CTA Button (Brainly clean style) */}
        <div>
          <button
            onClick={onOpenAskModal}
            className="h-[46px] px-8 rounded-full bg-[#050505] hover:bg-[#1A1A1A] text-white font-extrabold text-xs sm:text-sm tracking-wide uppercase inline-flex items-center gap-2 transition transform hover:-translate-y-0.5 cursor-pointer shadow-sm whitespace-nowrap"
          >
            <span>Ask Your Question</span>
          </button>
        </div>
      </div>
    </div>
  );
};
