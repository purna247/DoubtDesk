import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  BrainCircuit,
  BookOpen,
  ChevronRight,
  BarChart2,
  Loader2,
  CheckCircle,
  MessageSquare,
  Users,
  ShieldCheck,
  Send,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { apiClient } from '../../api/client';
import { CourseOffering } from '../../types/academics';
import { TeacherAnalyticsPage } from './TeacherAnalyticsPage';

interface DoubtAuthor {
  id?: string;
  display_name?: string;
  avatar_url?: string;
  is_anonymous?: boolean;
}

interface BackendAnswer {
  id: string;
  author?: DoubtAuthor;
  body_markdown: string;
  is_teacher_verified: boolean;
  upvote_count: number;
  created_at?: string;
}

interface BackendDoubt {
  id: string;
  title: string;
  body_markdown: string;
  concept_name?: string;
  author?: DoubtAuthor;
  created_at: string;
  answers?: BackendAnswer[];
}

interface CourseIndicators { gaps: number; attempts: number; pendingQuestions: number; activeInterventions: number }

export const TeacherDashboardPage: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();
  const [offerings, setOfferings] = useState<CourseOffering[]>([]);
  const [doubts, setDoubts] = useState<BackendDoubt[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'doubts' | 'analytics'>('overview');

  // Teacher answering state
  const [replyingDoubtId, setReplyingDoubtId] = useState<string | null>(null);
  const [replyText, setReplyText] = useState<string>('');
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);
  const [courseIndicators, setCourseIndicators] = useState<Record<string, CourseIndicators>>({});

  const teacherName = user?.fullName || user?.full_name || 'Faculty Member';
  const institutionName = user?.institutionName || user?.institution_name || 'Academic Institution';

  useEffect(() => {
    if (location.pathname === '/teacher/analytics') setActiveTab('analytics');
    else if (new URLSearchParams(location.search).get('tab') === 'doubts') setActiveTab('doubts');
    else setActiveTab('overview');
  }, [location.pathname, location.search]);

  const showNotification = (msg: string) => {
    setActionSuccessMessage(msg);
    setTimeout(() => setActionSuccessMessage(null), 4000);
  };

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      apiClient.get<CourseOffering[]>('/api/v1/academics/teacher/offerings').catch(() => []),
      apiClient.get<BackendDoubt[]>('/api/v1/doubts').catch(() => []),
    ])
      .then(([offeringsData, doubtsData]) => {
        if (isMounted) {
          if (Array.isArray(offeringsData)) setOfferings(offeringsData);
          if (Array.isArray(doubtsData)) setDoubts(doubtsData);
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!offerings.length) { setCourseIndicators({}); return; }
    Promise.all(offerings.map(async (offering) => {
      const [analytics, activity, questions, interventions] = await Promise.all([
        apiClient.get<{ confirmed_weak_count: number }[]>(`/api/v1/courses/${offering.id}/analytics/concepts`).catch(() => []),
        apiClient.get<{ attempt_id: string }[]>(`/api/v1/courses/${offering.id}/assessment-activity`).catch(() => []),
        apiClient.get<{ latest_version?: { approval_status: string } }[]>(`/api/v1/courses/${offering.id}/questions`).catch(() => []),
        apiClient.get<{ status: string }[]>(`/api/v1/courses/${offering.id}/interventions`).catch(() => []),
      ]);
      return [offering.id, {
        gaps: analytics.reduce((sum, item) => sum + (item.confirmed_weak_count || 0), 0),
        attempts: activity.length,
        pendingQuestions: questions.filter((item) => ['draft', 'pending_review'].includes(item.latest_version?.approval_status || '')).length,
        activeInterventions: interventions.filter((item) => item.status === 'active').length,
      }] as const;
    })).then((entries) => { if (!cancelled) setCourseIndicators(Object.fromEntries(entries)); });
    return () => { cancelled = true; };
  }, [offerings]);

  const handleVerifyAnswer = async (answerId: string, _doubtId: string) => {
    try {
      await apiClient.post(`/api/v1/doubts/answers/${answerId}/verify`, {});
      const refreshed = await apiClient.get<BackendDoubt[]>('/api/v1/doubts');
      setDoubts(Array.isArray(refreshed) ? refreshed : []);
      showNotification('Answer verified.');
    } catch {
      showNotification('Could not verify this answer. Please retry.');
    }
  };

  const handleSubmitTeacherAnswer = async (doubtId: string) => {
    if (!replyText.trim()) return;
    try {
      await apiClient.post<BackendAnswer>(`/api/v1/doubts/${doubtId}/answers`, {
        body_markdown: replyText.trim(),
      });
      const refreshed = await apiClient.get<BackendDoubt[]>('/api/v1/doubts');
      setDoubts(Array.isArray(refreshed) ? refreshed : []);
      setReplyText('');
      setReplyingDoubtId(null);
      showNotification('Faculty answer submitted. Verify it when ready.');
    } catch {
      showNotification('Could not publish the faculty solution. Please retry.');
    }
  };
  // Metrics
  const doubtsAwaitingVerification = doubts.filter(
    (d) => !(d.answers || []).some((a) => a.is_teacher_verified)
  );

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {actionSuccessMessage && (
        <div className="fixed top-20 right-6 z-50 bg-[#111111] text-white text-xs px-4 py-2.5 rounded-xl shadow-lg border border-slate-700 flex items-center gap-2 animate-in fade-in">
          <CheckCircle className="w-4 h-4 text-emerald-400" />
          <span>{actionSuccessMessage}</span>
        </div>
      )}

      {/* Faculty Command Console Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E8EFF3] pb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 mb-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            Faculty Instructor Command Console
          </div>
          <h1 className="text-2xl font-bold text-[#111111]">{teacherName}</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {institutionName} · Faculty course delivery
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <a
            href="/teacher/courses"
            className="btn-outline text-xs px-3.5 py-2 flex items-center gap-1.5 cursor-pointer"
          >
            <BrainCircuit className="w-4 h-4 text-slate-600" /> Course Studio
          </a>
          <a
            href="/doubts"
            className="btn-primary text-xs px-4 py-2 flex items-center gap-1.5 cursor-pointer"
          >
            <MessageSquare className="w-4 h-4" /> Campus Doubts
          </a>
        </div>
      </div>

      {/* Live Faculty KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Assigned Offerings */}
        <div className="card-base p-5 border-[#DCE7EE] bg-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Assigned Courses
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#0A8FF5] flex items-center justify-center">
              <BookOpen className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-[#111111]">{offerings.length}</div>
          <p className="text-[11px] text-slate-500 mt-1">Active deliveries this term</p>
        </div>

        {/* Card 2: Doubts Requiring Verification */}
        <div className="card-base p-5 border-[#DCE7EE] bg-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Doubts Pending Review
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <HelpCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-amber-600">
            {doubtsAwaitingVerification.length}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">Questions without faculty verified badge</p>
        </div>

        {/* Card 3: Campus doubts */}
        <div className="card-base p-5 border-[#DCE7EE] bg-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Campus Doubts
            </span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-[#111111]">
            {doubts.length}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Questions across the institution feed
          </p>
        </div>

        {/* Card 4: Submitted answers */}
        <div className="card-base p-5 border-[#DCE7EE] bg-white">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Submitted Answers
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <BarChart2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-black text-[#111111] mt-1">{doubts.reduce((count, doubt) => count + (doubt.answers?.length ?? 0), 0)}</div>
          <p className="text-[11px] text-slate-500 mt-1">Answers on student questions</p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-3 border-b border-[#E8EFF3]">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-3 text-xs font-bold transition-colors cursor-pointer relative ${
            activeTab === 'overview' ? 'text-[#111111]' : 'text-slate-400 hover:text-slate-700'
          }`}
        >
          <span>Course Deliveries ({offerings.length})</span>
          {activeTab === 'overview' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#111111] rounded-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('doubts')}
          className={`pb-3 text-xs font-bold transition-colors cursor-pointer relative flex items-center gap-1.5 ${
            activeTab === 'doubts' ? 'text-[#111111]' : 'text-slate-400 hover:text-slate-700'
          }`}
        >
          <span>Doubt Verification Queue</span>
          {doubtsAwaitingVerification.length > 0 && (
            <span className="w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] flex items-center justify-center font-bold">
              {doubtsAwaitingVerification.length}
            </span>
          )}
          {activeTab === 'doubts' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#111111] rounded-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('analytics')}
          className={`pb-3 text-xs font-bold transition-colors cursor-pointer relative ${
            activeTab === 'analytics' ? 'text-[#111111]' : 'text-slate-400 hover:text-slate-700'
          }`}
        >
          <span>Analytics</span>
          {activeTab === 'analytics' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#111111] rounded-full" />
          )}
        </button>
      </div>

      {/* TAB 1: Assigned Course Deliveries */}
      {activeTab === 'overview' && (
        <div className="space-y-4">
          {loading ? (
            <div className="card-base p-12 text-center text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[#0A8FF5]" />
              <p className="text-xs">Loading course delivery allocations...</p>
            </div>
          ) : offerings.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {offerings.map((offering) => (
                <div
                  key={offering.id}
                  className="card-base p-6 border-[#DCE7EE] bg-white rounded-2xl shadow-xs hover:border-[#0A8FF5] transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#EAF5FF] text-[#0A8FF5]">
                        {offering.official_subject_code || 'Course'}
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        Sec {offering.section_code} • {offering.delivery_mode.replace('_', ' ')}
                      </span>
                    </div>

                    <h2 className="text-base font-bold text-[#111111]">
                      {offering.subject_name || offering.official_subject_code || 'Assigned course'}
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">
                      {offering.cohort_label || `Section ${offering.section_code}`}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {offering.delivering_unit_name || 'Academic unit'} · Term: {offering.term_code || 'Current term'}
                    </p>
                    <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                      <div className="rounded-lg bg-slate-50 p-2"><span className="font-bold text-amber-700">{courseIndicators[offering.id]?.gaps ?? '—'}</span><span className="ml-1 text-slate-600">confirmed student gaps</span></div>
                      <div className="rounded-lg bg-slate-50 p-2"><span className="font-bold text-slate-900">{courseIndicators[offering.id]?.attempts ?? '—'}</span><span className="ml-1 text-slate-600">assessment attempts</span></div>
                      <div className="rounded-lg bg-slate-50 p-2"><span className="font-bold text-slate-900">{courseIndicators[offering.id]?.pendingQuestions ?? '—'}</span><span className="ml-1 text-slate-600">questions to review</span></div>
                      <div className="rounded-lg bg-slate-50 p-2"><span className="font-bold text-blue-700">{courseIndicators[offering.id]?.activeInterventions ?? '—'}</span><span className="ml-1 text-slate-600">active interventions</span></div>
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between gap-2">
                    <a
                      href="/teacher/courses"
                      className="text-xs font-semibold text-slate-700 hover:text-[#0A8FF5] flex items-center gap-1 transition"
                    >
                      <BarChart2 className="w-3.5 h-3.5" /> Syllabus Studio
                    </a>
                    <a
                      href="/teacher/analytics"
                      className="text-xs font-semibold text-[#0A8FF5] hover:underline flex items-center gap-0.5"
                    >
                      Concept Analytics <ChevronRight className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card-base p-12 text-center border-dashed border-slate-200">
              <BookOpen className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <h3 className="text-sm font-bold text-slate-700">No Course Deliveries Assigned</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                Your department administrator has not assigned active course sections to your faculty profile for this term.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Student Doubt Verification Queue */}
      {activeTab === 'doubts' && (
        <div className="space-y-4">
          <div className="card-base p-4 bg-blue-50/50 border-blue-200 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-[#0A8FF5]" />
              <span className="text-xs font-semibold text-blue-900">
                Peer learning solutions are verified by faculty to establish verified authority in the campus knowledge base.
              </span>
            </div>
            <span className="text-xs font-bold text-[#0A8FF5] shrink-0">
              {doubts.length} Thread(s)
            </span>
          </div>

          {doubts.length > 0 ? (
            <div className="space-y-4">
              {doubts.map((doubt) => {
                const hasVerifiedAnswer = (doubt.answers || []).some((a) => a.is_teacher_verified);

                return (
                  <div
                    key={doubt.id}
                    className="card-base p-5 border-[#DCE7EE] bg-white rounded-2xl shadow-xs"
                  >
                    {/* Top doubt author & metadata */}
                    <div className="flex items-start justify-between gap-3 mb-2.5">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-[#111111]">
                            {doubt.author?.is_anonymous ? 'Anonymous Student' : (doubt.author?.display_name || 'Student')}
                          </span>
                          <span className="text-xs text-slate-400">•</span>
                          <span className="text-[11px] font-semibold text-[#0A8FF5] bg-[#EAF5FF] px-2 py-0.5 rounded-md">
                            {doubt.concept_name || 'Unmapped concept'}
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-[#111111] mt-1">
                          {doubt.title}
                        </h3>
                      </div>
                      <div>
                        {hasVerifiedAnswer ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
                            <CheckCircle className="w-3 h-3 text-emerald-600" />
                            Faculty Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700 bg-amber-50 px-2.5 py-0.5 rounded-full border border-amber-200">
                            <HelpCircle className="w-3 h-3 text-amber-600" />
                            Awaiting Verification
                          </span>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-xl mb-3">
                      {doubt.body_markdown}
                    </p>

                    {/* Existing Answers */}
                    {(doubt.answers || []).length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-100 space-y-2.5">
                        <h4 className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                          Submitted Answers ({(doubt.answers || []).length})
                        </h4>
                        {(doubt.answers || []).map((ans) => (
                          <div
                            key={ans.id}
                            className={`p-3 rounded-xl border text-xs ${
                              ans.is_teacher_verified
                                ? 'bg-emerald-50/60 border-emerald-200'
                                : 'bg-white border-slate-200'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1.5">
                              <span className="font-bold text-slate-800">
                                {ans.author?.display_name || 'Community Member'}
                              </span>
                              {ans.is_teacher_verified ? (
                                <span className="text-[11px] font-bold text-emerald-700 flex items-center gap-1">
                                  <CheckCircle className="w-3.5 h-3.5" /> Endorsed by Faculty
                                </span>
                              ) : (
                                <button
                                  onClick={() => handleVerifyAnswer(ans.id, doubt.id)}
                                  className="text-[11px] font-bold text-emerald-600 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100 px-2.5 py-1 rounded-full border border-emerald-200 transition cursor-pointer"
                                >
                                  Verify This Solution
                                </button>
                              )}
                            </div>
                            <p className="text-slate-700 leading-relaxed">{ans.body_markdown}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Faculty Quick Answer Form */}
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      {replyingDoubtId === doubt.id ? (
                        <div className="space-y-2">
                          <textarea
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            placeholder="Write authoritative faculty explanation..."
                            rows={3}
                            className="w-full text-xs p-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#0A8FF5]/30 focus:border-[#0A8FF5]"
                          />
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => {
                                setReplyingDoubtId(null);
                                setReplyText('');
                              }}
                              className="btn-outline text-xs px-3 py-1.5 cursor-pointer"
                            >
                              Cancel
                            </button>
                            <button
                              onClick={() => handleSubmitTeacherAnswer(doubt.id)}
                              className="btn-primary text-xs px-4 py-1.5 flex items-center gap-1.5 cursor-pointer"
                            >
                              <Send className="w-3.5 h-3.5" /> Post Faculty Answer
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setReplyingDoubtId(doubt.id)}
                          className="text-xs font-semibold text-[#0A8FF5] hover:underline flex items-center gap-1 cursor-pointer"
                        >
                          <Send className="w-3.5 h-3.5" /> Provide Faculty Answer
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="card-base p-10 text-center text-slate-400">
              <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-xs font-semibold text-slate-600">No Pending Doubts in Queue</p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                All student questions currently have verified explanations.
              </p>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Concept Gap Diagnostics & Analytics */}
      {activeTab === 'analytics' && (
        <TeacherAnalyticsPage offerings={offerings} />
      )}
    </div>
  );
};
