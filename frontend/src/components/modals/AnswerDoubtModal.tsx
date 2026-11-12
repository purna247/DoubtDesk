import React, { useState } from 'react';
import { X, Send, Award, CheckCircle2 } from 'lucide-react';
import { DoubtItem } from '../../data/doubtsData';

interface AnswerDoubtModalProps {
  doubt: DoubtItem | null;
  onClose: () => void;
  onSubmitAnswer: (doubtId: string, answerText: string) => void;
}

export const AnswerDoubtModal: React.FC<AnswerDoubtModalProps> = ({
  doubt,
  onClose,
  onSubmitAnswer
}) => {
  const [answerText, setAnswerText] = useState('');

  if (!doubt) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!answerText.trim()) return;

    onSubmitAnswer(doubt.id, answerText.trim());
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl border border-[#DCE7EE] shadow-2xl max-w-lg w-full p-6 relative">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-[#71808C] hover:text-[#111111] p-1.5 rounded-full hover:bg-[#EDF4F8] transition"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#E7F7EF] flex items-center justify-center text-[#22A06B]">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-[#111111]">Write an Answer</h3>
            <p className="text-xs text-[#71808C]">
              Earn +{doubt.rewardPoints} points and help a fellow student
            </p>
          </div>
        </div>

        {/* Question Preview Box */}
        <div className="p-3.5 rounded-xl bg-[#F7FAFC] border border-[#E8EFF3] mb-4">
          <span className="text-[11px] font-bold text-[#0A8FF5] block mb-1">
            Question by {doubt.studentName}:
          </span>
          <p className="text-sm font-semibold text-[#111111] line-clamp-2">
            {doubt.doubtQuestion}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-[#111111] mb-1.5">
              Your Detailed Solution <span className="text-[#E52521]">*</span>
            </label>
            <textarea
              required
              rows={6}
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="Provide a step-by-step breakdown with clear points and explanations..."
              className="w-full p-3.5 rounded-xl bg-[#EDF4F8] border border-transparent text-sm text-[#111111] placeholder-[#71808C] focus:bg-white focus:border-[#0A8FF5] focus:outline-none resize-none leading-relaxed"
            />
          </div>

          <div className="p-3 rounded-xl bg-[#FFF9E6] border border-[#F5D36C] text-xs text-[#7C5E00] flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#D49E00] shrink-0" />
            <span>High-quality, well-structured solutions get verified by course teachers.</span>
          </div>

          <div className="pt-3 border-t border-[#E8EFF3] flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 rounded-full text-xs font-semibold text-[#4D5963] hover:bg-[#EDF4F8] transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!answerText.trim()}
              className="btn-primary text-xs py-2.5 px-6 disabled:opacity-40"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Submit Answer</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
