import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
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
import { useAuth } from '../../contexts/AuthContext';
import { useAcademicOfferings } from '../../hooks/useAcademicOfferings';
import { useDoubtsFeed, mapApiDoubt } from '../../hooks/useDoubtsFeed';
import { apiClient } from '../../api/client';
import type { DoubtItem } from '../../data/doubtsData';

const ROUTE_BY_TAB: Record<string, string> = {
  doubts: '/doubts',
  learn: '/courses',
  quiz: '/quiz',
  pyq: '/pyq',
  studymaterial: '/materials',
};

const TAB_BY_ROUTE: Record<string, string> = {
  '/doubts': 'doubts',
  '/courses': 'learn',
  '/quiz': 'quiz',
  '/pyq': 'pyq',
  '/materials': 'studymaterial',
};

const resolveTabFromLocation = (pathname: string, search: string): string => {
  const tabParam = new URLSearchParams(search).get('tab');
  if (tabParam && tabParam in ROUTE_BY_TAB) {
    return tabParam;
  }
  return TAB_BY_ROUTE[pathname] ?? 'doubts';
};

export const StudentFeedPage: React.FC = () => {
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
  const [viewMode, setViewMode] = useState<'feed' | 'post' | 'profile'>('feed');
  const [activeDoubtId, setActiveDoubtId] = useState<string | null>(null);

  const [isAskModalOpen, setIsAskModalOpen] = useState(false);
  const [answeringDoubt, setAnsweringDoubt] = useState<DoubtItem | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [myStats, setMyStats] = useState<MyDoubtStats | null>(null);
  const [isStatsLoading, setIsStatsLoading] = useState(true);

  const showToast = (msg: string) => setToastMessage(msg);

  // Shared hooks
  const { offerings: studentOfferings, enrolledSubjects } = useAcademicOfferings('STUDENT');
  const {
    doubts,
    setDoubts,
    isLoading: isDoubtsLoading,
    hasError: doubtsLoadError,
    toggleBookmark,
    toggleThanks,
    addComment,
    addAnswer,
  } = useDoubtsFeed();

  const refreshMyStats = useCallback(async () => {
    try {
      const s = await apiClient.get<MyDoubtStats>('/api/v1/doubts/me/stats');
      setMyStats(s);
    } catch {
      // Keep previous stats
    } finally {
      setIsStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshMyStats();
  }, [refreshMyStats]);

  // Sync route
  useEffect(() => {
    if (location.pathname === '/profile') {
      setViewMode('profile');
      return;
    }
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

  const handleOpenProfile = () => {
    setViewMode('profile');
    if (location.pathname !== '/profile') navigate('/profile');
  };

  const handleBackToFeed = () => {
    setViewMode('feed');
    setActiveDoubtId(null);
    if (location.pathname !== '/doubts') navigate('/doubts');
  };

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
      await addAnswer(doubtId, answerText);
      refreshMyStats();
      showToast('Your answer was submitted.');
    } catch {
      showToast('Your answer could not be submitted. Please try again.');
    }
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
            (a) =>
              a.answeredBy.toLowerCase().includes(q) ||
              a.content.toLowerCase().includes(q)
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

  const studentDisplayName =
    user?.fullName || user?.full_name || user?.email?.split('@')[0] || 'Student';
  const studentSemester = 'Enrolled Student';

  if (authLoading) {
    return (
      <div className="min-h-screen grid place-items-center bg-[#F8FAFC] text-sm text-slate-600">
        Loading student workspace…
      </div>
    );
  }

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
        onOpenAskModal={() => setIsAskModalOpen(true)}
        onOpenProfile={handleOpenProfile}
        onNavigateHome={handleBackToFeed}
        activeTab={activeNavTab}
        onSelectTab={handleNavTabSelect}
        leftSidebar={
          viewMode !== 'profile' ? (
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
          ) : undefined
        }
        rightSidebar={
          viewMode !== 'profile' ? (
            <RightSidebar
              role="STUDENT"
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
          ) : undefined
        }
      >
        {viewMode === 'profile' ? (
          <ProfilePage
            onBackToFeed={handleBackToFeed}
            allDoubts={doubts}
            studentName={studentDisplayName}
            avatarUrl={user?.avatar_url || user?.avatarUrl}
            stats={myStats}
            onSelectDoubt={(doubtId) => {
              setActiveDoubtId(doubtId);
              setViewMode('post');
            }}
          />
        ) : viewMode === 'post' && activeDoubt ? (
          <PostDetailView
            doubt={activeDoubt}
            onBackToFeed={handleBackToFeed}
            onToggleBookmark={toggleBookmark}
            onToggleThanks={toggleThanks}
            onAddComment={addComment}
            onSubmitNewAnswer={handleAddNewAnswer}
            onShowToast={showToast}
          />
        ) : activeNavTab === 'learn' ? (
          <LearnView selectedSubject={selectedSubject} offerings={studentOfferings} />
        ) : activeNavTab === 'quiz' ? (
          <QuizView offerings={studentOfferings} selectedSubject={selectedSubject} onShowToast={showToast} />
        ) : activeNavTab === 'pyq' ? (
          <PYQView selectedSubject={selectedSubject} />
        ) : activeNavTab === 'studymaterial' ? (
          <StudyMaterialView selectedSubject={selectedSubject} offerings={studentOfferings} />
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
                      const target = doubts.find((d) => d.id === doubtId) || doubt;
                      setAnsweringDoubt(target);
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

      <AnswerDoubtModal
        doubt={answeringDoubt}
        onClose={() => setAnsweringDoubt(null)}
        onSubmitAnswer={handleAddNewAnswer}
      />

      <ToastNotification message={toastMessage} onClose={() => setToastMessage(null)} />
    </>
  );
};
