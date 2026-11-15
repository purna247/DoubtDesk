import React, { useState } from 'react';
import {
  ArrowLeft,
  Heart,
  Share2,
  Bookmark,
  MessageSquare,
  CheckCircle2,
  ShieldCheck,
  Send,
  Flag,
  Sparkles,
  Plus
} from 'lucide-react';
import { DoubtItem, getSortedAnswers } from '../../data/doubtsData';

interface PostDetailViewProps {
  doubt: DoubtItem;
  onBackToFeed: () => void;
  onToggleBookmark: (doubtId: string) => void;
  onToggleThanks: (doubtId: string, answerId: string) => void;
  onAddComment: (doubtId: string, answerId: string, text: string) => void;
  onSubmitNewAnswer: (doubtId: string, answerText: string) => void;
  onShowToast: (message: string) => void;
}

export const PostDetailView: React.FC<PostDetailViewProps> = ({
  doubt,
  onBackToFeed,
  onToggleBookmark,
  onToggleThanks,
  onAddComment,
  onSubmitNewAnswer,
  onShowToast
}) => {
  const [newAnswerText, setNewAnswerText] = useState('');
  const [showAnswerForm, setShowAnswerForm] = useState(false);
  const [activeCommentBoxAnswerId, setActiveCommentBoxAnswerId] = useState<string | null>(null);
  const [commentInput, setCommentInput] = useState('');

  // 1. Sort answers so Teacher-Verified answer appears 1st, then the rest
  const sortedAnswers = getSortedAnswers(doubt.answers);
  const totalThanksCount = sortedAnswers.reduce((acc, ans) => acc + ans.thanksCount, 0);

  const handleCopyLink = () => {
    navigator.clipboard?.writeText(window.location.href);
    onShowToast('Question link copied to clipboard!');
  };

  const handlePostAnswer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAnswerText.trim()) return;
    onSubmitNewAnswer(doubt.id, newAnswerText.trim());
    setNewAnswerText('');
    setShowAnswerForm(false);
    onShowToast('Your answer was submitted to the community! (+25 pts)');
  };

  const handlePostComment = (e: React.FormEvent, answerId: string) => {
    e.preventDefault();
    if (!commentInput.trim()) return;
    onAddComment(doubt.id, answerId, commentInput.trim());
    setCommentInput('');
    onShowToast('Comment posted successfully!');
  };

  return (
    <div className="w-full max-w-[820px] mx-auto animate-in fade-in duration-200">
      {/* Breadcrumb & Back Navigation */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <button
          onClick={onBackToFeed}
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#0A8FF5] hover:text-[#087FD8] transition cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to All Doubts</span>
        </button>

        <div className="flex items-center gap-1.5 text-xs text-[#71808C]">
          <span>{doubt.subject}</span>
          <span aria-hidden="true">·</span>
          <span>{doubt.topic}</span>
        </div>
      </div>

      {/* 1. TOP QUESTION CARD (Matching Brainly clicked-post layout in screenshot) */}
      <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-7 mb-6 shadow-xs">
        {/* Author Metadata row */}
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 sm:w-11 sm:h-11 rounded-full overflow-hidden bg-slate-100 border border-[#DCE7EE] shrink-0">
              {doubt.studentAvatar ? <img src={doubt.studentAvatar} alt={doubt.studentName} className="w-full h-full object-cover" referrerPolicy="no-referrer" /> : <span className="w-full h-full flex items-center justify-center text-sm font-bold text-slate-500">{doubt.studentName.trim().slice(0, 1).toUpperCase() || '?'}</span>}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm sm:text-base text-[#111111] truncate">
                  {doubt.studentName}
                </span>
              </div>
              <div className="text-xs text-[#71808C] truncate">
                {doubt.askedAt} · {doubt.syllabusNodeTitle ? `${doubt.subject} (${doubt.syllabusNodeTitle})` : doubt.subject} · {doubt.studentGrade}
              </div>
            </div>
          </div>

          {/* Answered Status Pill matching screenshot */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="px-3 py-1 rounded-full bg-[#EDF4F8] text-[#111111] text-xs font-bold uppercase tracking-wider flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-[#22A06B]" />
              <span>{doubt.answers.length > 0 ? 'answered' : 'needs answer'}</span>
            </span>
          </div>
        </div>

        {/* The Doubt Question Body - Strictly ONE Section */}
        <div className="mb-6">
          {doubt.syllabusNodeTitle && (
            <div className="mb-2.5">
              <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200/60 px-3 py-1 text-xs font-semibold text-[#0A8FF5]">
                Topic: {doubt.syllabusNodeTitle}
              </span>
            </div>
          )}
          <h1 className="text-lg sm:text-[21px] font-bold text-[#111111] leading-relaxed tracking-tight">
            {doubt.doubtQuestion}
          </h1>
        </div>

        {/* Bottom Action Row matching screenshot */}
        <div className="pt-4 border-t border-[#E8EFF3] flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* "(N) SEE ANSWERS" button matching screenshot */}
            <a
              href="#answers-section"
              className="h-10 px-5 rounded-full bg-[#050505] text-white font-extrabold text-xs sm:text-sm tracking-wide inline-flex items-center gap-2 hover:bg-[#1A1A1A] transition cursor-pointer"
            >
              <span className="w-5 h-5 rounded-full bg-white text-[#050505] flex items-center justify-center text-xs font-bold">
                {doubt.answers.length}
              </span>
              <span>SEE {doubt.answers.length === 1 ? 'ANSWER' : 'ANSWERS'}</span>
            </a>

            {/* Answer this doubt button */}
            <button
              onClick={() => setShowAnswerForm(!showAnswerForm)}
              className="btn-outline h-10 text-xs sm:text-sm px-4 rounded-full"
            >
              <Plus className="w-4 h-4" />
              <span>Answer</span>
            </button>
          </div>

          {/* Right utility icons: Bookmark & Share */}
          <div className="flex items-center gap-1.5 text-[#71808C]">
            <button
              onClick={() => onToggleBookmark(doubt.id)}
              className={`w-9 h-9 rounded-full flex items-center justify-center hover:bg-[#EDF4F8] transition cursor-pointer ${
                doubt.isBookmarked ? 'text-[#0A8FF5]' : ''
              }`}
              aria-label="Bookmark"
            >
              <Bookmark className={`w-4 h-4 ${doubt.isBookmarked ? 'fill-[#0A8FF5]' : ''}`} />
            </button>
            <button
              onClick={handleCopyLink}
              className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-[#EDF4F8] transition cursor-pointer"
              aria-label="Share"
            >
              <Share2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => onShowToast('Question reported for moderation review')}
              className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-[#EDF4F8] transition cursor-pointer"
              aria-label="Report"
            >
              <Flag className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Write an Answer Form (collapsible / toggleable) */}
      {showAnswerForm && (
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-6 mb-6 shadow-xs animate-in fade-in duration-150">
          <h3 className="text-base font-bold text-[#111111] mb-2 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#0A8FF5]" />
            <span>Contribute your answer to this doubt</span>
          </h3>
          <p className="text-xs text-[#71808C] mb-4">
            Earn +{doubt.rewardPoints} points and help fellow peers understand operating system kernels.
          </p>

          <form onSubmit={handlePostAnswer} className="space-y-3.5">
            <textarea
              required
              rows={5}
              value={newAnswerText}
              onChange={(e) => setNewAnswerText(e.target.value)}
              placeholder="Provide a clear, step-by-step solution..."
              className="w-full p-4 rounded-xl bg-[#EDF4F8] border border-transparent text-sm text-[#111111] placeholder-[#71808C] focus:bg-white focus:border-[#0A8FF5] focus:outline-none resize-none leading-relaxed"
            />
            <div className="flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowAnswerForm(false)}
                className="px-4 py-2 rounded-full text-xs font-semibold text-[#4D5963] hover:bg-[#EDF4F8] transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!newAnswerText.trim()}
                className="btn-primary text-xs py-2 px-5 disabled:opacity-40"
              >
                Submit Solution (+{doubt.rewardPoints} pts)
              </button>
            </div>
          </form>
        </div>
      )}

      {/* 2. ANSWERS SECTION (Matching screenshot with Teacher Verified 1st) */}
      <div id="answers-section" className="space-y-6">
        {/* Section Header */}
        <div className="flex items-center justify-between px-1">
          <h2 className="text-xl sm:text-2xl font-bold text-[#111111]">
            Answer{sortedAnswers.length > 1 ? `s (${sortedAnswers.length})` : ''}
          </h2>
          <span className="text-xs sm:text-sm font-semibold text-[#71808C]">
            {totalThanksCount} people found {sortedAnswers.length > 1 ? 'them' : 'it'} helpful
          </span>
        </div>

        {/* Answers List: Teacher Verified Answer is guaranteed to be 1st! */}
        {sortedAnswers.map((answer, index) => (
          <div
            key={answer.id}
            className={`border rounded-[16px] bg-white p-5 sm:p-7 shadow-xs relative ${
              answer.isVerifiedByTeacher
                ? 'border-[#0A8FF5]/40 ring-1 ring-[#0A8FF5]/20'
                : 'border-[#DCE7EE]'
            }`}
          >
            {/* Answer Header: Author info & Teacher verified seal */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-[#E8EFF3]">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-full overflow-hidden bg-slate-100 border border-[#DCE7EE] shrink-0">
                  {answer.authorAvatar ? <img src={answer.authorAvatar} alt={answer.answeredBy} className="w-full h-full object-cover" referrerPolicy="no-referrer" /> : <span className="w-full h-full flex items-center justify-center text-sm font-bold text-slate-500">{answer.answeredBy.trim().slice(0, 1).toUpperCase() || '?'}</span>}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-base text-[#111111]">
                      {answer.answeredBy}
                    </span>
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      String(answer.authorRank).toLowerCase().includes('teacher') || answer.isVerifiedByTeacher
                        ? 'bg-[#E7F7EF] text-[#18754E] border border-[#22A06B]/30'
                        : 'bg-[#EAF5FF] text-[#0A8FF5]'
                    }`}>
                      {String(answer.authorRank).toLowerCase().includes('teacher') || answer.isVerifiedByTeacher ? 'Teacher' : answer.authorRank}
                    </span>
                  </div>
                  <div className="text-xs text-[#71808C] truncate mt-0.5">
                    {answer.isVerifiedByTeacher ? 'Faculty Verified' : answer.authorTitle} · {answer.answeredAt}
                  </div>
                </div>
              </div>

              {/* Teacher Verified Badge (1st answer badge) */}
              {(answer.isVerifiedByTeacher || String(answer.authorRank).toLowerCase().includes('teacher')) && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#E7F7EF] border border-[#22A06B]/30 text-[#18754E] text-xs font-bold shadow-xs shrink-0 self-start sm:self-auto">
                  <CheckCircle2 className="w-4 h-4 text-[#22A06B]" />
                  <span>Verified by Teacher</span>
                </div>
              )}
            </div>

            {/* Answer Body */}
            <div className="text-[15px] sm:text-[16px] text-[#111111] leading-relaxed space-y-4">
              {answer.intro && (
                <div className="whitespace-pre-line font-normal text-[#111111]">
                  {answer.intro}
                </div>
              )}

              {/* Structured Points */}
              {answer.points && answer.points.length > 0 ? (
                <div className="space-y-3.5 my-4">
                  {answer.points.map((pt, pIdx) => (
                    <div
                      key={pIdx}
                      className="p-3.5 sm:p-4 rounded-xl bg-[#F7FAFC] border border-[#E8EFF3] hover:border-[#DCE7EE] transition"
                    >
                      <h4 className="font-bold text-[15px] text-[#111111] mb-1 flex items-center gap-2.5">
                        <span className="w-6 h-6 rounded-full bg-[#0A8FF5]/10 text-[#0A8FF5] flex items-center justify-center text-xs font-bold shrink-0">
                          {pIdx + 1}
                        </span>
                        <span>{pt.title.replace(/^\d+\.\s*/, '')}</span>
                      </h4>
                      <p className="text-sm sm:text-[15px] text-[#4D5963] leading-relaxed pl-8">
                        {pt.description}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="whitespace-pre-line text-[#111111]">
                  {answer.content}
                </div>
              )}

              {answer.summary && (
                <p className="text-sm sm:text-[15px] font-medium text-[#111111] leading-relaxed pt-2">
                  {answer.summary}
                </p>
              )}

              {/* Verified Teacher Endorsement Certificate Box */}
              {answer.isVerifiedByTeacher && (
                <div className="mt-5 p-4 rounded-xl bg-[#FFF9E6] border border-[#F5D36C] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-[#F5D36C] flex items-center justify-center text-[#7C5E00] shrink-0 mt-0.5">
                      <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold uppercase tracking-wider text-[#8A6800]">
                          [Verified by Teacher]
                        </span>
                        <span className="text-xs font-semibold text-[#111111] truncate">
                          · {answer.teacherName} ({answer.teacherTitle})
                        </span>
                      </div>
                      <p className="text-xs text-[#5C4500] mt-0.5 font-normal leading-relaxed">
                        {answer.verificationNote ||
                          'Verified for technical correctness and academic clarity.'}
                      </p>
                    </div>
                  </div>
                  <span className="text-[11px] font-semibold text-[#8A6800] bg-white/70 px-2.5 py-1 rounded-md border border-[#F5D36C]/60 shrink-0 self-start sm:self-auto">
                    {answer.verifiedAt}
                  </span>
                </div>
              )}
            </div>

            {/* Answer Engagement Actions */}
            <div className="mt-5 pt-4 border-t border-[#E8EFF3] flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={Boolean(answer.hasThanked)}
                  aria-pressed={Boolean(answer.hasThanked)}
                  title={answer.hasThanked ? 'You have already thanked this answer' : 'Thank answer author'}
                  onClick={() => onToggleThanks(doubt.id, answer.id)}
                  className={`inline-flex items-center gap-2 h-9 px-4 rounded-full text-xs font-bold transition ${
                    answer.hasThanked
                      ? 'bg-[#FFF0F0] text-[#E52521] border border-[#E52521]/30 cursor-default'
                      : 'bg-[#EDF4F8] hover:bg-[#E3EDF3] text-[#111111] cursor-pointer'
                  }`}
                >
                  <Heart
                    className={`w-4 h-4 ${
                      answer.hasThanked ? 'fill-[#E52521] text-[#E52521]' : 'text-[#71808C]'
                    }`}
                  />
                  <span>{answer.hasThanked ? `Thanked (${answer.thanksCount})` : `Thanks (${answer.thanksCount})`}</span>
                </button>

                <button
                  onClick={() =>
                    setActiveCommentBoxAnswerId(
                      activeCommentBoxAnswerId === answer.id ? null : answer.id
                    )
                  }
                  className="inline-flex items-center gap-2 h-9 px-4 rounded-full bg-[#EDF4F8] hover:bg-[#E3EDF3] text-[#111111] text-xs font-semibold transition cursor-pointer"
                >
                  <MessageSquare className="w-4 h-4 text-[#71808C]" />
                  <span>Comments ({answer.comments.length})</span>
                </button>
              </div>

              <div className="flex items-center gap-1.5 text-xs text-[#71808C]">
                <span>Answer #{index + 1}</span>
                {answer.isVerifiedByTeacher && (
                  <span className="font-semibold text-[#22A06B]">· Verified</span>
                )}
              </div>
            </div>

            {/* Comments Thread & Follow-up Input */}
            {activeCommentBoxAnswerId === answer.id && (
              <div className="mt-4 p-4 rounded-xl bg-[#F7FAFC] border border-[#E8EFF3]">
                <h4 className="text-xs font-bold text-[#111111] uppercase tracking-wider mb-3">
                  Discussion & Clarifications
                </h4>

                {answer.comments.length > 0 ? (
                  <div className="space-y-2.5 mb-4">
                    {answer.comments.map((comm) => (
                      <div
                        key={comm.id}
                        className="p-3 bg-white rounded-xl border border-[#E8EFF3] flex items-start gap-2.5"
                      >
                        {comm.avatar ? <img src={comm.avatar} alt={comm.author} className="w-7 h-7 rounded-full object-cover shrink-0 mt-0.5" referrerPolicy="no-referrer" /> : <span className="w-7 h-7 rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 flex items-center justify-center shrink-0 mt-0.5">{comm.author.trim().slice(0, 1).toUpperCase() || '?'}</span>}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <div className="flex items-center gap-1.5 min-w-0">
                              <span className="text-xs font-bold text-[#111111] truncate">
                                {comm.author}
                              </span>
                              <span className="text-[10px] text-[#71808C] bg-[#EDF4F8] px-1.5 py-0.5 rounded shrink-0">
                                {comm.role}
                              </span>
                            </div>
                            <span className="text-[11px] text-[#71808C] shrink-0">
                              {comm.createdAt}
                            </span>
                          </div>
                          <p className="text-xs text-[#4D5963] leading-relaxed">{comm.text}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#71808C] mb-3">
                    No comments yet. Have a question or want to thank {answer.answeredBy}?
                  </p>
                )}

                <form
                  onSubmit={(e) => handlePostComment(e, answer.id)}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={commentInput}
                    onChange={(e) => setCommentInput(e.target.value)}
                    placeholder="Write a clarification or question..."
                    className="flex-1 h-9 sm:h-10 px-3.5 sm:px-4 rounded-full bg-white border border-[#DCE7EE] text-xs text-[#111111] placeholder-[#71808C] focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 min-w-0"
                  />
                  <button
                    type="submit"
                    disabled={!commentInput.trim()}
                    className="h-9 sm:h-10 px-4 rounded-full bg-[#050505] hover:bg-[#1A1A1A] disabled:opacity-40 text-white text-xs font-bold inline-flex items-center gap-1.5 transition cursor-pointer shrink-0"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Send</span>
                  </button>
                </form>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Floating or Bottom CTA to Add Another Answer */}
      <div className="mt-8 p-5 rounded-2xl bg-[#F7FAFC] border border-[#DCE7EE] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h4 className="font-bold text-sm text-[#111111]">
            Can you provide another perspective or example?
          </h4>
          <p className="text-xs text-[#71808C]">
            Multiple students can answer! Help {doubt.studentName} with additional insights.
          </p>
        </div>
        <button
          onClick={() => {
            setShowAnswerForm(true);
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
          className="btn-primary text-xs py-2.5 px-5 whitespace-nowrap shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>Write an Answer (+{doubt.rewardPoints} pts)</span>
        </button>
      </div>
    </div>
  );
};
