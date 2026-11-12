import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Brain,
  CheckCircle,
  CheckCircle2,
  HelpCircle,
  Lightbulb,
  Loader2,
  Lock,
  Play,
  RotateCcw,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import type { CourseOffering } from '../../types/academics';

interface PracticeSummary {
  session_id: string;
  status: string;
  current_difficulty: string;
  questions_answered: number;
  correct_count: number;
  target_correct_count: number;
  mistake_count: number;
  easier_followups_triggered: number;
  hints_used: number;
  recovered_after_mistake_count: number;
  repeated_mistakes: boolean;
  needs_easier_questions: boolean;
  improving: boolean;
}

interface LearningNode {
  id: string;
  title: string;
  module_title?: string | null;
  difficulty_rank?: number | null;
  description?: string | null;
  sequence_no: number;
  is_unlocked?: boolean;
  progress_status?: string | null;
  question_count?: number;
  practice_summary?: PracticeSummary | null;
  status: string;
  concept_ids: string[];
}
interface LearningMap { nodes: LearningNode[] }

interface PracticeQuestion {
  activity_version_id: string;
  title: string;
  question: string;
  options: { option_id: string; text: string }[];
  difficulty: 'easy' | 'medium' | 'hard' | string;
  is_remediation: boolean;
  has_hint: boolean;
}

interface PracticeSessionState {
  id: string;
  learning_node_id: string;
  status: string;
  current_difficulty: string;
  in_remediation: boolean;
  target_correct_count: number;
  questions_answered: number;
  correct_count: number;
  mistake_count: number;
  consecutive_mistakes: number;
  easier_followups_triggered: number;
  hints_used: number;
  recovered_after_mistake_count: number;
  repeated_mistakes: boolean;
  needs_easier_questions: boolean;
  improving: boolean;
}

interface PracticeSessionStartResponse {
  node_id: string;
  node_title: string;
  module_title?: string | null;
  session: PracticeSessionState;
  current_question?: PracticeQuestion | null;
}

interface PracticeAnswerResult {
  is_correct: boolean;
  correct_option_id?: string | null;
  explanation: string;
  feedback_summary: string;
  node_completed: boolean;
  session: PracticeSessionState;
  next_question?: PracticeQuestion | null;
}

interface LearnViewProps { onBackToFeed: () => void; selectedSubject?: string; offerings: CourseOffering[] }

const DIFFICULTY_STYLES: Record<string, string> = {
  easy: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  medium: 'bg-amber-50 text-amber-800 border-amber-200',
  hard: 'bg-violet-50 text-violet-700 border-violet-200',
};

const formatRankLabel = (rank?: number | null): string => {
  if (!rank) return 'Topic';
  if (rank <= 2) return `Level ${rank} · Foundational`;
  if (rank <= 4) return `Level ${rank} · Core`;
  return `Level ${rank} · Advanced`;
};

