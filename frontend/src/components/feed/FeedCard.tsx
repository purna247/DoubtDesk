import React, { useState } from 'react';
import {
  MoreVertical,
  Share2,
  Bookmark,
  CheckCircle2
} from 'lucide-react';
import { DoubtItem } from '../../data/doubtsData';

interface FeedCardProps {
  doubt: DoubtItem;
  onSelectDoubt?: (doubtId: string) => void;
  onAnswerDoubt: (doubtId: string) => void;
  onToggleBookmark: (doubtId: string) => void;
  onAddComment?: (doubtId: string, answerId: string, commentText: string) => void;
  onToggleThanks?: (doubtId: string, answerId: string) => void;
  onShowToast: (message: string) => void;
}

export const FeedCard: React.FC<FeedCardProps> = ({
  doubt,
  onSelectDoubt,
  onAnswerDoubt,
  onToggleBookmark,
  onShowToast
}) => {
  const [showMenu, setShowMenu] = useState(false);

  const hasAnswers = doubt.answers.length > 0;
  const isVerified = doubt.answers.some((a) => a.isVerifiedByTeacher);

  const handleCopyLink = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard?.writeText(window.location.href);
    onShowToast('Link copied to clipboard!');
    setShowMenu(false);
  };

  return (
    <article
      onClick={() => onSelectDoubt && onSelectDoubt(doubt.id)}
      className="feed-card border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-6 mb-4 hover:border-[#B8D0E0] transition-colors cursor-pointer"
    >
      {/* 1. Header: Avatar + Subject & Time on left, Points badge on right */}
      <div className="flex items-center justify-between gap-3 mb-3.5">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full overflow-hidden bg-slate-100 border border-[#DCE7EE] shrink-0">
            {doubt.studentAvatar ? (
              <img
                src={doubt.studentAvatar}
                alt={doubt.studentName}
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <span className="w-full h-full flex items-center justify-center text-xs font-bold text-slate-500" aria-label={doubt.studentName}>
                {doubt.studentName.trim().slice(0, 1).toUpperCase() || '?'}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-xs text-[#71808C] truncate">
            <span className="font-semibold text-[#111111]">{doubt.studentName}</span>
            <span aria-hidden="true" className="text-slate-300">·</span>
            <span>{doubt.askedAt}</span>
          </div>
        </div>
      </div>

      {/* 2. Question Text (Brainly clean typography) */}
      <div className="mb-5">
        {doubt.syllabusNodeTitle && (
          <div className="mb-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200/60 px-2.5 py-0.5 text-[11px] font-semibold text-[#0A8FF5]">
              Topic: {doubt.syllabusNodeTitle}
            </span>
          </div>
        )}
        <h2 className="text-[17px] sm:text-[18px] font-bold text-[#111111] leading-snug tracking-tight">
          {doubt.doubtQuestion}
        </h2>
      </div>

      {/* 3. Footer Action Strip (Brainly: status on left, ⋮ and ANSWER button on right) */}
      <div className="flex items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2 text-xs text-[#71808C]">
          {isVerified ? (
            <span className="inline-flex items-center gap-1 text-[#18754E] font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#22A06B]" />
              Verified solution
            </span>
          ) : hasAnswers ? (
            <span className="text-[#4D5963] font-medium">
              {doubt.answers.length} {doubt.answers.length === 1 ? 'answer' : 'answers'}
            </span>
          ) : (
            <span className="text-[#8898A6]">Not answered yet</span>
          )}
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {/* Three dots options menu */}
          <div className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowMenu(!showMenu);
              }}
              className="w-8 h-8 rounded-full flex items-center justify-center text-[#71808C] hover:text-[#111111] hover:bg-[#EDF4F8] transition cursor-pointer"
              aria-label="More options"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
            {showMenu && (
              <div className="absolute right-0 bottom-full mb-1 w-44 bg-white rounded-xl border border-[#DCE7EE] shadow-lg z-20 py-1.5 text-xs text-[#4D5963]">
                <button
                  onClick={handleCopyLink}
                  className="w-full text-left px-3 py-2 hover:bg-[#EDF4F8] hover:text-[#111111] transition flex items-center gap-2 cursor-pointer"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Copy Question Link</span>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleBookmark(doubt.id);
                    setShowMenu(false);
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-[#EDF4F8] hover:text-[#111111] transition flex items-center gap-2 cursor-pointer"
                >
                  <Bookmark className="w-3.5 h-3.5" />
                  <span>{doubt.isBookmarked ? 'Remove Bookmark' : 'Save Question'}</span>
                </button>
              </div>
            )}
          </div>

          {/* Brainly Outline ANSWER / SEE ANSWER Pill Button */}
          {hasAnswers ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (onSelectDoubt) onSelectDoubt(doubt.id);
              }}
              className="h-9 px-6 rounded-full border border-[#111111] hover:bg-[#111111] hover:text-white text-[#111111] font-extrabold text-xs tracking-wider uppercase transition cursor-pointer"
            >
              See Answer
            </button>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onAnswerDoubt(doubt.id);
              }}
              className="h-9 px-6 rounded-full border border-[#111111] hover:bg-[#111111] hover:text-white text-[#111111] font-extrabold text-xs tracking-wider uppercase transition cursor-pointer"
            >
              Answer
            </button>
          )}
        </div>
      </div>
    </article>
  );
};
