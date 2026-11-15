import React, { useState } from 'react';
import {
  Users,
  Trophy,
  Heart,
  TrendingDown,
  TrendingUp,
  ChevronRight,
  HelpCircle,
  CheckCheck
} from 'lucide-react';
import type { CourseOffering } from '../../types/academics';

export interface InfluencePeriodStats {
  popularity: number;
  popularity_delta_pct?: number | null;
  best_answers: number;
  best_answers_delta_pct?: number | null;
  thanks: number;
  thanks_delta_pct?: number | null;
}

export interface MyDoubtStats {
  asked_count: number;
  answered_count: number;
  verified_answers_count: number;
  thanks_count: number;
  last_7_days: InfluencePeriodStats;
  overall: InfluencePeriodStats;
}

export interface TeacherDoubtSummary {
  unansweredCount: number;
  pendingVerificationCount: number;
  verifiedCount: number;
  totalCount: number;
}

interface RightSidebarProps {
  role?: string | null;
  teacherOfferings?: CourseOffering[];
  facultyName?: string;
  onSelectContributor?: (name: string) => void;
  onOpenProfile?: () => void;
  studentName?: string;
  semester?: string;
  avatarUrl?: string | null;
  stats?: MyDoubtStats | null;
  isLoadingStats?: boolean;
  teacherDoubtSummary?: TeacherDoubtSummary;
  activeFilterMode?: string;
  onSelectDoubtFilter?: (filter: string) => void;
}

const formatDoubtCount = (count: number) => `${count} ${count === 1 ? 'doubt' : 'doubts'}`;

const getInitials = (name: string) => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'S';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
};