export const LearnView: React.FC<LearnViewProps> = ({ onBackToFeed, selectedSubject = 'all', offerings }) => {
  const courseOptions = useMemo(() => offerings.filter((o) => selectedSubject === 'all' || o.curriculum_subject_entry_id === selectedSubject), [offerings, selectedSubject]);
  const [offeringId, setOfferingId] = useState('');
  const [nodes, setNodes] = useState<LearningNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Adaptive Learn practice state
  const [startingNodeId, setStartingNodeId] = useState<string | null>(null);
  const [practiceMeta, setPracticeMeta] = useState<{ nodeId: string; title: string; moduleTitle?: string | null } | null>(null);
  const [practiceSession, setPracticeSession] = useState<PracticeSessionState | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<PracticeQuestion | null>(null);
  const [selectedPracticeOption, setSelectedPracticeOption] = useState<string>('');
  const [hintText, setHintText] = useState<string | null>(null);
  const [loadingHint, setLoadingHint] = useState(false);
  const [checkingAnswer, setCheckingAnswer] = useState(false);
  const [lastFeedback, setLastFeedback] = useState<PracticeAnswerResult | null>(null);

  useEffect(() => {
    if (!courseOptions.some((o) => o.id === offeringId)) setOfferingId(courseOptions[0]?.id ?? '');
  }, [courseOptions, offeringId]);

  const loadLearnWorkspace = useCallback(async (targetOfferingId: string) => {
    if (!targetOfferingId) {
      setNodes([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const map = await apiClient.get<LearningMap>(`/api/v1/courses/${targetOfferingId}/student/map`);
      setNodes(Array.isArray(map.nodes) ? map.nodes : []);
    } catch {
      setError('Learning content could not be loaded. Please retry.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setPracticeSession(null);
    setPracticeMeta(null);
    setCurrentQuestion(null);
    setLastFeedback(null);
    setHintText(null);
    void loadLearnWorkspace(offeringId);
  }, [offeringId, loadLearnWorkspace]);

  const groupedModules = useMemo(() => {
    const groups: { moduleTitle: string; nodes: LearningNode[] }[] = [];
    const byModule = new Map<string, LearningNode[]>();
    for (const node of nodes) {
      const key = (node.module_title || 'Course Topics').trim();
      if (!byModule.has(key)) {
        const list: LearningNode[] = [];
        byModule.set(key, list);
        groups.push({ moduleTitle: key, nodes: list });
      }
      byModule.get(key)!.push(node);
    }
    for (const g of groups) {
      g.nodes.sort((a, b) => (a.sequence_no ?? 0) - (b.sequence_no ?? 0) || (a.difficulty_rank ?? 0) - (b.difficulty_rank ?? 0));
    }
    return groups;
  }, [nodes]);

  const startNodePractice = async (node: LearningNode) => {
    setError('');
    setStartingNodeId(node.id);
    setHintText(null);
    setSelectedPracticeOption('');
    setLastFeedback(null);
    try {
      const res = await apiClient.post<PracticeSessionStartResponse>(
        `/api/v1/learning-nodes/${node.id}/practice/start`,
        {}
      );
      setPracticeMeta({ nodeId: res.node_id, title: res.node_title, moduleTitle: res.module_title });
      setPracticeSession(res.session);
      setCurrentQuestion(res.current_question ?? null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not start topic practice. Please try again.';
      setError(msg);
    } finally {
      setStartingNodeId(null);
    }
  };

  const requestPracticeHint = async () => {
    if (!practiceSession || loadingHint) return;
    setLoadingHint(true);
    try {
      const res = await apiClient.post<{ hint: string; hints_used: number }>(
        `/api/v1/practice-sessions/${practiceSession.id}/hint`,
        {}
      );
      setHintText(res.hint);
      setPracticeSession((prev) => (prev ? { ...prev, hints_used: res.hints_used } : prev));
    } catch {
      setError('Hint could not be loaded right now.');
    } finally {
      setLoadingHint(false);
    }
  };

  const submitPracticeAnswer = async () => {
    if (!practiceSession || !currentQuestion || !selectedPracticeOption || checkingAnswer) return;
    setCheckingAnswer(true);
    setError('');
    try {
      const res = await apiClient.post<PracticeAnswerResult>(
        `/api/v1/practice-sessions/${practiceSession.id}/answer`,
        {
          activity_version_id: currentQuestion.activity_version_id,
          selected_option_id: selectedPracticeOption,
        }
      );
      setLastFeedback(res);
      setPracticeSession(res.session);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not check answer. Please retry.';
      setError(msg);
    } finally {
      setCheckingAnswer(false);
    }
  };

  const advancePracticeQuestion = () => {
    if (!lastFeedback) return;
    setCurrentQuestion(lastFeedback.next_question ?? null);
    setLastFeedback(null);
    setSelectedPracticeOption('');
    setHintText(null);
  };

  const exitPracticeSession = async () => {
    setPracticeSession(null);
    setPracticeMeta(null);
    setCurrentQuestion(null);
    setLastFeedback(null);
    setSelectedPracticeOption('');
    setHintText(null);
    await loadLearnWorkspace(offeringId);
  };

  const selectedCourse = courseOptions.find((o) => o.id === offeringId);

  // =========================================================================
  // ADAPTIVE PRACTICE SESSION PLAYER
  // =========================================================================
  if (practiceSession && practiceMeta) {
    const progressPct = practiceSession.target_correct_count > 0
      ? Math.min(100, Math.round((practiceSession.correct_count / practiceSession.target_correct_count) * 100))
      : 0;
    const isCompleted = practiceSession.status === 'completed' || Boolean(lastFeedback?.node_completed);
    const activeDifficulty = (currentQuestion?.difficulty || practiceSession.current_difficulty || 'easy').toLowerCase();

    return (
      <div className="space-y-5">
        <div className="rounded-2xl border border-[#DCE7EE] bg-white p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <button
                onClick={() => void exitPracticeSession()}
                className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1 mb-2 cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back to Roadmap
              </button>
              {practiceMeta.moduleTitle && (
                <p className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
                  {practiceMeta.moduleTitle}
                </p>
              )}
              <h2 className="text-lg sm:text-xl font-bold text-[#111111] mt-0.5">{practiceMeta.title}</h2>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {currentQuestion?.is_remediation && (
                <span className="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
                  <RotateCcw className="w-3 h-3" /> Easier Follow-up
                </span>
              )}
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold capitalize ${
                  DIFFICULTY_STYLES[activeDifficulty] ?? DIFFICULTY_STYLES.easy
                }`}
              >
                {activeDifficulty}
              </span>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-slate-600 font-medium">
              <span>Concept Mastery Progress</span>
              <span>{practiceSession.correct_count} / {practiceSession.target_correct_count} correct</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-[#0A8FF5] transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-1 text-[11px] font-semibold">
            <span className="rounded-lg bg-emerald-50 text-emerald-700 px-2.5 py-1">
              Correct: {practiceSession.correct_count}
            </span>
            <span className="rounded-lg bg-slate-100 text-slate-700 px-2.5 py-1">
              Mistakes: {practiceSession.mistake_count}
            </span>
            <span className="rounded-lg bg-amber-50 text-amber-800 px-2.5 py-1">
              Hints used: {practiceSession.hints_used}
            </span>
            {practiceSession.needs_easier_questions && (
              <span className="rounded-lg bg-sky-50 text-sky-700 px-2.5 py-1">
                Easier questions: {practiceSession.easier_followups_triggered}
              </span>
            )}
            {practiceSession.improving && (
              <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 text-emerald-700 px-2.5 py-1">
                <TrendingUp className="w-3 h-3" /> Improving after feedback ({practiceSession.recovered_after_mistake_count})
              </span>
            )}
            {practiceSession.repeated_mistakes && !practiceSession.improving && (
              <span className="rounded-lg bg-rose-50 text-rose-700 px-2.5 py-1">
                Needs step-by-step practice
              </span>
            )}
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {error}
          </div>
        )}

        {isCompleted ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 sm:p-8 text-center space-y-3">
            <CheckCircle2 className="w-10 h-10 text-emerald-600 mx-auto" />
            <h3 className="text-lg font-bold text-emerald-950">Topic Mastered!</h3>
            <p className="text-sm text-emerald-800 max-w-md mx-auto">
              You answered {practiceSession.correct_count} questions correctly
              {practiceSession.recovered_after_mistake_count > 0
                ? `, recovered ${practiceSession.recovered_after_mistake_count} time(s) after explanations,`
                : ''}
              {' '}and unlocked the next topic on your roadmap.
            </p>
            <div className="pt-2">
              <button
                onClick={() => void exitPracticeSession()}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 cursor-pointer"
              >
                Back to Roadmap <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        ) : currentQuestion ? (
          <div className="rounded-2xl border border-[#DCE7EE] bg-white p-5 sm:p-6 space-y-5">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-slate-400">
                Question #{practiceSession.questions_answered + (lastFeedback ? 0 : 1)}
              </p>
              <h3 className="text-base sm:text-lg font-bold text-[#111111] leading-snug">
                {currentQuestion.question}
              </h3>
            </div>

            {hintText && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs sm:text-sm text-amber-900 flex items-start gap-2.5">
                <Lightbulb className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Hint: </span>
                  {hintText}
                </div>
              </div>
            )}

            <div className="space-y-2.5">
              {currentQuestion.options.map((opt) => {
                const isSelected = selectedPracticeOption === opt.option_id;
                let style = 'border-[#DCE7EE] hover:bg-[#F4F7F9] text-[#111111]';
                if (lastFeedback) {
                  if (lastFeedback.correct_option_id === opt.option_id) {
                    style = 'border-emerald-500 bg-emerald-50 text-emerald-950 font-semibold';
                  } else if (isSelected && !lastFeedback.is_correct) {
                    style = 'border-rose-400 bg-rose-50 text-rose-900';
                  } else {
                    style = 'border-[#DCE7EE] opacity-65';
                  }
                } else if (isSelected) {
                  style = 'border-[#0A8FF5] bg-[#EAF5FF] text-[#0A8FF5] font-semibold';
                }

                return (
                  <button
                    key={opt.option_id}
                    type="button"
                    disabled={Boolean(lastFeedback) || checkingAnswer}
                    onClick={() => setSelectedPracticeOption(opt.option_id)}
                    className={`w-full text-left p-3.5 rounded-xl border text-sm transition flex items-center justify-between gap-3 cursor-pointer ${style}`}
                  >
                    <span>{opt.text}</span>
                    {lastFeedback && lastFeedback.correct_option_id === opt.option_id && (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>

            {lastFeedback ? (
              <div
                className={`rounded-xl border p-4 space-y-3 ${
                  lastFeedback.is_correct
                    ? 'border-emerald-200 bg-emerald-50/70'
                    : 'border-amber-200 bg-amber-50/70'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  {lastFeedback.is_correct ? (
                    <Sparkles className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <HelpCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  )}
                  <div className="space-y-1 text-sm">
                    <p className={`font-bold ${lastFeedback.is_correct ? 'text-emerald-900' : 'text-amber-900'}`}>
                      {lastFeedback.feedback_summary}
                    </p>
                    <p className="text-slate-700 leading-relaxed">
                      <span className="font-semibold">Short explanation:</span> {lastFeedback.explanation}
                    </p>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={advancePracticeQuestion}
                    className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 cursor-pointer"
                  >
                    {lastFeedback.next_question?.is_remediation
                      ? 'Try Easier Follow-up'
                      : 'Next Question'}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => void requestPracticeHint()}
                  disabled={loadingHint || Boolean(hintText)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50 cursor-pointer"
                >
                  <Lightbulb className="w-3.5 h-3.5" />
                  {loadingHint ? 'Loading hint...' : hintText ? 'Hint shown' : 'Show Hint'}
                </button>
                <button
                  type="button"
                  onClick={() => void submitPracticeAnswer()}
                  disabled={!selectedPracticeOption || checkingAnswer}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#0A8FF5] px-5 py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-[#097ED8] disabled:opacity-50 cursor-pointer"
                >
                  {checkingAnswer ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  Check Answer
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-2xl border bg-white p-8 text-center text-sm text-slate-600">
            No practice questions are available for this topic yet.
          </div>
        )}
      </div>
    );
  }

  return <div className="space-y-5">
    {selectedSubject !== 'all' && selectedCourse && <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">Learning workspace · {selectedCourse.subject_name || selectedCourse.official_subject_code}</div>}
    {courseOptions.length > 1 && <label className="block text-sm font-semibold text-slate-700">Course offering<select className="mt-2 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5" value={offeringId} onChange={(e) => setOfferingId(e.target.value)}>{courseOptions.map((o) => <option key={o.id} value={o.id}>{[o.official_subject_code, o.subject_name, o.section_code].filter(Boolean).join(' · ')}</option>)}</select></label>}
    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
    {loading ? <div className="rounded-2xl border bg-white p-10 text-center text-slate-500"><Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin"/>Loading published learning content…</div> : !offeringId ? <div className="rounded-2xl border bg-white p-10 text-center"><BookOpen className="mx-auto mb-3 h-7 w-7 text-slate-400"/><h2 className="font-bold">No enrolled course offerings found</h2><p className="mt-2 text-sm text-slate-500">Learning content appears here after you are enrolled in a course.</p></div> : <>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-blue-600" />
            <div>
              <h2 className="font-bold">Learning map</h2>
              <p className="text-xs text-slate-500">Organized by module, topic, and difficulty — learn through practice and immediate feedback.</p>
            </div>
          </div>
        </div>
        {groupedModules.length ? (
          <div className="space-y-5">
            {groupedModules.map((group) => (
              <div key={group.moduleTitle} className="space-y-2.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 px-1">
                  {group.moduleTitle}
                </h3>
                <ol className="space-y-2.5">
                  {group.nodes.map((node) => {
                    const completed = node.progress_status === 'completed';
                    const unlocked = Boolean(node.is_unlocked);
                    const stats = node.practice_summary;
                    return (
                      <li
                        key={node.id}
                        className={`rounded-xl border p-4 transition ${
                          completed
                            ? 'border-emerald-200 bg-emerald-50/40'
                            : unlocked
                              ? 'border-slate-200 bg-white hover:border-blue-200'
                              : 'border-slate-200 bg-slate-50/70 opacity-80'
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex items-start gap-3 min-w-0 flex-1">
                            <span className="mt-0.5 shrink-0">
                              {completed ? (
                                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                              ) : unlocked ? (
                                <CheckCircle className="h-5 w-5 text-blue-600" />
                              ) : (
                                <Lock className="h-5 w-5 text-slate-400" />
                              )}
                            </span>
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <h4 className="font-semibold text-slate-900">{node.title}</h4>
                                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                                  {formatRankLabel(node.difficulty_rank)}
                                </span>
                              </div>
                              {node.description && (
                                <p className="mt-1 text-sm leading-relaxed text-slate-600">{node.description}</p>
                              )}
                              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                <span>
                                  {completed
                                    ? 'Completed'
                                    : unlocked
                                      ? 'Available'
                                      : 'Complete previous topic to unlock'}
                                </span>
                                <span>· {node.concept_ids.length} mapped concepts</span>
                                {(node.question_count ?? 0) > 0 && (
                                  <span>· {node.question_count} questions</span>
                                )}
                                {stats && (
                                  <>
                                    <span className="text-emerald-700 font-medium">
                                      · {stats.correct_count}/{stats.target_correct_count} mastered
                                    </span>
                                    {stats.hints_used > 0 && <span>· {stats.hints_used} hints</span>}
                                    {stats.improving && (
                                      <span className="text-emerald-700 font-medium">· Improving</span>
                                    )}
                                  </>
                                )}
                              </div>
                            </div>
                          </div>

                          <button
                            type="button"
                            disabled={!unlocked || startingNodeId === node.id}
                            onClick={() => void startNodePractice(node)}
                            className={`inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-semibold shrink-0 cursor-pointer disabled:cursor-not-allowed ${
                              unlocked
                                ? completed
                                  ? 'border border-emerald-300 bg-white text-emerald-800 hover:bg-emerald-50'
                                  : 'bg-[#0A8FF5] text-white hover:bg-[#097ED8]'
                                : 'bg-slate-200 text-slate-500'
                            }`}
                          >
                            {startingNodeId === node.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : unlocked ? (
                              <Play className="w-3.5 h-3.5" />
                            ) : (
                              <Lock className="w-3.5 h-3.5" />
                            )}
                            {completed
                              ? 'Practice Again'
                              : stats && stats.questions_answered > 0
                                ? 'Continue'
                                : unlocked
                                  ? 'Start Practice'
                                  : 'Locked'}
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No published learning nodes are available for this course yet.</p>
        )}
      </section>
    </>}
    <button onClick={onBackToFeed} className="btn-outline inline-flex items-center gap-2 px-4 py-2 text-sm"><ArrowLeft className="h-4 w-4"/>Back to Doubts Feed</button>
  </div>;
};
