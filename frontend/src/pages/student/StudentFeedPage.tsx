import React, { useState, useMemo, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppHeader } from '../../components/layout/AppHeader';
import { SecondaryNav } from '../../components/layout/SecondaryNav';
import { DesktopSidebar } from '../../components/layout/DesktopSidebar';
import { RightSidebar, type MyDoubtStats } from '../../components/sidebar/RightSidebar';
import { FeedFilters } from '../../components/feed/FeedFilters';
import { FeedCard } from '../../components/feed/FeedCard';
import { PostDetailView } from '../../components/post/PostDetailView';
import { ProfilePage } from '../../components/profile/ProfilePage';
import { AskDoubtModal, AskDoubtSubmission } from '../../components/modals/AskDoubtModal';
import { AnswerDoubtModal } from '../../components/modals/AnswerDoubtModal';
import { ToastNotification } from '../../components/ui/ToastNotification';
import { LearnView } from '../../components/academic/LearnView';
import { QuizView } from '../../components/academic/QuizView';
import { PYQView } from '../../components/academic/PYQView';
import { StudyMaterialView } from '../../components/academic/StudyMaterialView';
import { TeacherMaterialsPage } from '../teacher/TeacherMaterialsPage';
import { TeacherAnalyticsPage } from '../teacher/TeacherAnalyticsPage';
import { TeacherLearnWorkspace } from '../teacher/TeacherLearnWorkspace';
import type { EnrolledSubjectItem } from '../../components/layout/DesktopSidebar';
import type { CourseOffering } from '../../types/academics';
import { DoubtItem } from '../../data/doubtsData';
import { useAuth } from '../../contexts/AuthContext';
import { apiClient } from '../../api/client';
import { HelpCircle } from 'lucide-react';

const formatApiDate = (value?: string) => {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
};

const mapApiDoubt = (d: any): DoubtItem => ({
  id: String(d.id),
  studentName: d.author?.is_anonymous ? 'Anonymous Student' : (d.author?.display_name || 'Student'),
  studentAvatar: d.author?.avatar_url || '',
  studentGrade: d.author?.role_label || '',
  subject: d.concept_name || 'Uncategorized',
  topic: d.title,
  askedAt: formatApiDate(d.created_at),
  createdAtTimestamp: d.created_at ? new Date(d.created_at).getTime() : 0,
  rewardPoints: 0,
  doubtQuestion: d.body_markdown,
  viewsCount: 0,
  isBookmarked: false,
  answers: (d.answers || []).map((a: any) => {
    const isTeacher =
      String(a.author?.role_label || '').toLowerCase().includes('teacher') ||
      Boolean(a.is_teacher_verified) ||
      ['dr.', 'prof.', 'dr ', 'prof '].some((p) => String(a.author?.display_name || '').toLowerCase().startsWith(p));
    const roleLabel = isTeacher ? 'Teacher' : (a.author?.role_label || 'Student');
    return {
      id: String(a.id),
      answeredBy: a.author?.is_anonymous ? 'Anonymous Student' : (a.author?.display_name || 'Community Member'),
      authorAvatar: a.author?.avatar_url || '',
      authorRank: roleLabel,
      authorTitle: (a.is_teacher_verified || isTeacher) ? 'Faculty Verified' : roleLabel,
      content: a.body_markdown,
      isVerifiedByTeacher: Boolean(a.is_teacher_verified || isTeacher),
      thanksCount: a.upvote_count ?? 0,
      hasThanked: Boolean(a.has_thanked),
      answeredAt: formatApiDate(a.created_at),
      comments: (a.comments || []).map((c: any) => {
        const isCommentTeacher =
          String(c.author?.role_label || '').toLowerCase().includes('teacher') ||
          ['dr.', 'prof.', 'dr ', 'prof '].some((p) => String(c.author?.display_name || '').toLowerCase().startsWith(p));
        return {
          id: String(c.id),
          author: c.author?.is_anonymous ? 'Anonymous Student' : (c.author?.display_name || 'Community Member'),
          avatar: c.author?.avatar_url || '',
          role: isCommentTeacher ? 'Teacher' : 'Student',
          text: c.body_markdown,
          createdAt: formatApiDate(c.created_at),
          likes: 0,
        };
      }),
    };
  }),
});