const renderDeltaBadge = (delta?: number | null) => {
  if (typeof delta !== 'number') return null;
  const isPositive = delta >= 0;
  return (
    <span
      className={`text-[11px] font-semibold inline-flex items-center gap-0.5 mt-0.5 ${
        isPositive ? 'text-[#22A06B]' : 'text-[#E52521]'
      }`}
    >
      {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      <span>{isPositive ? `+${delta}%` : `${delta}%`}</span>
    </span>
  );
};

export const RightSidebar: React.FC<RightSidebarProps> = ({
  role,
  teacherOfferings = [],
  facultyName = 'Faculty',
  onOpenProfile,
  studentName = 'Student Scholar',
  semester = 'Enrolled Student',
  avatarUrl,
  stats,
  isLoadingStats = false,
  teacherDoubtSummary,
  activeFilterMode,
  onSelectDoubtFilter,
}) => {
  const [influencePeriod, setInfluencePeriod] = useState<'7days' | 'overall'>('7days');
  const activeStats = influencePeriod === '7days' ? stats?.last_7_days : stats?.overall;
  const answeredCount = stats?.answered_count ?? 0;
  const askedCount = stats?.asked_count ?? 0;
  const progressDashOffset = Math.max(0, 170 - Math.min(100, (answeredCount + askedCount) * 10) * 1.7);

  if (role === 'TEACHER') {
    const unanswered = teacherDoubtSummary?.unansweredCount ?? 0;
    const pendingVer = teacherDoubtSummary?.pendingVerificationCount ?? 0;
    const verified = teacherDoubtSummary?.verifiedCount ?? 0;
    const total = teacherDoubtSummary?.totalCount ?? 0;
    const totalPending = unanswered + pendingVer;

    return (
      <aside className="w-[290px] xl:w-[320px] 2xl:w-[340px] shrink-0 hidden lg:flex flex-col gap-4 sticky top-6">
        {/* 1. Faculty Profile Card */}
        <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-[#0F172A] text-white flex items-center justify-center font-bold text-sm tracking-wide shrink-0 overflow-hidden">
              {avatarUrl ? (
                <img src={avatarUrl} alt={facultyName} className="w-full h-full object-cover" />
              ) : (
                <span>{getInitials(facultyName)}</span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-bold text-[#111111] leading-tight truncate">
                {facultyName}
              </h3>
              <p className="text-xs text-[#71808C] mt-0.5 font-medium">Faculty Member</p>
            </div>
          </div>
        </div>

        {/* 2. Doubts Pending Review / Answer / Verify Card */}
        <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5] flex items-center gap-1.5">
              <HelpCircle className="w-3.5 h-3.5" />
              Doubt Review Queue
            </p>
            {totalPending > 0 ? (
              <span className="rounded-full bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 text-[10px] font-bold">
                {totalPending} Pending
              </span>
            ) : (
              <span className="rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold">
                All Cleared
              </span>
            )}
          </div>

          <div className="space-y-2">
            {/* Unanswered doubts */}
            <button
              type="button"
              onClick={() => onSelectDoubtFilter?.('unanswered')}
              className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-left transition cursor-pointer ${
                activeFilterMode === 'unanswered'
                  ? 'bg-[#EAF5FF] border-[#B8D9F5]'
                  : 'bg-[#F8FAFC] border-[#E8EFF3] hover:bg-slate-100'
              }`}
              title="Click to view doubts needing an answer"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-xs">
                  {unanswered}
                </div>
                <div>
                  <p className="text-xs font-semibold text-[#111111]">Unanswered Doubts</p>
                  <p className="text-[10px] text-[#71808C]">Awaiting faculty or peer answer</p>
                </div>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-[#71808C]" />
            </button>

            {/* Pending Verification */}
            <button
              type="button"
              onClick={() => onSelectDoubtFilter?.('needs_verification')}
              className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-left transition cursor-pointer ${
                activeFilterMode === 'needs_verification'
                  ? 'bg-[#EAF5FF] border-[#B8D9F5]'
                  : 'bg-[#F8FAFC] border-[#E8EFF3] hover:bg-slate-100'
              }`}
              title="Click to view answers awaiting teacher verification"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center font-bold text-xs">
                  {pendingVer}
                </div>
                <div>
                  <p className="text-xs font-semibold text-[#111111]">Pending Verification</p>
                  <p className="text-[10px] text-[#71808C]">Answers waiting for faculty check</p>
                </div>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-[#71808C]" />
            </button>

            {/* Verified Answers */}
            <button
              type="button"
              onClick={() => onSelectDoubtFilter?.('verified')}
              className={`w-full flex items-center justify-between p-2.5 rounded-xl border text-left transition cursor-pointer ${
                activeFilterMode === 'verified'
                  ? 'bg-[#EAF5FF] border-[#B8D9F5]'
                  : 'bg-[#F8FAFC] border-[#E8EFF3] hover:bg-slate-100'
              }`}
              title="Click to view verified answers"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">
                  {verified}
                </div>
                <div>
                  <p className="text-xs font-semibold text-[#111111]">Faculty Verified</p>
                  <p className="text-[10px] text-[#71808C]">Approved solutions</p>
                </div>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-[#71808C]" />
            </button>
          </div>

          {/* Quick reset / view all button */}
          <button
            type="button"
            onClick={() => onSelectDoubtFilter?.('all')}
            className={`mt-3 w-full text-center py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
              activeFilterMode === 'all'
                ? 'bg-slate-200 text-slate-800'
                : 'text-[#0A8FF5] hover:bg-[#EAF5FF]'
            }`}
          >
            View All Doubts ({total})
          </button>
        </div>

        {/* 3. Assigned Courses Card */}
        <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
          <p className="text-[11px] font-bold uppercase tracking-wider text-[#71808C] mb-2.5">
            Assigned Courses ({teacherOfferings.length})
          </p>
          {teacherOfferings.length > 0 ? (
            <ul className="space-y-2.5">
              {teacherOfferings.map((offering) => (
                <li key={offering.id} className="border-b border-[#F1F5F9] pb-2 last:border-0 last:pb-0">
                  <p className="text-xs font-semibold text-[#111111] leading-snug">
                    {offering.subject_name || offering.official_subject_code || 'Assigned course'}
                  </p>
                  <p className="mt-0.5 text-[11px] text-[#71808C]">
                    {[offering.official_subject_code, offering.section_code && `Sec ${offering.section_code}`, offering.term_code].filter(Boolean).join(' · ')}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[#71808C]">No assigned course offerings returned.</p>
          )}
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-[290px] xl:w-[320px] 2xl:w-[340px] shrink-0 hidden lg:flex flex-col gap-5">
      {/* 1. Student Profile Card (Matching user screenshot) */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white overflow-hidden shadow-xs">
        <div className="p-5">
          {/* Avatar with circular progress ring + Name & Status */}
          <div className="flex items-center gap-3.5 mb-4">
            {/* Circular Avatar with Progress Ring */}
            <div className="relative w-16 h-16 shrink-0 flex items-center justify-center">
              {/* Segmented green progress ring SVG */}
              <svg className="w-16 h-16 -rotate-90 shrink-0" viewBox="0 0 64 64">
                <circle
                  cx="32"
                  cy="32"
                  r="27"
                  fill="none"
                  stroke="#E8EFF3"
                  strokeWidth="2.5"
                />
                <circle
                  cx="32"
                  cy="32"
                  r="27"
                  fill="none"
                  stroke="#22A06B"
                  strokeWidth="2.5"
                  strokeDasharray="170"
                  strokeDashoffset={progressDashOffset}
                  strokeLinecap="round"
                />
              </svg>

              {/* Inner Avatar Graphic */}
              <div className="absolute inset-2 rounded-full overflow-hidden bg-[#0F172A] text-white flex items-center justify-center font-bold text-sm tracking-wide">
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt={studentName}
                    className="w-full h-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span>{getInitials(studentName)}</span>
                )}
              </div>
            </div>

            {/* Name & Ambitious Badge */}
            <div className="min-w-0 flex-1">
              <h3 className="text-[19px] font-bold text-[#111111] leading-tight truncate">
                {studentName}
              </h3>
              <div className="mt-1">
                <span className="inline-block px-3 py-0.5 rounded-full bg-[#FFF2C6] text-[#111111] font-semibold text-xs truncate max-w-full">
                  {semester}
                </span>
              </div>
            </div>
          </div>

          {/* Answered & Doubts Counter */}
          <div className="grid grid-cols-2 gap-2 pt-3 border-t border-[#E8EFF3] text-left">
            <div className="p-2 rounded-xl bg-[#F7FAFC] min-w-0">
              <div className="flex items-center gap-1 text-[11px] text-[#71808C] font-medium truncate">
                <CheckCheck className="w-3.5 h-3.5 text-[#22A06B]" />
                <span className="truncate">Answered</span>
              </div>
              <span className="text-sm sm:text-base font-bold text-[#111111] tabular-nums block mt-0.5 truncate">
                {isLoadingStats && !stats ? '—' : formatDoubtCount(answeredCount)}
              </span>
            </div>
            <div className="p-2 rounded-xl bg-[#F7FAFC] min-w-0">
              <div className="flex items-center gap-1 text-[11px] text-[#71808C] font-medium truncate">
                <HelpCircle className="w-3.5 h-3.5 text-[#0A8FF5]" />
                <span className="truncate">Asked</span>
              </div>
              <span className="text-sm sm:text-base font-bold text-[#111111] tabular-nums block mt-0.5 truncate">
                {isLoadingStats && !stats ? '—' : formatDoubtCount(askedCount)}
              </span>
            </div>
          </div>
        </div>

        {/* Bottom Link: "View My Achievements" with right chevron > */}
        <button
          onClick={onOpenProfile}
          className="w-full py-3.5 px-5 border-t border-[#E8EFF3] flex items-center justify-between text-left hover:bg-[#F7FAFC] transition group cursor-pointer"
        >
          <span className="text-sm font-bold text-[#0A58CA] group-hover:text-[#084298] transition">
            View My Achievements
          </span>
          <ChevronRight className="w-4 h-4 text-[#0A58CA] group-hover:translate-x-0.5 transition" />
        </button>
      </div>

      {/* 2. Your Influence / Statistics Card (Matching screenshot) */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-5 shadow-xs">
        <h3 className="text-[17px] font-bold text-[#111111] mb-2.5">
          Your influence
        </h3>

        {/* Segmented Filter Pills matching screenshot */}
        <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#F0F5F8] mb-3">
          <button
            onClick={() => setInfluencePeriod('7days')}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
              influencePeriod === '7days'
                ? 'bg-white text-[#111111] shadow-xs'
                : 'text-[#71808C] hover:text-[#111111]'
            }`}
          >
            Last 7 days
          </button>
          <button
            onClick={() => setInfluencePeriod('overall')}
            className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer ${
              influencePeriod === 'overall'
                ? 'bg-white text-[#111111] shadow-xs'
                : 'text-[#71808C] hover:text-[#111111]'
            }`}
          >
            Overall
          </button>
        </div>

        <p className="text-[11px] text-[#71808C] mb-3 leading-snug">
          Your stats from the {influencePeriod === '7days' ? 'last 7 days compared with previous 7 days' : 'entire semester learning activity'}
        </p>

        <div className="flex flex-col">
          {/* Metric 1: Popularity */}
          <div className="py-2.5 flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-[#EAF5FF] flex items-center justify-center text-[#0A8FF5] shrink-0 mt-0.5">
                <Users className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#111111] truncate">Popularity</p>
                <p className="text-xs text-[#71808C] truncate">People interacting</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-2xl font-bold text-[#111111] leading-none tabular-nums block">
                {isLoadingStats && !stats ? '—' : (activeStats?.popularity ?? 0)}
              </span>
              {influencePeriod === '7days' && renderDeltaBadge(activeStats?.popularity_delta_pct)}
            </div>
          </div>

          <div className="h-[1px] bg-[#E8EFF3] my-1" />

          {/* Metric 2: Best answers */}
          <div className="py-2.5 flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-[#FFF4CF] flex items-center justify-center text-[#D49E00] shrink-0 mt-0.5">
                <Trophy className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#111111] truncate">Best Answer</p>
                <p className="text-xs text-[#71808C] truncate">Verified best answers</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-2xl font-bold text-[#111111] leading-none tabular-nums block">
                {isLoadingStats && !stats ? '—' : (activeStats?.best_answers ?? 0)}
              </span>
              {influencePeriod === '7days' && renderDeltaBadge(activeStats?.best_answers_delta_pct)}
            </div>
          </div>

          <div className="h-[1px] bg-[#E8EFF3] my-1" />

          {/* Metric 3: Thanks */}
          <div className="py-2.5 flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-lg bg-[#FFF0F0] flex items-center justify-center text-[#E52521] shrink-0 mt-0.5">
                <Heart className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#111111] truncate">Thanks</p>
                <p className="text-xs text-[#71808C] truncate">Peer appreciations</p>
              </div>
            </div>
            <div className="text-right shrink-0">
              <span className="text-2xl font-bold text-[#111111] leading-none tabular-nums block">
                {isLoadingStats && !stats ? '—' : (activeStats?.thanks ?? 0)}
              </span>
              {influencePeriod === '7days' && renderDeltaBadge(activeStats?.thanks_delta_pct)}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
};
