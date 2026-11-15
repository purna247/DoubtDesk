import React, { useState, useEffect } from 'react';
import { X, Paperclip, ChevronDown } from 'lucide-react';
import { apiClient } from '../../api/client';

export interface AskDoubtSubmission {
  question: string;
  courseOfferingId: string;
  syllabusNodeId?: string;
  isAnonymousToPeers: boolean;
}

export interface AskDoubtSubject {
  offeringId: string;
  subjectCode?: string | null;
  subjectName?: string | null;
  sectionCode?: string | null;
}

interface SyllabusTopicOption {
  id: string;
  title: string;
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
  const [syllabusNodeId, setSyllabusNodeId] = useState('');
  const [topics, setTopics] = useState<SyllabusTopicOption[]>([]);
  const [isAnonymousToPeers, setIsAnonymousToPeers] = useState(false);

  useEffect(() => {
    if (!subjects.some((subject) => subject.offeringId === courseOfferingId)) {
      setCourseOfferingId(subjects[0]?.offeringId ?? '');
    }
  }, [subjects, courseOfferingId]);

  // Load syllabus topics whenever the selected course offering changes
  useEffect(() => {
    if (!courseOfferingId) {
      setTopics([]);
      setSyllabusNodeId('');
      return;
    }

    let isMounted = true;
    apiClient
      .get<any>(`/api/v1/courses/${courseOfferingId}/student/syllabus`)
      .then((res) => {
        if (!isMounted) return;
        const flatTopics: SyllabusTopicOption[] = [];
        const traverse = (nodeList: any[]) => {
          for (const node of nodeList || []) {
            if (node.id && node.title) {
              flatTopics.push({ id: String(node.id), title: node.title });
            }
            if (Array.isArray(node.children) && node.children.length > 0) {
              traverse(node.children);
            }
          }
        };
        if (res && Array.isArray(res.nodes)) {
          traverse(res.nodes);
        }
        setTopics(flatTopics);
        setSyllabusNodeId('');
      })
      .catch(() => {
        if (isMounted) {
          setTopics([]);
          setSyllabusNodeId('');
        }
      });

    return () => {
      isMounted = false;
    };
  }, [courseOfferingId]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    if (!courseOfferingId) return;

    onSubmitDoubt({
      question: question.trim(),
      courseOfferingId,
      syllabusNodeId: syllabusNodeId || undefined,
      isAnonymousToPeers,
    });

    setQuestion('');
    setSyllabusNodeId('');
    setIsAnonymousToPeers(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-white rounded-[20px] border border-[#DCE7EE] shadow-2xl max-w-[620px] w-full p-6 sm:p-7 relative">
        {/* Header */}
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
          {/* Question Textarea */}
          <div className="rounded-[16px] bg-[#EDF4F8]/70 border border-[#DCE7EE]/60 p-4 sm:p-5 mb-5 focus-within:bg-white focus-within:border-[#0A8FF5]/50 focus-within:ring-4 focus-within:ring-[#0A8FF5]/10 transition-all">
            <textarea
              required
              rows={6}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Write your question here (Keep it simple and clear to get the best answer)"
              className="w-full bg-transparent border-none text-[15px] sm:text-[16px] text-[#111111] placeholder-[#637381] focus:outline-none resize-none leading-relaxed"
            />

            {/* Formatting Toolbar */}
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

          {/* Controls: Course selector, Optional topic selector, Anonymity, Submit button */}
          <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto] items-end gap-4 pt-1">
            <div className="flex min-w-0 flex-col items-start gap-3 w-full">
              {/* Course Offering Dropdown */}
              <div className="relative w-full min-w-0">
                <select
                  value={courseOfferingId}
                  onChange={(e) => setCourseOfferingId(e.target.value)}
                  aria-label="Enrolled course"
                  className="h-10 w-full max-w-full truncate pl-3.5 pr-8 rounded-full bg-[#EDF4F8] hover:bg-[#E3EDF3] text-xs sm:text-sm font-semibold text-[#111111] appearance-none border-none cursor-pointer focus:outline-none transition"
                >
                  {subjects.length === 0 && <option value="">No enrolled courses found</option>}
                  {subjects.map((subject) => (
                    <option key={subject.offeringId} value={subject.offeringId}>
                      {[subject.subjectCode, subject.subjectName, subject.sectionCode && `Section ${subject.sectionCode}`]
                        .filter(Boolean)
                        .join(' · ')}
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-[#61717D] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>

              {/* Optional Syllabus Topic Dropdown */}
              {topics.length > 0 && (
                <div className="relative w-full min-w-0">
                  <select
                    value={syllabusNodeId}
                    onChange={(e) => setSyllabusNodeId(e.target.value)}
                    aria-label="Syllabus topic (optional)"
                    className="h-10 w-full max-w-full truncate pl-3.5 pr-8 rounded-full bg-[#F0F5FA] hover:bg-[#E6EEF5] text-xs sm:text-sm font-medium text-[#243342] appearance-none border border-[#DCE7EE] cursor-pointer focus:outline-none transition"
                  >
                    <option value="">Topic: Auto-detect / All Topics</option>
                    {topics.map((t) => (
                      <option key={t.id} value={t.id}>
                        Topic: {t.title}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="w-4 h-4 text-[#61717D] absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              )}

              {/* Anonymity Checkbox */}
              <label className="flex items-center gap-2 text-xs font-medium text-[#4D5963] cursor-pointer">
                <input
                  type="checkbox"
                  checked={isAnonymousToPeers}
                  onChange={(event) => setIsAnonymousToPeers(event.target.checked)}
                  className="h-4 w-4 accent-[#0A8FF5] rounded cursor-pointer"
                />
                Ask anonymously to other students
              </label>
            </div>

            {/* Submit Button */}
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
