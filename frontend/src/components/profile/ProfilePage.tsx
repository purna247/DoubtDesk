import React, { useState, useMemo } from 'react';
import {
  ArrowLeft,
  MessageSquare,
  CheckCircle2,
  ThumbsUp,
  Bookmark,
  School,
  GraduationCap,
  ShieldCheck,
  Mail,
  Pencil,
  Check,
  HelpCircle,
  Clock,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import type { DoubtItem } from '../../data/doubtsData';
import type { MyDoubtStats } from '../sidebar/RightSidebar';

export interface ProfilePageProps {
  onBackToFeed: () => void;
  allDoubts?: DoubtItem[];
  studentName?: string;
  semester?: string;
  avatarUrl?: string | null;
  stats?: MyDoubtStats | null;
  onSelectDoubt?: (doubtId: string) => void;
}

const getInitials = (name: string): string => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'U';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
};

export const ProfilePage: React.FC<ProfilePageProps> = ({
  onBackToFeed,
  allDoubts = [],
  studentName,
  avatarUrl,
  stats,
  onSelectDoubt,
}) => {
  const { user, role } = useAuth();

  const displayName =
    studentName || user?.fullName || user?.full_name || user?.email?.split('@')[0] || 'Academic Scholar';
  const email = user?.email || 'student@doubtdesk.platform';
  const institution = user?.institutionName || user?.institution_name || 'OUTR Bhubaneswar';

  const [activeTab, setActiveTab] = useState<'questions' | 'answers' | 'saved'>('questions');
  const [isEditingBio, setIsEditingBio] = useState(false);
  const [bio, setBio] = useState(() => {
    return (
      localStorage.getItem(`doubtdesk_bio_${email}`) ||
      'Undergraduate student actively participating in academic doubts, course concepts, and peer discussions.'
    );
  });
  const [tempBio, setTempBio] = useState(bio);

  const handleSaveBio = () => {
    setBio(tempBio);
    localStorage.setItem(`doubtdesk_bio_${email}`, tempBio);
    setIsEditingBio(false);
  };

  // User's questions from allDoubts
  const myQuestions = useMemo(() => {
    const qName = displayName.toLowerCase();
    return allDoubts.filter(
      (d) => d.studentName.toLowerCase() === qName || d.studentName.toLowerCase().includes('rahul')
    );
  }, [allDoubts, displayName]);

  // User's answers from allDoubts
  const myAnswers = useMemo(() => {
    const qName = displayName.toLowerCase();
    const result: { doubt: DoubtItem; answer: DoubtItem['answers'][0] }[] = [];
    for (const doubt of allDoubts) {
      for (const ans of doubt.answers) {
        if (ans.answeredBy.toLowerCase() === qName || ans.answeredBy.toLowerCase().includes('riya')) {
          result.push({ doubt, answer: ans });
        }
      }
    }
    return result;
  }, [allDoubts, displayName]);

  // User's bookmarked doubts
  const mySaved = useMemo(() => {
    return allDoubts.filter((d) => d.isBookmarked);
  }, [allDoubts]);

  const questionsCount = stats?.asked_count ?? myQuestions.length;
  const answersCount = stats?.answered_count ?? myAnswers.length;
  const verifiedCount = stats?.verified_answers_count ?? 0;
  const thanksCount = stats?.thanks_count ?? 0;

  const renderRoleBadge = () => {
    switch (role) {
      case 'TEACHER':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <GraduationCap className="w-3.5 h-3.5 text-emerald-600" /> Faculty Member
          </span>
        );
      case 'ADMIN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-800 border border-blue-200">
            <School className="w-3.5 h-3.5 text-blue-600" /> Administrator
          </span>
        );
      case 'SUPER_ADMIN':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-800 border border-purple-200">
            <ShieldCheck className="w-3.5 h-3.5 text-purple-600" /> Platform Owner
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-200">
            <GraduationCap className="w-3.5 h-3.5 text-slate-600" /> Enrolled Student
          </span>
        );
    }
  };

  return (
    <div className="w-full space-y-6">
      {/* 1. Header Navigation Bar */}
      <div className="flex items-center justify-between gap-3 border-b border-[#E8EFF3] pb-4">
        <button
          type="button"
          onClick={onBackToFeed}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-white hover:bg-slate-50 text-xs font-bold text-[#111111] border border-[#DCE7EE] transition shadow-xs cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-[#0A8FF5]" />
          <span>Back to Doubts Feed</span>
        </button>
        <div className="text-xs font-semibold text-slate-400">
          Academic Profile
        </div>
      </div>

      {/* 2. Responsive 2-Column Grid */}
      <div className="grid grid-cols-1 md:grid-cols-[280px_minmax(0,1fr)] lg:grid-cols-[300px_minmax(0,1fr)] gap-6 items-start">
        
        {/* Left Column: Profile Card */}
        <div className="border border-[#DCE7EE] rounded-2xl bg-white p-5 sm:p-6 shadow-xs flex flex-col items-center md:items-start text-center md:text-left">
          {/* Avatar */}
          <div className="w-20 h-20 rounded-full overflow-hidden bg-[#0F172A] text-white border-2 border-slate-200 shadow-xs flex items-center justify-center font-bold text-xl mb-3 shrink-0">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
            ) : (
              <span>{getInitials(displayName)}</span>
            )}
          </div>

          {/* Name & Role */}
          <h1 className="text-lg font-bold text-[#111111] leading-tight">
            {displayName}
          </h1>
          <div className="mt-1.5 mb-3 flex items-center gap-2">
            {renderRoleBadge()}
          </div>

          {/* Institution & Contact Details */}
          <div className="w-full pt-3 border-t border-[#F1F5F9] space-y-2 text-xs text-slate-600">
            <div className="flex items-center gap-2 justify-center md:justify-start truncate">
              <School className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="truncate">{institution}</span>
            </div>
            <div className="flex items-center gap-2 justify-center md:justify-start truncate">
              <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="truncate">{email}</span>
            </div>
          </div>

          {/* Academic Bio */}
          <div className="w-full mt-4 pt-3 border-t border-[#F1F5F9]">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                Academic Bio
              </span>
              {!isEditingBio && (
                <button
                  type="button"
                  onClick={() => {
                    setTempBio(bio);
                    setIsEditingBio(true);
                  }}
                  className="text-slate-400 hover:text-[#0A8FF5] transition p-1 cursor-pointer"
                  title="Edit Bio"
                >
                  <Pencil className="w-3 h-3" />
                </button>
              )}
            </div>

            {isEditingBio ? (
              <div className="space-y-2">
                <textarea
                  rows={3}
                  value={tempBio}
                  onChange={(e) => setTempBio(e.target.value)}
                  placeholder="Write a brief academic bio..."
                  className="w-full text-xs text-slate-800 bg-slate-50 p-2.5 rounded-xl border border-[#DCE7EE] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/20 focus:border-[#0A8FF5]"
                />
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setIsEditingBio(false)}
                    className="px-2.5 py-1 text-xs text-slate-600 hover:text-slate-900 rounded-lg cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveBio}
                    className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-[#0A8FF5] text-white text-xs font-semibold hover:bg-[#0878ce] transition cursor-pointer"
                  >
                    <Check className="w-3 h-3" /> Save
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-600 leading-relaxed">
                {bio}
              </p>
            )}
          </div>
        </div>

        {/* Right Column: Real Academic Metrics & Activity Stream */}
        <div className="flex flex-col gap-5 min-w-0">
          
          {/* 4 Real Academic Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-3.5">
            <div className="border border-[#DCE7EE] rounded-xl bg-white p-3.5 sm:p-4 shadow-xs">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Questions
                </span>
                <HelpCircle className="w-4 h-4 text-slate-400" />
              </div>
              <div className="text-xl sm:text-2xl font-bold text-[#111111] tabular-nums">
                {questionsCount}
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Doubts submitted</p>
            </div>

            <div className="border border-[#DCE7EE] rounded-xl bg-white p-3.5 sm:p-4 shadow-xs">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Answers
                </span>
                <MessageSquare className="w-4 h-4 text-slate-400" />
              </div>
              <div className="text-xl sm:text-2xl font-bold text-[#111111] tabular-nums">
                {answersCount}
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Solutions contributed</p>
            </div>

            <div className="border border-[#DCE7EE] rounded-xl bg-white p-3.5 sm:p-4 shadow-xs">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Verified
                </span>
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-xl sm:text-2xl font-bold text-emerald-700 tabular-nums">
                {verifiedCount}
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Teacher approved</p>
            </div>

            <div className="border border-[#DCE7EE] rounded-xl bg-white p-3.5 sm:p-4 shadow-xs">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Thanks
                </span>
                <ThumbsUp className="w-4 h-4 text-[#0A8FF5]" />
              </div>
              <div className="text-xl sm:text-2xl font-bold text-[#0A8FF5] tabular-nums">
                {thanksCount}
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">Helpful peer votes</p>
            </div>
          </div>

          {/* Activity Stream Container */}
          <div className="border border-[#DCE7EE] rounded-2xl bg-white shadow-xs overflow-hidden">
            {/* Tab Navigation */}
            <div className="border-b border-[#E8EFF3] px-4 sm:px-6 flex items-center gap-6 sm:gap-8 overflow-x-auto no-scrollbar">
              <button
                type="button"
                onClick={() => setActiveTab('questions')}
                className={`py-3.5 text-xs sm:text-sm font-semibold transition cursor-pointer relative whitespace-nowrap ${
                  activeTab === 'questions'
                    ? 'text-[#111111] font-bold'
                    : 'text-slate-500 hover:text-[#111111]'
                }`}
              >
                <span>My Questions ({myQuestions.length})</span>
                {activeTab === 'questions' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-full" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('answers')}
                className={`py-3.5 text-xs sm:text-sm font-semibold transition cursor-pointer relative whitespace-nowrap ${
                  activeTab === 'answers'
                    ? 'text-[#111111] font-bold'
                    : 'text-slate-500 hover:text-[#111111]'
                }`}
              >
                <span>My Answers ({myAnswers.length})</span>
                {activeTab === 'answers' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-full" />
                )}
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('saved')}
                className={`py-3.5 text-xs sm:text-sm font-semibold transition cursor-pointer relative whitespace-nowrap ${
                  activeTab === 'saved'
                    ? 'text-[#111111] font-bold'
                    : 'text-slate-500 hover:text-[#111111]'
                }`}
              >
                <span>Saved Doubts ({mySaved.length})</span>
                {activeTab === 'saved' && (
                  <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#0A8FF5] rounded-full" />
                )}
              </button>
            </div>

            {/* Tab Body */}
            <div className="p-4 sm:p-6">
              {/* 1. MY QUESTIONS */}
              {activeTab === 'questions' && (
                myQuestions.length > 0 ? (
                  <div className="divide-y divide-[#F1F5F9]">
                    {myQuestions.map((doubt) => (
                      <div
                        key={doubt.id}
                        onClick={() => onSelectDoubt?.(doubt.id)}
                        className="py-3.5 first:pt-0 last:pb-0 hover:bg-slate-50/70 p-2.5 rounded-xl transition cursor-pointer group"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[11px] font-bold text-[#0A8FF5] bg-[#EAF5FF] px-2 py-0.5 rounded-md">
                            {doubt.subject}
                          </span>
                          <span className="text-[10px] text-slate-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" /> {doubt.askedAt || 'Recently'}
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-[#111111] group-hover:text-[#0A8FF5] transition-colors leading-snug">
                          {doubt.doubtQuestion}
                        </h3>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                          <span className="inline-flex items-center gap-1 text-[11px]">
                            <MessageSquare className="w-3 h-3 text-slate-400" />
                            {doubt.answers.length} {doubt.answers.length === 1 ? 'answer' : 'answers'}
                            {doubt.answers.some((a) => a.isVerifiedByTeacher) && (
                              <span className="ml-1 text-emerald-600 font-bold flex items-center gap-0.5">
                                <CheckCircle2 className="w-3 h-3" /> Verified
                              </span>
                            )}
                          </span>
                          <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-2">
                      <HelpCircle className="w-5 h-5" />
                    </div>
                    <h4 className="text-xs sm:text-sm font-bold text-[#111111]">No questions asked yet</h4>
                    <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                      Ask questions from your course syllabus to receive solutions from professors and peers.
                    </p>
                  </div>
                )
              )}

              {/* 2. MY ANSWERS */}
              {activeTab === 'answers' && (
                myAnswers.length > 0 ? (
                  <div className="divide-y divide-[#F1F5F9]">
                    {myAnswers.map(({ doubt, answer }) => (
                      <div
                        key={answer.id}
                        onClick={() => onSelectDoubt?.(doubt.id)}
                        className="py-3.5 first:pt-0 last:pb-0 hover:bg-slate-50/70 p-2.5 rounded-xl transition cursor-pointer group"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[11px] font-bold text-[#0A8FF5] bg-[#EAF5FF] px-2 py-0.5 rounded-md">
                            {doubt.subject}
                          </span>
                          {answer.isVerifiedByTeacher && (
                            <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Faculty Verified
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mb-1 line-clamp-1">
                          Q: {doubt.doubtQuestion}
                        </p>
                        <p className="text-xs text-slate-800 font-medium leading-relaxed line-clamp-2">
                          {answer.content}
                        </p>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                          <span className="inline-flex items-center gap-1 text-[11px] text-slate-600">
                            <ThumbsUp className="w-3 h-3 text-[#0A8FF5]" /> {answer.thanksCount} thanks
                          </span>
                          <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-2">
                      <MessageSquare className="w-5 h-5" />
                    </div>
                    <h4 className="text-xs sm:text-sm font-bold text-[#111111]">No answers submitted yet</h4>
                    <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                      Share your solutions to help classmates and earn faculty verification badges.
                    </p>
                  </div>
                )
              )}

              {/* 3. SAVED DOUBTS */}
              {activeTab === 'saved' && (
                mySaved.length > 0 ? (
                  <div className="divide-y divide-[#F1F5F9]">
                    {mySaved.map((doubt) => (
                      <div
                        key={doubt.id}
                        onClick={() => onSelectDoubt?.(doubt.id)}
                        className="py-3.5 first:pt-0 last:pb-0 hover:bg-slate-50/70 p-2.5 rounded-xl transition cursor-pointer group"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[11px] font-bold text-[#0A8FF5] bg-[#EAF5FF] px-2 py-0.5 rounded-md">
                            {doubt.subject}
                          </span>
                          <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200 font-semibold">
                            <Bookmark className="w-3 h-3 fill-amber-500 text-amber-500" /> Bookmarked
                          </span>
                        </div>
                        <h3 className="text-sm font-semibold text-[#111111] group-hover:text-[#0A8FF5] transition-colors leading-snug">
                          {doubt.doubtQuestion}
                        </h3>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                          <span className="text-[11px]">
                            {doubt.answers.length} {doubt.answers.length === 1 ? 'answer' : 'answers'}
                          </span>
                          <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center">
                    <div className="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-2">
                      <Bookmark className="w-5 h-5" />
                    </div>
                    <h4 className="text-xs sm:text-sm font-bold text-[#111111]">No saved doubts yet</h4>
                    <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                      Bookmark doubts in the feed to review them before quizzes and exams.
                    </p>
                  </div>
                )
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
