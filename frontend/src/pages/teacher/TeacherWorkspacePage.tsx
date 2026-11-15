import React, { useState, useMemo, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { DesktopSidebar } from '../../components/layout/DesktopSidebar';
import { RightSidebar } from '../../components/sidebar/RightSidebar';
import { FeedFilters } from '../../components/feed/FeedFilters';
import { FeedCard } from '../../components/feed/FeedCard';
import { PostDetailView } from '../../components/post/PostDetailView';
import { ToastNotification } from '../../components/ui/ToastNotification';
import { TeacherLearnWorkspace } from './TeacherLearnWorkspace';
import { TeacherMaterialsPage } from './TeacherMaterialsPage';
import { TeacherAnalyticsPage } from './TeacherAnalyticsPage';
import { QuizView } from '../../components/academic/QuizView';
import { PYQView } from '../../components/academic/PYQView';
import { useAuth } from '../../contexts/AuthContext';
import { useAcademicOfferings } from '../../hooks/useAcademicOfferings';
import { useDoubtsFeed } from '../../hooks/useDoubtsFeed';
import type { DoubtItem } from '../../data/doubtsData';

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

export const TeacherWorkspacePage: React.FC = () => {
  const { user, isLoading: authLoading } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const [activeNavTab, setActiveNavTab] = useState(() =>
    resolveTabFromLocation(location.pathname, location.search)
  );
  const [selectedSubject, setSelectedSubject] = useState('all');
  const [filterMode, setFilterMode] = useState('all');
  const [sortBy, setSortBy] = useState('recent');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'feed' | 'post'>('feed');
  const [activeDoubtId, setActiveDoubtId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => setToastMessage(msg);

  // Custom hooks to deduplicate logic
  const { offerings, enrolledSubjects } = useAcademicOfferings('TEACHER');
  const {
    doubts,
    isLoading: isDoubtsLoading,
    hasError: doubtsLoadError,
    teacherDoubtSummary,
    toggleBookmark,
    toggleThanks,
    addComment,
    addAnswer,
  } = useDoubtsFeed();

  // Sync route changes
  useEffect(() => {
    setActiveNavTab(resolveTabFromLocation(location.pathname, location.search));
    setViewMode('feed');
    setActiveDoubtId(null);
  }, [location.pathname, location.search]);

  const handleNavTabSelect = (tabId: string) => {
    setActiveNavTab(tabId);
    setViewMode('feed');
    setActiveDoubtId(null);

    const targetRoute = ROUTE_BY_TAB[tabId];
    if (targetRoute && `${location.pathname}${location.search}` !== targetRoute) {
      navigate(targetRoute);
    }
  };

  const handleBackToFeed = () => {
    setViewMode('feed');
    setActiveDoubtId(null);
    if (location.pathname !== '/doubts') navigate('/doubts');
  };

  // Filter & Search Logic
  const filteredDoubts = useMemo(() => {
    return doubts
      .filter((d) => {
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchQuestion = d.doubtQuestion.toLowerCase().includes(q);
          const matchStudent = d.studentName.toLowerCase().includes(q);
          const matchSubject = d.subject.toLowerCase().includes(q);
          const matchTopic = d.topic.toLowerCase().includes(q);
          const matchAnswer = d.answers.some(
            (a) => a.answeredBy.toLowerCase().includes(q) || a.content.toLowerCase().includes(q)
          );
          if (!matchQuestion && !matchStudent && !matchSubject && !matchTopic && !matchAnswer) {
            return false;
          }
        }

        if (selectedSubject !== 'all') {
          const selected = enrolledSubjects.find((subject) => subject.id === selectedSubject);
          if (!selected) return false;
          const subjectName = selected.name.toLowerCase();
          const subjectCode = selected.code.toLowerCase();
          const matchesSubject =
            d.subject.toLowerCase().includes(subjectName) ||
            d.topic.toLowerCase().includes(subjectName) ||
            (subjectCode !== '' &&
              [d.subject, d.topic, d.doubtQuestion].some((v) => v.toLowerCase().includes(subjectCode)));
          if (!matchesSubject) return false;
        }

        if (filterMode === 'verified') {
          return d.answers.some((a) => a.isVerifiedByTeacher);
        }
        if (filterMode === 'unanswered') {
          return d.answers.length === 0;
        }
        if (filterMode === 'needs_verification') {
          return d.answers.length > 0 && !d.answers.some((a) => a.isVerifiedByTeacher);
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

  const activeDoubt = useMemo(() => {
    if (!activeDoubtId) return null;
    return doubts.find((d) => d.id === activeDoubtId) || null;
  }, [doubts, activeDoubtId]);

  const facultyDisplayName =
    user?.fullName || user?.full_name || user?.email?.split('@')[0] || 'Dr. R. K. Sharma';

  if (authLoading) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F8FAFC] text-sm text-slate-600">
        Loading faculty workspace…
      </div>
    );
  }

  const isLearnTab = activeNavTab === 'learn';

  return (
    <>
      <AppLayout
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          if (viewMode !== 'feed') {
            setViewMode('feed');
            navigate('/doubts');
          }
        }}
        onNavigateHome={handleBackToFeed}
        activeTab={activeNavTab}
        onSelectTab={handleNavTabSelect}
        fullWidthMain={isLearnTab}
        leftSidebar={
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
        }
        rightSidebar={
          !isLearnTab ? (
            <RightSidebar
              role="TEACHER"
              teacherOfferings={offerings}
              facultyName={facultyDisplayName}
              avatarUrl={user?.avatar_url || user?.avatarUrl}
              teacherDoubtSummary={teacherDoubtSummary}
              activeFilterMode={filterMode}
              onSelectDoubtFilter={(mode) => {
                setFilterMode(mode);
                setActiveNavTab('doubts');
                setViewMode('feed');
                setActiveDoubtId(null);
              }}
            />
          ) : undefined
        }
      >
        {viewMode === 'post' && activeDoubt ? (
          <PostDetailView
            doubt={activeDoubt}
            onBackToFeed={handleBackToFeed}
            onToggleBookmark={toggleBookmark}
            onToggleThanks={toggleThanks}
            onAddComment={addComment}
            onSubmitNewAnswer={async (doubtId, answerText) => {
              await addAnswer(doubtId, answerText);
              showToast('Your faculty response was published.');
            }}
            onShowToast={showToast}
          />
        ) : activeNavTab === 'learn' ? (
          <TeacherLearnWorkspace offerings={offerings} selectedSubject={selectedSubject} />
        ) : activeNavTab === 'quiz' ? (
          <QuizView offerings={offerings} selectedSubject={selectedSubject} onShowToast={showToast} />
        ) : activeNavTab === 'pyq' ? (
          <PYQView selectedSubject={selectedSubject} />
        ) : activeNavTab === 'studymaterial' ? (
          <TeacherMaterialsPage embedded />
        ) : activeNavTab === 'teacher_analytics' ? (
          <TeacherAnalyticsPage offerings={offerings} />
        ) : (
          <>
            <FeedFilters
              currentFilter={filterMode}
              onFilterChange={(f) => setFilterMode(f)}
              sortBy={sortBy}
              onSortChange={(s) => setSortBy(s)}
              totalCount={filteredDoubts.length}
            />

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
                {filteredDoubts.map((doubt: DoubtItem) => (
                  <FeedCard
                    key={doubt.id}
                    doubt={doubt}
                    onSelectDoubt={(id) => {
                      setActiveDoubtId(id);
                      setViewMode('post');
                    }}
                    onAnswerDoubt={(doubtId) => {
                      setActiveDoubtId(doubtId);
                      setViewMode('post');
                    }}
                    onToggleBookmark={toggleBookmark}
                    onToggleThanks={toggleThanks}
                    onAddComment={addComment}
                    onShowToast={showToast}
                  />
                ))}
              </div>
            ) : (
              <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-12 text-center my-6">
                <p className="text-sm font-semibold text-[#111111]">No doubts found for this filter</p>
                <button
                  type="button"
                  onClick={() => {
                    setFilterMode('all');
                    setSelectedSubject('all');
                    setSearchQuery('');
                  }}
                  className="mt-3 btn-outline text-xs px-5 py-2 cursor-pointer"
                >
                  Reset Filters
                </button>
              </div>
            )}
          </>
        )}
      </AppLayout>

      <ToastNotification message={toastMessage} onClose={() => setToastMessage(null)} />
    </>
  );
};