const ROUTE_BY_TAB: Record<string, string> = {
  doubts: '/doubts',
  learn: '/courses',
  quiz: '/quiz',
  pyq: '/pyq',
  studymaterial: '/materials',
  teacher_analytics: '/analytics',
};

const TAB_BY_ROUTE: Record<string, string> = {
  '/doubts': 'doubts',
  '/courses': 'learn',
  '/quiz': 'quiz',
  '/pyq': 'pyq',
  '/materials': 'studymaterial',
  '/analytics': 'teacher_analytics',
};

const resolveTabFromLocation = (pathname: string, search: string): string => {
  const tabParam = new URLSearchParams(search).get('tab');
  if (tabParam && tabParam in ROUTE_BY_TAB) {
    return tabParam;
  }
  return TAB_BY_ROUTE[pathname] ?? 'doubts';
};

export const StudentFeedPage: React.FC = () => {
  const { user, role, isLoading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [doubts, setDoubts] = useState<DoubtItem[]>([]);
  const [isDoubtsLoading, setIsDoubtsLoading] = useState(true);
  const [doubtsLoadError, setDoubtsLoadError] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('all');
  const [filterMode, setFilterMode] = useState('all'); // 'all' | 'verified' | 'unanswered' | 'bookmarked'
  const [sortBy, setSortBy] = useState('recent'); // 'recent' | 'helpful' | 'points'
  const [activeNavTab, setActiveNavTab] = useState(() =>
    resolveTabFromLocation(location.pathname, location.search)
  );
  const [userPoints] = useState(655);
  const [enrolledSubjects, setEnrolledSubjects] = useState<EnrolledSubjectItem[]>([]);
  const [studentOfferings, setStudentOfferings] = useState<CourseOffering[]>([]);
  const [teacherOfferings, setTeacherOfferings] = useState<CourseOffering[]>([]);
  const [myStats, setMyStats] = useState<MyDoubtStats | null>(null);
  const [isStatsLoading, setIsStatsLoading] = useState(true);

  // App Navigation View Mode: 'feed' | 'post' | 'profile'
  const [viewMode, setViewMode] = useState<'feed' | 'post' | 'profile'>('feed');
  const [activeDoubtId, setActiveDoubtId] = useState<string | null>(null);

  // Modals state
  const [isAskModalOpen, setIsAskModalOpen] = useState(false);
  const [answeringDoubt, setAnsweringDoubt] = useState<DoubtItem | null>(null);

  // Toast state
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
  };

  // Sync URL route with activeNavTab / viewMode
  useEffect(() => {
    if (location.pathname === '/profile') {
      setViewMode('profile');
      return;
    }

    setActiveNavTab(resolveTabFromLocation(location.pathname, location.search));
    setViewMode('feed');
    setActiveDoubtId(null);
  }, [location.pathname, location.search]);

  // Handle Tab changes
  const handleNavTabSelect = (tabId: string) => {
    setActiveNavTab(tabId);
    setViewMode('feed');
    setActiveDoubtId(null);

    const targetRoute = ROUTE_BY_TAB[tabId];
    if (targetRoute && `${location.pathname}${location.search}` !== targetRoute) {
      navigate(targetRoute);
    }
  };

  const handleOpenProfile = () => {
    setViewMode('profile');
    if (location.pathname !== '/profile') navigate('/profile');
  };

  const handleBackToFeed = () => {
    setViewMode('feed');
    setActiveDoubtId(null);
    if (location.pathname !== '/doubts') navigate('/doubts');
  };

  // Fetch live doubts and user stats from backend API
  const refreshMyStats = async () => {
    try {
      const s = await apiClient.get<MyDoubtStats>('/api/v1/doubts/me/stats');
      setMyStats(s);
    } catch {
      // Keep previous stats on transient failure
    } finally {
      setIsStatsLoading(false);
    }
  };

  useEffect(() => {
    const fetchLiveDoubts = async () => {
      try {
        const rows = await apiClient.get<any[]>('/api/v1/doubts');
        setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
        setDoubtsLoadError(false);
      } catch {
        setDoubts([]);
        setDoubtsLoadError(true);
      } finally {
        setIsDoubtsLoading(false);
      }
    };
    fetchLiveDoubts();
    refreshMyStats();
  }, []);

  const toSubjectItems = (offerings: CourseOffering[]): EnrolledSubjectItem[] => {
    const subjects = new Map<string, EnrolledSubjectItem>();
    for (const offering of offerings) {
      const id = offering.curriculum_subject_entry_id;
      const code = offering.official_subject_code?.trim() ?? '';
      const name = offering.subject_name?.trim() || code;
      if (id && name && !subjects.has(id)) subjects.set(id, { id, code, name });
    }
    return [...subjects.values()];
  };

  useEffect(() => {
    if (role === 'TEACHER') {
      let cancelled = false;
      apiClient.get<CourseOffering[]>('/api/v1/academics/teacher/offerings')
        .then((rows) => {
          if (cancelled) return;
          const list = Array.isArray(rows) ? rows : [];
          setTeacherOfferings(list);
          setEnrolledSubjects(toSubjectItems(list));
        })
        .catch(() => {
          if (!cancelled) {
            setTeacherOfferings([]);
            setEnrolledSubjects([]);
          }
        });
      return () => { cancelled = true; };
    }

    setTeacherOfferings([]);
    if (role !== 'STUDENT') {
      setEnrolledSubjects([]);
      setStudentOfferings([]);
      return;
    }

    let cancelled = false;
    apiClient.get<CourseOffering[]>('/api/v1/academics/student/offerings')
      .then((offerings) => {
        if (cancelled) return;
        setStudentOfferings(offerings);
        setEnrolledSubjects(toSubjectItems(offerings));
      })
      .catch(() => {
        if (!cancelled) {
          setEnrolledSubjects([]);
          setStudentOfferings([]);
        }
      });

    return () => { cancelled = true; };
  }, [role]);

  // Currently selected doubt for detail view
  const activeDoubt = useMemo(() => {
    if (!activeDoubtId) return null;
    return doubts.find((d) => d.id === activeDoubtId) || null;
  }, [doubts, activeDoubtId]);

  // Filter & Search Logic
  const filteredDoubts = useMemo(() => {
    return doubts
      .filter((d) => {
        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchQuestion = d.doubtQuestion.toLowerCase().includes(q);
          const matchStudent = d.studentName.toLowerCase().includes(q);
          const matchSubject = d.subject.toLowerCase().includes(q);
          const matchTopic = d.topic.toLowerCase().includes(q);
          const matchAnswer = d.answers.some(
            (a) =>
              a.answeredBy.toLowerCase().includes(q) ||
              a.content.toLowerCase().includes(q) ||
              (a.points && a.points.some((p) => p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)))
          );
          if (!matchQuestion && !matchStudent && !matchSubject && !matchTopic && !matchAnswer) {
            return false;
          }
        }

        // Subject or Enrolled Course filter
        if (selectedSubject !== 'all') {
          const selected = enrolledSubjects.find((subject) => subject.id === selectedSubject);
          if (!selected) return false;
          const subjectName = selected.name.toLowerCase();
          const subjectCode = selected.code.toLowerCase();
          const matchesSubject = d.subject.toLowerCase().includes(subjectName) ||
            d.topic.toLowerCase().includes(subjectName) ||
            (subjectCode !== '' && [d.subject, d.topic, d.doubtQuestion].some((value) => value.toLowerCase().includes(subjectCode)));
          if (!matchesSubject) return false;
        }

        // Filter mode
        if (filterMode === 'verified') {
          return d.answers.some((a) => a.isVerifiedByTeacher);
        }
        if (filterMode === 'unanswered') {
          return d.answers.length === 0;
        }
        if (filterMode === 'bookmarked') {
          return d.isBookmarked === true;
        }

        return true;
      })
      .sort((a, b) => {
        if (sortBy === 'recent') {
          return (b.createdAtTimestamp ?? 0) - (a.createdAtTimestamp ?? 0);
        }
        if (sortBy === 'points') {
          return b.rewardPoints - a.rewardPoints;
        }
        if (sortBy === 'helpful') {
          const aThanks = a.answers.reduce((acc, ans) => acc + ans.thanksCount, 0);
          const bThanks = b.answers.reduce((acc, ans) => acc + ans.thanksCount, 0);
          return bThanks - aThanks;
        }
        return 0;
      });
  }, [doubts, searchQuery, selectedSubject, enrolledSubjects, filterMode, sortBy]);

  const handleAddNewDoubt = async (doubtData: AskDoubtSubmission) => {
    try {
      const offering = studentOfferings.find((item) => item.id === doubtData.courseOfferingId);
      const posted = await apiClient.post<any>('/api/v1/doubts', {
        title: doubtData.question.slice(0, 255),
        body_markdown: doubtData.question,
        course_offering_id: doubtData.courseOfferingId,
        is_anonymous_to_peers: doubtData.isAnonymousToPeers,
        visibility: 'course',
      });
      const mapped = mapApiDoubt({
        ...posted,
        concept_name: posted.concept_name || offering?.subject_name || offering?.official_subject_code,
      });
      setDoubts((prev) => [mapped, ...prev]);
      refreshMyStats();
      showToast('Your question was posted to the campus feed.');
    } catch {
      showToast('Your question could not be posted. Please try again.');
    }
  };

  const handleAddNewAnswer = async (doubtId: string, answerText: string) => {
    try {
      await apiClient.post(`/api/v1/doubts/${doubtId}/answers`, { body_markdown: answerText });
      const rows = await apiClient.get<any[]>('/api/v1/doubts');
      setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
      refreshMyStats();
      showToast('Your answer was submitted.');
    } catch {
      showToast('Your answer could not be submitted. Please try again.');
    }
  };
  const handleToggleBookmark = (doubtId: string) => {
    setDoubts((prev) =>
      prev.map((d) => {
        if (d.id === doubtId) {
          const nextState = !d.isBookmarked;
          showToast(nextState ? 'Doubt saved to your bookmarks!' : 'Doubt removed from bookmarks');
          return { ...d, isBookmarked: nextState };
        }
        return d;
      })
    );
  };

  const handleToggleThanks = async (doubtId: string, answerId: string) => {
    const existingDoubt = doubts.find((d) => d.id === doubtId);
    const existingAnswer = existingDoubt?.answers.find((a) => a.id === answerId);
    if (existingAnswer?.hasThanked) return;

    try {
      const res = await apiClient.post<{
        upvote_count: number;
        has_thanked: boolean;
        already_thanked: boolean;
      }>(`/api/v1/doubts/answers/${answerId}/thank`);

      setDoubts((prev) =>
        prev.map((d) => {
          if (d.id !== doubtId) return d;
          return {
            ...d,
            answers: d.answers.map((a) =>
              a.id === answerId
                ? { ...a, thanksCount: res.upvote_count, hasThanked: Boolean(res.has_thanked) }
                : a
            ),
          };
        })
      );
      refreshMyStats();
      showToast(res.already_thanked ? 'You have already thanked this answer.' : 'Thanked answer author!');
    } catch {
      showToast('Could not record your thanks. Please try again.');
    }
  };

  const handleAddComment = async (doubtId: string, answerId: string, commentText: string) => {
    try {
      await apiClient.post(`/api/v1/doubts/${doubtId}/comments`, {
        answer_id: answerId,
        body_markdown: commentText,
      });
      const rows = await apiClient.get<any[]>('/api/v1/doubts');
      setDoubts(Array.isArray(rows) ? rows.map(mapApiDoubt) : []);
    } catch {
      showToast('Your comment could not be submitted. Please try again.');
    }
  };

  const studentDisplayName =
    user?.fullName || user?.full_name || user?.email?.split('@')[0] || 'Student';
  const studentSemester = role === 'TEACHER' ? 'Faculty' : 'Enrolled Student';

  if (authLoading) {
    return <div className="min-h-screen grid place-items-center bg-[#F8FAFC] text-sm text-slate-600">Loading your workspace…</div>;
  }

  const isTeacherLearn = role === 'TEACHER' && activeNavTab === 'learn';

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex flex-col">
      {/* 1. Global Header with prototype styling and functionality */}
      <AppHeader
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          if (viewMode !== 'feed') {
            setViewMode('feed');
            navigate('/doubts');
          }
        }}
        onOpenAskModal={() => setIsAskModalOpen(true)}
        onOpenProfile={handleOpenProfile}
        onNavigateHome={handleBackToFeed}
      />

      {/* 2. Secondary Academic Navigation Strip */}
      <SecondaryNav
        activeTab={activeNavTab}
        onSelectTab={handleNavTabSelect}
        role={role}
      />

      {/* 3. Conditional Page Render: Full Profile Page vs Main 3-Column Layout */}
      {viewMode === 'profile' ? (
        <ProfilePage
          onBackToFeed={handleBackToFeed}
          userPoints={userPoints}
          allDoubts={doubts}
          studentName={studentDisplayName}
          semester={studentSemester}
          avatarUrl={user?.avatar_url || user?.avatarUrl}
          stats={myStats}
        />
      ) : (
        <main className="flex-1 w-full max-w-[1540px] mx-auto px-3 sm:px-6 py-5 sm:py-6">
          <div
            className={`grid grid-cols-1 ${
              isTeacherLearn
                ? 'md:grid-cols-[210px_minmax(0,1fr)] lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)]'
                : 'md:grid-cols-[210px_minmax(0,1fr)] lg:grid-cols-[200px_minmax(0,1fr)_290px] xl:grid-cols-[230px_minmax(0,1fr)_320px] 2xl:grid-cols-[240px_minmax(0,820px)_340px]'
            } gap-4 lg:gap-5 xl:gap-7 justify-center`}
          >
            
            {/* Column 1: Left Subjects Navigation Column */}
            <DesktopSidebar
              selectedSubject={selectedSubject}
              onSelectSubject={(id) => {
                setSelectedSubject(id);
                setViewMode('feed');
                setActiveDoubtId(null);
              }}
              filterMode={filterMode}
              onSelectFilterMode={(mode) => {
                setFilterMode(mode);
                setViewMode('feed');
                setActiveDoubtId(null);
              }}
              activeNavTab={activeNavTab}
              enrolledSubjects={enrolledSubjects}
            />

            {/* Column 2: Main Content Column */}
            <section className={`min-w-0 ${isTeacherLearn ? 'w-full' : 'max-w-[820px] w-full mx-auto md:mx-0'}`}>
              {viewMode === 'post' && activeDoubt ? (
                /* DEDICATED POST DETAIL VIEW */
                <PostDetailView
                  doubt={activeDoubt}
                  onBackToFeed={handleBackToFeed}
                  onToggleBookmark={handleToggleBookmark}
                  onToggleThanks={handleToggleThanks}
                  onAddComment={handleAddComment}
                  onSubmitNewAnswer={handleAddNewAnswer}
                  onShowToast={showToast}
                />
              ) : activeNavTab === 'learn' ? (
                /* AI ADAPTIVE LEARNING & WEAKNESS REMEDIATION */
                role === 'TEACHER' ? (
                  <TeacherLearnWorkspace offerings={teacherOfferings} selectedSubject={selectedSubject} />
                ) : (
                  <LearnView
                    selectedSubject={selectedSubject}
                    offerings={studentOfferings}
                  />
                )
              ) : activeNavTab === 'quiz' ? (
                /* COURSE QUIZZES, ASSESSMENTS & TARGETED SUPPORT */
                <QuizView
                  offerings={role === 'TEACHER' ? teacherOfferings : studentOfferings}
                  selectedSubject={selectedSubject}
                  onShowToast={showToast}
                />
              ) : activeNavTab === 'pyq' ? (
                /* PREVIOUS YEAR QUESTIONS (PYQ) ARCHIVE */
                <PYQView selectedSubject={selectedSubject} />
              ) : activeNavTab === 'studymaterial' ? (
                /* TEACHER LECTURE SLIDES & STUDY MATERIAL */
                role === 'TEACHER' ? (
                  <TeacherMaterialsPage embedded />
                ) : (
                  <StudyMaterialView
                    selectedSubject={selectedSubject}
                    offerings={studentOfferings}
                  />
                )
              ) : activeNavTab === 'teacher_analytics' ? (
                <TeacherAnalyticsPage offerings={teacherOfferings} />
              ) : (
                /* COMMUNITY FEED VIEW */
                <>
                  {/* Feed Filters */}
                  <FeedFilters
                    currentFilter={filterMode}
                    onFilterChange={(f) => setFilterMode(f)}
                    sortBy={sortBy}
                    onSortChange={(s) => setSortBy(s)}
                    totalCount={filteredDoubts.length}
                  />

                  {/* Doubts Feed */}
                  {isDoubtsLoading ? (
                    <div className="border border-[#DCE7EE] rounded-[14px] bg-white p-8 text-center my-6 text-sm text-[#71808C]">
                      Loading questions…
                    </div>
                  ) : doubtsLoadError ? (
                    <div className="border border-[#DCE7EE] rounded-[14px] bg-white p-8 text-center my-6 text-sm text-[#71808C]">
                      Questions could not be loaded. Please refresh and try again.
                    </div>
                  ) : filteredDoubts.length > 0 ? (
                    <div className="space-y-5 sm:space-y-6">
                      {filteredDoubts.map((doubt) => (
                        <FeedCard
                          key={doubt.id}
                          doubt={doubt}
                          onSelectDoubt={(id) => {
                            setActiveDoubtId(id);
                            setViewMode('post');
                          }}
                          onAnswerDoubt={(id) => {
                            const d = doubts.find((item) => item.id === id);
                            if (d) setAnsweringDoubt(d);
                          }}
                          onToggleBookmark={handleToggleBookmark}
                          onAddComment={handleAddComment}
                          onToggleThanks={handleToggleThanks}
                          onShowToast={showToast}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="border border-[#DCE7EE] rounded-[14px] bg-white p-8 sm:p-12 text-center my-6">
                      <div className="w-12 h-12 rounded-full bg-[#EDF4F8] flex items-center justify-center text-[#71808C] mx-auto mb-3">
                        <HelpCircle className="w-6 h-6" />
                      </div>
                      <h3 className="text-base font-bold text-[#111111] mb-5">
                        {doubts.length === 0 ? 'No doubts posted yet' : 'No doubts found for this filter'}
                      </h3>
                      {doubts.length > 0 && (
                        <button
                          onClick={() => {
                            setSearchQuery('');
                            setFilterMode('all');
                            setSelectedSubject('all');
                            setActiveNavTab('doubts');
                          }}
                          className="btn-outline text-xs px-5 py-2 cursor-pointer"
                        >
                          Reset Filters
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}
            </section>

            {/* Column 3: Right Sidebar — hidden on Teacher Learn tab for maximum studio workspace */}
            {!isTeacherLearn && (
              <RightSidebar
                role={role}
                teacherOfferings={teacherOfferings}
                facultyName={studentDisplayName}
                studentName={studentDisplayName}
                semester={studentSemester}
                avatarUrl={user?.avatar_url || user?.avatarUrl}
                stats={myStats}
                isLoadingStats={isStatsLoading}
                onOpenProfile={handleOpenProfile}
                onSelectContributor={(name) => {
                  setSearchQuery(name);
                  setViewMode('feed');
                  setActiveDoubtId(null);
                  showToast(`Showing questions answered by ${name}`);
                }}
              />
            )}

          </div>
        </main>
      )}

      {/* Ask Doubt Modal */}
      <AskDoubtModal
        isOpen={isAskModalOpen}
        onClose={() => setIsAskModalOpen(false)}
        onSubmitDoubt={handleAddNewDoubt}
        subjects={studentOfferings.map((offering) => ({
          offeringId: offering.id,
          subjectCode: offering.official_subject_code,
          subjectName: offering.subject_name,
          sectionCode: offering.section_code,
        }))}
      />

      {/* Answer Doubt Modal */}
      <AnswerDoubtModal
        doubt={answeringDoubt}
        onClose={() => setAnsweringDoubt(null)}
        onSubmitAnswer={handleAddNewAnswer}
      />

      {/* Toast Notification */}
      <ToastNotification
        message={toastMessage}
        onClose={() => setToastMessage(null)}
      />
    </div>
  );
};
