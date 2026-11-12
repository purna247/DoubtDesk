import React, { useState } from 'react';
import { X, Paperclip, ChevronDown } from 'lucide-react';
export interface AskDoubtSubmission {
  question: string;
  courseOfferingId: string;
  isAnonymousToPeers: boolean;
}

export interface AskDoubtSubject {
  offeringId: string;
  subjectCode?: string | null;
  subjectName?: string | null;
  sectionCode?: string | null;
}

interface AskDoubtModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmitDoubt: (doubt: AskDoubtSubmission) => void;
  subjects: AskDoubtSubject[];
}

export const AskDoubtModal: React.FC<AskDoubtModalProps> = ({
  isOpen,
  onClose,
  onSubmitDoubt,
  subjects,
}) => {
  const [question, setQuestion] = useState('');
  const [courseOfferingId, setCourseOfferingId] = useState('');
  const [isAnonymousToPeers, setIsAnonymousToPeers] = useState(false);

  React.useEffect(() => {
    if (!subjects.some((subject) => subject.offeringId === courseOfferingId)) {
      setCourseOfferingId(subjects[0]?.offeringId ?? '');
    }
  }, [subjects, courseOfferingId]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    if (!courseOfferingId) return;
    onSubmitDoubt({ question: question.trim(), courseOfferingId, isAnonymousToPeers });

    setQuestion('');
    setIsAnonymousToPeers(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-[20px] border border-[#DCE7EE] shadow-2xl max-w-[620px] w-full p-6 sm:p-7 relative">
        {/* Header matching screenshot */}
        <div className="flex items-center justify-between pb-4">
          <h2 className="text-lg sm:text-[20px] font-bold text-[#111111] tracking-tight">
            Ask a question about your assignment
          </h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[#71808C] hover:text-[#111111] hover:bg-[#EDF4F8] transition cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Single Question Input Box matching screenshot */}
          <div className="rounded-[16px] bg-[#EDF4F8]/70 border border-[#DCE7EE]/60 p-4 sm:p-5 mb-5 focus-within:bg-white focus-within:border-[#0A8FF5]/50 focus-within:ring-4 focus-within:ring-[#0A8FF5]/10 transition-all">
            <textarea
              required
              rows={6}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Write your question here (Keep it simple and clear to get the best answer)"
              className="w-full bg-transparent border-none text-[15px] sm:text-[16px] text-[#111111] placeholder-[#637381] focus:outline-none resize-none leading-relaxed"
            />

            {/* Formatting Toolbar: √x, Ω, paperclip */}
            <div className="flex items-center gap-4 pt-3 border-t border-[#DCE7EE]/50 text-[#4D5963]">
              <button
                type="button"
                onClick={() => setQuestion((prev) => prev + ' √x ')}
                className="text-base font-bold hover:text-[#0A8FF5] transition cursor-pointer px-1 py-0.5 rounded"
                title="Insert math formula"
              >
                √x
              </button>
              <button
                type="button"
                onClick={() => setQuestion((prev) => prev + ' Ω ')}
                className="text-base font-bold hover:text-[#0A8FF5] transition cursor-pointer px-1 py-0.5 rounded"
                title="Insert symbol"
              >
                Ω
              </button>
              <button
                type="button"
                className="hover:text-[#0A8FF5] transition cursor-pointer p-0.5 rounded"
                title="Attach file"
              >
                <Paperclip className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Course selection, anonymity, and submit controls */}
          <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto] items-end gap-4 pt-1">
            <div className="flex min-w-0 flex-col items-start gap-3">
              <div className="relative w-full min-w-0">
                <select
                  value={courseOfferingId}
                  onChange={(e) => setCourseOfferingId(e.target.value)}
                  aria-label="Enrolled course"
                  className="h-10 w-full max-w-full truncate pl-3.5 pr-8 rounded-full bg-[#EDF4F8] hover:bg-[#E3EDF3] text-xs sm:text-sm font-semibold text-[#111111] appearance-none border-none cursor-pointer focus:outline-none transition"
                >
                  {subjects.length === 0 && <option value="">No enrolled courses found</option>}
                  {subjects.map((subject) => <option key={subject.offeringId} value={subject.offeringId}>
                    {[subject.subjectCode, subject.subjectName, subject.sectionCode && `Section ${subject.sectionCode}`].filter(Boolean).join(' · ')}
                  </option>)}
                </select>
                <ChevronDown className="w-4 h-4 text-[#61717D] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>

              <label className="flex items-center gap-2 text-xs font-medium text-[#4D5963]">
                <input type="checkbox" checked={isAnonymousToPeers} onChange={(event) => setIsAnonymousToPeers(event.target.checked)} className="h-4 w-4 accent-[#0A8FF5]" />
                Ask anonymously to other students
              </label>

            </div>

            <button
              type="submit"
              disabled={!question.trim() || !courseOfferingId || subjects.length === 0}
              className="h-11 w-full sm:w-auto px-6 rounded-full bg-[#050505] hover:bg-[#1A1A1A] disabled:opacity-40 text-white font-extrabold text-xs sm:text-sm tracking-wide transition cursor-pointer whitespace-nowrap shadow-sm"
            >
              ASK YOUR QUESTION
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
