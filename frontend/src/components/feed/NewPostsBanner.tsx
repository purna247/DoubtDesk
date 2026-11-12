import React from 'react';
import { ArrowUp } from 'lucide-react';

export interface PendingAuthor {
  name: string;
  avatar: string;
}

interface NewPostsBannerProps {
  pendingCount: number;
  authors: PendingAuthor[];
  onShowNewPosts: () => void;
}

export const NewPostsBanner: React.FC<NewPostsBannerProps> = ({
  pendingCount,
  authors,
  onShowNewPosts
}) => {
  if (pendingCount <= 0) return null;

  return (
    <div className="sticky top-[120px] z-30 flex justify-center py-1 mb-4 pointer-events-none animate-in fade-in slide-in-from-top-3 duration-300">
      <button
        onClick={onShowNewPosts}
        className="pointer-events-auto inline-flex items-center gap-2.5 px-4 sm:px-5 py-2 rounded-full bg-white border border-[#DCE7EE] shadow-md hover:shadow-lg hover:border-[#0A8FF5]/40 text-[#111111] transition-all transform hover:-translate-y-0.5 active:scale-95 cursor-pointer group"
      >
        {/* Twitter/X style overlapping profile icons */}
        <div className="flex items-center -space-x-2 shrink-0">
          {authors.slice(0, 3).map((author, index) => (
            <img
              key={index}
              src={author.avatar}
              alt={author.name}
              className="w-6 h-6 rounded-full border-2 border-white object-cover shadow-xs ring-1 ring-black/5"
            />
          ))}
        </div>

        {/* Text */}
        <span className="text-xs sm:text-[13px] font-bold text-[#111111] group-hover:text-[#0A8FF5] transition-colors">
          Show {pendingCount} new {pendingCount === 1 ? 'doubt' : 'doubts'}
        </span>

        {/* Twitter style up arrow */}
        <div className="w-5 h-5 rounded-full bg-[#EBF4FC] flex items-center justify-center text-[#0A8FF5] group-hover:bg-[#0A8FF5] group-hover:text-white transition-colors">
          <ArrowUp className="w-3 h-3 stroke-[2.5]" />
        </div>
      </button>
    </div>
  );
};
