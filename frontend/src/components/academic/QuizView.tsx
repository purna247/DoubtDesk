import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Award,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Copy,
  Eye,
  FileText,
  HelpCircle,
  Loader2,
  Plus,
  Send,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useAuth } from '../../contexts/AuthContext';
import type { CourseOffering } from '../../types/academics';
import type { Question } from '../../types/questions';
import type {
  Assessment,
  AssessmentItem,
  AttemptSummary,
  QuizAiGenerateResponse,
  StartAttemptResponse,
} from '../../types/assessments';

interface QuizViewProps {
  onEarnPoints?: (pts: number) => void;
  onShowToast?: (msg: string) => void;
  selectedSubject?: string;
  offerings?: CourseOffering[];
}

interface QuizWithCourse {
  assessment: Assessment;
  offering?: CourseOffering;
}

interface DraftOption {
  id: string;
  text: string;
  isCorrect: boolean;
}

interface DraftQuestion {
  id: string;
  statement: string;
  options: DraftOption[];
  explanation: string;
  marks: number;
  sourceChunkIds?: string[];
  conceptIds?: string[];
}

interface McqPayloadOption {
  option_id: string;
  text: string;
}

interface StudentIntervention {
  intervention_id: string;
  title: string;
  description?: string | null;
  current_phase: string;
  phase_a_unlocked: boolean;
  phase_a_completed: boolean;
  phase_a_assessment_id?: string | null;
  phase_a_score?: number | null;
  phase_b_unlocked: boolean;
  phase_b_completed: boolean;
  phase_b_primer_content?: string | null;
  phase_b_practice_assessment_id?: string | null;
  phase_b_items_completed: number;
  phase_b_rule_description: string;
  phase_c_unlocked: boolean;
  phase_c_completed: boolean;
  phase_c_assessment_id?: string | null;
  phase_c_score?: number | null;
  observed_score_change?: number | null;
  outcome_status?: string | null;
  offering?: CourseOffering;
}

const formatOfferingLabel = (offering?: CourseOffering): string => {
  if (!offering) return 'Assigned Course';
  return [offering.official_subject_code, offering.subject_name, offering.section_code && `Sec ${offering.section_code}`]
    .filter(Boolean)
    .join(' · ');
};

const createEmptyQuestion = (): DraftQuestion => {
  const uid = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  return {
    id: `q-${uid}`,
    statement: '',
    options: [
      { id: `opt-${uid}-1`, text: '', isCorrect: true },
      { id: `opt-${uid}-2`, text: '', isCorrect: false },
      { id: `opt-${uid}-3`, text: '', isCorrect: false },
      { id: `opt-${uid}-4`, text: '', isCorrect: false },
    ],
    explanation: '',
    marks: 2,
  };
};

const getMcqQuestionText = (item: AssessmentItem): string => {
  const payload = item.student_payload_json as Record<string, unknown> | undefined | null;
  if (payload && typeof payload.question === 'string' && payload.question.trim()) {
    return payload.question;
  }
  return item.question_prompt || item.title || `Question ${item.sequence_no}`;
};

const getMcqOptions = (item: AssessmentItem): McqPayloadOption[] => {
  const payload = item.student_payload_json as Record<string, unknown> | undefined | null;
  const raw = payload?.options;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((o): o is Record<string, unknown> => Boolean(o && typeof o === 'object'))
    .map((o, idx) => ({
      option_id: String(o.option_id ?? `opt_${idx + 1}`),
      text: String(o.text ?? ''),
    }));
};

export const QuizView: React.FC<QuizViewProps> = ({
  onEarnPoints,
  onShowToast,
  selectedSubject = 'all',
  offerings = [],
}) => {
  const { role } = useAuth();
  const isTeacher = role === 'TEACHER' || role === 'ADMIN' || role === 'SUPER_ADMIN';

  const [quizzes, setQuizzes] = useState<QuizWithCourse[]>([]);
  const [interventions, setInterventions] = useState<StudentIntervention[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<'all' | 'published' | 'draft'>('all');

  // Active sub-mode within the existing center frame: 'list' | 'manual_form' | 'preview' | 'take_quiz'
  const [mode, setMode] = useState<'list' | 'manual_form' | 'question_bank' | 'preview' | 'take_quiz'>('list');

  // AI Generator modal state
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [aiOfferingId, setAiOfferingId] = useState('');
  const [aiTopic, setAiTopic] = useState('');
  const [aiQuestionCount, setAiQuestionCount] = useState(5);
  const [aiDifficulty, setAiDifficulty] = useState('Intermediate');
  const [isGenerating, setIsGenerating] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Manual (Google-Forms-style) Quiz Builder state
  const [builderOfferingId, setBuilderOfferingId] = useState('');
  const [manualTitle, setManualTitle] = useState('');
  const [manualDescription, setManualDescription] = useState('');
  const [manualTimeLimit, setManualTimeLimit] = useState(15);
  const [manualQuestions, setManualQuestions] = useState<DraftQuestion[]>([createEmptyQuestion()]);
  const [aiSources, setAiSources] = useState<QuizAiGenerateResponse['sources']>([]);
  const [savingQuiz, setSavingQuiz] = useState(false);
  const [bankQuestions, setBankQuestions] = useState<Question[]>([]);
  const [bankSelectedIds, setBankSelectedIds] = useState<string[]>([]);
  const [bankTitle, setBankTitle] = useState('');
  const [bankDuration, setBankDuration] = useState(30);
  const [bankLoading, setBankLoading] = useState(false);

  // Teacher Preview state
  const [previewTarget, setPreviewTarget] = useState<QuizWithCourse | null>(null);

  // Student CBT Attempt state
  const [activeQuizMeta, setActiveQuizMeta] = useState<QuizWithCourse | null>(null);
  const [activeAttempt, setActiveAttempt] = useState<StartAttemptResponse | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>({});
  const [submittingAttempt, setSubmittingAttempt] = useState(false);
  const [attemptSummary, setAttemptSummary] = useState<AttemptSummary | null>(null);

  // Filter offerings based on left-sidebar subject selection
  const scopedOfferings = useMemo(
    () =>
      offerings.filter(
        (o) => selectedSubject === 'all' || o.curriculum_subject_entry_id === selectedSubject
      ),
    [offerings, selectedSubject]
  );

  // Keep default offering selected for builders
  useEffect(() => {
    const firstId = scopedOfferings[0]?.id ?? offerings[0]?.id ?? '';
    if (!offerings.some((o) => o.id === aiOfferingId)) setAiOfferingId(firstId);
    if (!offerings.some((o) => o.id === builderOfferingId)) setBuilderOfferingId(firstId);
  }, [offerings, scopedOfferings, aiOfferingId, builderOfferingId]);

  const loadQuizzes = useCallback(async () => {
    if (!offerings.length) {
      setQuizzes([]);
      setInterventions([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const results = await Promise.all(
        offerings.map(async (offering) => {
          const endpoint = isTeacher
            ? `/api/v1/courses/${offering.id}/assessments`
            : `/api/v1/courses/${offering.id}/student/assessments`;
          const rows = await apiClient.get<Assessment[]>(endpoint).catch(() => []);
          return (Array.isArray(rows) ? rows : []).map((assessment) => ({
            assessment,
            offering,
          }));
        })
      );
      setQuizzes(results.flat());
      if (!isTeacher) {
        const interventionRows = await Promise.all(
          offerings.map(async (offering) => {
            const rows = await apiClient
              .get<StudentIntervention[]>(`/api/v1/courses/${offering.id}/interventions/student`)
              .catch(() => []);
            return (Array.isArray(rows) ? rows : []).map((item) => ({ ...item, offering }));
          })
        );
        setInterventions(interventionRows.flat());
      } else {
        setInterventions([]);
      }
    } finally {
      setLoading(false);
    }
  }, [offerings, isTeacher]);

  useEffect(() => {
    void loadQuizzes();
  }, [loadQuizzes]);

  const visibleQuizzes = useMemo(() => {
    return quizzes.filter(({ assessment, offering }) => {
      if (
        selectedSubject !== 'all' &&
        offering?.curriculum_subject_entry_id !== selectedSubject
      ) {
        return false;
      }
      if (isTeacher && statusFilter !== 'all' && assessment.status !== statusFilter) {
        return false;
      }
      if (!isTeacher && assessment.status !== 'published') {
        return false;
      }
      return true;
    });
  }, [quizzes, selectedSubject, isTeacher, statusFilter]);

  // -------------------------------------------------------------------------
  // Teacher Actions: AI Generation, Manual Builder, Publish, Unpublish, Delete
  // -------------------------------------------------------------------------
  const openManualBuilder = (prefill?: {
    offeringId?: string;
    title?: string;
    description?: string;
    questions?: DraftQuestion[];
  }) => {
    setBuilderOfferingId(prefill?.offeringId || scopedOfferings[0]?.id || offerings[0]?.id || '');
    setManualTitle(prefill?.title ?? '');
    setManualDescription(prefill?.description ?? '');
    setManualTimeLimit(Math.max(5, (prefill?.questions?.length ?? 3) * 3));
    setManualQuestions(prefill?.questions?.length ? prefill.questions : [createEmptyQuestion()]);
    if (!prefill?.questions?.length) setAiSources([]);
    setMode('manual_form');
  };

  const openQuestionBankBuilder = async () => {
    if (!builderOfferingId) return;
    setBankLoading(true);
    setBankSelectedIds([]);
    try {
      const rows = await apiClient.get<Question[]>(`/api/v1/courses/${builderOfferingId}/questions`);
      setBankQuestions((Array.isArray(rows) ? rows : []).filter((question) => question.latest_version?.approval_status === 'approved'));
      setBankTitle('Practice paper from Question Bank');
      setMode('question_bank');
    } catch {
      onShowToast?.('Could not load approved questions for this course.');
    } finally { setBankLoading(false); }
  };

  const saveQuestionBankQuiz = async (publish: boolean) => {
    const selected = bankQuestions.filter((question) => bankSelectedIds.includes(question.id) && question.latest_version);
    if (!selected.length || !builderOfferingId || !bankTitle.trim()) return;
    setSavingQuiz(true);
    try {
      const assessment = await apiClient.post<{ id: string }>(`/api/v1/courses/${builderOfferingId}/assessments`, {
        assessment_type: 'node_practice', title: bankTitle.trim(),
        description: 'Practice paper assembled from approved, source-linked Question Bank records.',
        version: {
          duration_seconds: Number(bankDuration) * 60,
          items: selected.map((question, index) => {
            const version = question.latest_version!;
            const allocations = new Map<string, number>();
            for (const part of version.parts) for (const allocation of part.concept_allocations ?? []) {
              allocations.set(allocation.concept_id, (allocations.get(allocation.concept_id) ?? 0) + allocation.allocated_marks);
            }
            return {
              question_version_id: version.id,
              sequence_no: index + 1,
              marks_available: version.marks_total,
              concept_allocations: Array.from(allocations, ([concept_id, marks_available]) => ({ concept_id, marks_available })),
            };
          }),
        },
      });
      if (publish) await apiClient.post(`/api/v1/assessments/${assessment.id}/publish`, {});
      await loadQuizzes();
      setMode('list'); setBankSelectedIds([]);
      onShowToast?.(publish
        ? 'Practice paper published with the original Question Bank records and concept mappings.'
        : 'Question Bank practice paper saved as a draft.');
    } catch (err: unknown) {
      onShowToast?.(err instanceof Error ? err.message : 'Could not publish this Question Bank paper.');
    } finally { setSavingQuiz(false); }
  };

  const handleGenerateWithAi = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!aiOfferingId) {
      onShowToast?.('No assigned course offering available.');
      return;
    }
    if (!aiTopic.trim()) {
      onShowToast?.('Please enter a topic for AI quiz generation.');
      return;
    }
    setIsGenerating(true);
    setAiError(null);
    try {
      const generated = await apiClient.post<QuizAiGenerateResponse>(
        `/api/v1/courses/${aiOfferingId}/quizzes/ai-generate`,
        {
          topic: aiTopic.trim(),
          question_count: aiQuestionCount,
          difficulty: aiDifficulty,
        }
      );
      const draftQuestions: DraftQuestion[] = generated.questions.map((q, qIdx) => {
        const uid = `${Date.now()}-${qIdx}`;
        return {
          id: `ai-q-${uid}`,
          statement: q.statement,
          options: q.options.map((text, oIdx) => ({
            id: `ai-opt-${uid}-${oIdx}`,
            text,
            isCorrect: oIdx === q.correct_index,
          })),
          explanation: q.explanation || '',
          marks: q.marks || 2,
          sourceChunkIds: q.source_chunk_ids ?? [],
          conceptIds: q.concept_ids ?? [],
        };
      });
      setIsAiModalOpen(false);
      setAiTopic('');
      setAiSources(generated.sources ?? []);
      openManualBuilder({
        offeringId: aiOfferingId,
        title: generated.title,
        description: generated.description,
        questions: draftQuestions,
      });
      onShowToast?.('AI generated quiz questions. Review or edit before publishing.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'AI quiz generation failed. Please retry.';
      setAiError(msg);
      onShowToast?.(msg);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveManualQuiz = async (publish: boolean) => {
    if (!builderOfferingId) {
      onShowToast?.('Please select a course offering.');
      return;
    }
    if (!manualTitle.trim()) {
      onShowToast?.('Please enter a Quiz Title.');
      return;
    }
    if (manualQuestions.some((q) => !q.statement.trim())) {
      onShowToast?.('Please fill in the statement for every question.');
      return;
    }
    if (manualQuestions.some((q) => q.options.filter((o) => o.text.trim()).length < 2)) {
      onShowToast?.('Each question needs at least two non-empty options.');
      return;
    }

    setSavingQuiz(true);
    try {
      await apiClient.post(`/api/v1/courses/${builderOfferingId}/quizzes`, {
        title: manualTitle.trim(),
        description: manualDescription.trim() || null,
        time_limit_minutes: Number(manualTimeLimit) || 15,
        publish,
        questions: manualQuestions.map((q) => {
          const validOpts = q.options.filter((o) => o.text.trim());
          const correctIdx = Math.max(
            0,
            validOpts.findIndex((o) => o.isCorrect)
          );
          return {
            statement: q.statement.trim(),
            options: validOpts.map((o) => o.text.trim()),
            correct_index: correctIdx,
            explanation: q.explanation.trim() || null,
            marks: Number(q.marks) > 0 ? Number(q.marks) : 2,
            source_chunk_ids: q.sourceChunkIds ?? [],
            concept_ids: q.conceptIds ?? [],
            origin_type: q.sourceChunkIds?.length ? 'ai_supplementary' : 'teacher_authored',
          };
        }),
      });
      await loadQuizzes();
      setMode('list');
      onShowToast?.(
        publish
          ? `Quiz "${manualTitle.trim()}" published to students!`
          : `Quiz "${manualTitle.trim()}" saved as draft.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not save quiz. Please retry.';
      onShowToast?.(msg);
    } finally {
      setSavingQuiz(false);
    }
  };

  const handleTogglePublish = async (assessment: Assessment) => {
    const isPublished = assessment.status === 'published';
    try {
      await apiClient.post(
        `/api/v1/assessments/${assessment.id}/${isPublished ? 'unpublish' : 'publish'}`,
        {}
      );
      await loadQuizzes();
      onShowToast?.(isPublished ? 'Quiz moved to drafts.' : 'Quiz published to students.');
    } catch {
      onShowToast?.('Could not update quiz status.');
    }
  };

  const handleDeleteQuiz = async (assessmentId: string) => {
    try {
      await apiClient.delete(`/api/v1/assessments/${assessmentId}`);
      await loadQuizzes();
      onShowToast?.('Quiz removed.');
    } catch {
      onShowToast?.('Could not remove quiz.');
    }
  };

  // Manual form question helpers
  const handleDuplicateQuestion = (idx: number) => {
    const src = manualQuestions[idx];
    const uid = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const clone: DraftQuestion = {
      ...src,
      id: `q-${uid}`,
      options: src.options.map((opt, oIdx) => ({ ...opt, id: `opt-${uid}-${oIdx}` })),
    };
    const next = [...manualQuestions];
    next.splice(idx + 1, 0, clone);
    setManualQuestions(next);
  };

  const handleDeleteQuestion = (idx: number) => {
    if (manualQuestions.length <= 1) {
      onShowToast?.('A quiz must have at least one question.');
      return;
    }
    setManualQuestions((prev) => prev.filter((_, i) => i !== idx));
  };

  // -------------------------------------------------------------------------
  // Student CBT Assessment Handlers
  // -------------------------------------------------------------------------
  const handleStartStudentQuiz = async (meta: QuizWithCourse) => {
    try {
      const started = await apiClient.post<StartAttemptResponse>(
        `/api/v1/assessments/${meta.assessment.id}/start`,
        {}
      );
      const restored: Record<string, string> = {};
      for (const item of started.items) {
        const saved = started.saved_responses?.[item.id]?.payload as Record<string, unknown> | undefined;
        if (saved?.answers && typeof saved.answers === 'object') {
          restored[item.id] = JSON.stringify(saved.answers);
        } else if (typeof saved?.selected_option_id === 'string') {
          restored[item.id] = saved.selected_option_id;
        } else if (typeof saved?.text === 'string') {
          restored[item.id] = saved.text;
        } else if (typeof saved?.answer === 'string') {
          restored[item.id] = saved.answer;
        }
      }
      setActiveQuizMeta(meta);
      setActiveAttempt(started);
      setSelectedAnswers(restored);
      setAttemptSummary(null);
      setMode('take_quiz');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not start quiz attempt.';
      onShowToast?.(msg);
    }
  };

  const handleSelectStudentOption = async (itemId: string, optionId: string) => {
    if (!activeAttempt || attemptSummary) return;
    const previousChoice = selectedAnswers[itemId];
    setSelectedAnswers((prev) => ({ ...prev, [itemId]: optionId }));
    try {
      await apiClient.post(`/api/v1/attempts/${activeAttempt.attempt_id}/responses`, {
        item_id: itemId,
        response_payload: { selected_option_id: optionId },
        response_state: 'answered',
      });
    } catch (err: unknown) {
      setSelectedAnswers((prev) => {
        const next = { ...prev };
        if (previousChoice) {
          next[itemId] = previousChoice;
        } else {
          delete next[itemId];
        }
        return next;
      });
      const msg = err instanceof Error ? err.message : 'Could not autosave response. Check your connection.';
      onShowToast?.(msg);
    }
  };

  const handleSaveStudentPayload = async (item: AssessmentItem, value: string) => {
    if (!activeAttempt || attemptSummary) return;
    const previousChoice = selectedAnswers[item.id];
    setSelectedAnswers((prev) => ({ ...prev, [item.id]: value }));
    try {
      let responsePayload: Record<string, unknown> = { text: value };
      if (item.activity_type === 'mcq' && !item.question_parts?.length) {
        responsePayload = { selected_option_id: value };
      } else if (item.activity_type === 'fill_blank') {
        responsePayload = { answer: value };
      } else if (item.question_parts?.length) {
        try {
          const parsed = JSON.parse(value);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            responsePayload = { answers: parsed };
          }
        } catch {
          /* free text */
        }
      }
      await apiClient.post(`/api/v1/attempts/${activeAttempt.attempt_id}/responses`, {
        item_id: item.id,
        response_payload: responsePayload,
        response_state: value.trim() ? 'answered' : 'empty',
      });
    } catch (err: unknown) {
      setSelectedAnswers((prev) => {
        const next = { ...prev };
        if (previousChoice) next[item.id] = previousChoice;
        else delete next[item.id];
        return next;
      });
      const msg = err instanceof Error ? err.message : 'Could not autosave response. Check your connection.';
      onShowToast?.(msg);
    }
  };

  const handleStartAssessmentById = async (
    assessmentId: string,
    title: string,
    assessmentType: Assessment['assessment_type'],
    offering?: CourseOffering
  ) => {
    await handleStartStudentQuiz({
      assessment: {
        id: assessmentId,
        institution_id: offering?.institution_id ?? '',
        course_offering_id: offering?.id ?? '',
        assessment_type: assessmentType,
        title,
        status: 'published',
        created_at: new Date().toISOString(),
      },
      offering,
    });
  };

  const handleSubmitStudentQuiz = async () => {
    if (!activeAttempt) return;
    setSubmittingAttempt(true);
    try {
      const summary = await apiClient.post<AttemptSummary>(
        `/api/v1/attempts/${activeAttempt.attempt_id}/submit`,
        {}
      );
      setAttemptSummary(summary);
      const awarded = summary.marks_awarded ?? 0;
      if (onEarnPoints && awarded > 0) {
        onEarnPoints(Math.round(awarded * 10));
      }
      onShowToast?.(`Quiz submitted! Scored ${awarded} / ${summary.marks_available ?? 0} marks.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Submission failed. Please retry.';
      onShowToast?.(msg);
    } finally {
      setSubmittingAttempt(false);
    }
  };

  // =========================================================================
  // VIEW 1: Student CBT Quiz Taking Mode (Inside existing center column)
  // =========================================================================
  if (mode === 'take_quiz' && activeAttempt && activeQuizMeta) {
    const totalMarks = activeAttempt.items.reduce((sum, it) => sum + it.marks_available, 0);
    const scoreByItem = new Map((attemptSummary?.item_scores || []).map((s) => [s.item_id, s]));

    return (
      <div className="space-y-5">
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-6 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <button
              onClick={() => {
                setMode('list');
                setActiveAttempt(null);
                setAttemptSummary(null);
              }}
              className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1 mb-2 cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Quizzes
            </button>
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
              {formatOfferingLabel(activeQuizMeta.offering)}
            </p>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] mt-0.5">
              {activeQuizMeta.assessment.title}
            </h2>
            {activeQuizMeta.assessment.description && (
              <p className="text-xs text-[#4D5963] mt-1">{activeQuizMeta.assessment.description}</p>
            )}
          </div>
          <div className="text-right shrink-0">
            <span className="text-[11px] font-semibold text-[#71808C]">Total Marks</span>
            <div className="text-lg font-black text-[#111111]">{totalMarks} pts</div>
          </div>
        </div>

        {attemptSummary && (
          <div className="p-6 rounded-[16px] bg-emerald-50 border border-emerald-200 text-center space-y-1.5">
            <CheckCircle2 className="w-9 h-9 text-emerald-600 mx-auto" />
            <h3 className="text-base font-bold text-emerald-900">Quiz Submitted</h3>
            <p className="text-sm font-semibold text-emerald-800">
              Score: <span className="font-black">{attemptSummary.marks_awarded ?? 0} / {attemptSummary.marks_available ?? totalMarks}</span> (
              {Math.round((attemptSummary.score_fraction ?? 0) * 100)}%)
            </p>
          </div>
        )}

        <div className="space-y-4">
          {activeAttempt.items.map((item, idx) => {
            const options = getMcqOptions(item);
            const chosen = selectedAnswers[item.id];
            const itemResult = scoreByItem.get(item.id);
            const correctId = itemResult?.correct_option_id;
            const isCorrect = Boolean(attemptSummary && itemResult?.result_status === 'correct');

            return (
              <div
                key={item.id}
                className={`p-5 sm:p-6 rounded-[16px] border bg-white space-y-4 ${
                  attemptSummary
                    ? isCorrect
                      ? 'border-emerald-300'
                      : 'border-rose-300'
                    : 'border-[#DCE7EE]'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="font-bold text-sm text-[#111111]">
                    {idx + 1}. {getMcqQuestionText(item)}
                  </span>
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#EDF4F8] text-[#4D5963] shrink-0">
                    {item.marks_available} pts
                  </span>
                </div>

                {item.question_parts?.length ? (
                  <div className="space-y-4">
                    {item.question_parts.map((part) => {
                      let partAnswers: Record<string, string> = {};
                      try {
                        partAnswers = JSON.parse(chosen || '{}') as Record<string, string>;
                      } catch {
                        partAnswers = {};
                      }
                      const savePartChoice = (optionId: string) => {
                        const encoded = JSON.stringify({ ...partAnswers, [part.id]: optionId });
                        void handleSaveStudentPayload(item, encoded);
                      };
                      return (
                        <div key={part.id} className="space-y-2">
                          <p className="text-xs font-semibold text-[#111111]">
                            {part.part_prompt} <span className="text-[#71808C]">({part.marks_available} pts)</span>
                          </p>
                          {part.answer_type === 'mcq' && part.options.length ? (
                            <div className="space-y-2">
                              {part.options.map((opt) => (
                                <button
                                  key={opt.id}
                                  type="button"
                                  disabled={Boolean(attemptSummary)}
                                  onClick={() => savePartChoice(opt.id)}
                                  className={`w-full text-left p-3.5 rounded-xl border text-xs flex items-center justify-between transition cursor-pointer ${
                                    partAnswers[part.id] === opt.id
                                      ? 'border-[#0A8FF5] bg-[#EAF5FF] text-[#0A8FF5] font-semibold'
                                      : 'border-[#DCE7EE] hover:bg-[#F4F7F9]'
                                  }`}
                                >
                                  <span>{opt.option_key}. {opt.display_text}</span>
                                </button>
                              ))}
                            </div>
                          ) : (
                            <textarea
                              rows={3}
                              disabled={Boolean(attemptSummary)}
                              value={chosen ?? ''}
                              onChange={(e) => setSelectedAnswers((prev) => ({ ...prev, [item.id]: e.target.value }))}
                              onBlur={(e) => void handleSaveStudentPayload(item, e.target.value)}
                              placeholder="Write your response..."
                              className="w-full p-3 rounded-xl border border-[#DCE7EE] text-xs"
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : options.length > 0 ? (
                  <div className="space-y-2">
                    {options.map((opt) => {
                      const isSelected = chosen === opt.option_id;
                      let optStyle = 'border-[#DCE7EE] hover:bg-[#F4F7F9]';
                      if (attemptSummary) {
                        if (correctId && opt.option_id === correctId) {
                          optStyle = 'border-emerald-500 bg-emerald-50 text-emerald-900 font-semibold';
                        } else if (isSelected && opt.option_id !== correctId) {
                          optStyle = 'border-rose-400 bg-rose-50 text-rose-900';
                        }
                      } else if (isSelected) {
                        optStyle = 'border-[#0A8FF5] bg-[#EAF5FF] text-[#0A8FF5] font-semibold';
                      }

                      return (
                        <button
                          key={opt.option_id}
                          type="button"
                          disabled={Boolean(attemptSummary)}
                          onClick={() => void handleSelectStudentOption(item.id, opt.option_id)}
                          className={`w-full text-left p-3.5 rounded-xl border text-xs flex items-center justify-between transition cursor-pointer ${optStyle}`}
                        >
                          <span>{opt.text}</span>
                          {attemptSummary && correctId && opt.option_id === correctId && (
                            <span className="text-[11px] font-bold text-emerald-700 inline-flex items-center gap-1 shrink-0">
                              <Check className="w-3.5 h-3.5" /> Correct Answer
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <textarea
                    rows={3}
                    disabled={Boolean(attemptSummary)}
                    value={chosen ?? ''}
                    onChange={(e) => setSelectedAnswers((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    onBlur={(e) => void handleSaveStudentPayload(item, e.target.value)}
                    placeholder="Write your response..."
                    className="w-full p-3 rounded-xl border border-[#DCE7EE] text-xs"
                  />
                )}

                {attemptSummary && itemResult?.explanation && (
                  <div className="p-3.5 rounded-xl bg-[#F8FAFC] border border-[#DCE7EE] text-xs text-[#4D5963] leading-relaxed">
                    <span className="font-bold text-[#111111] block mb-0.5">Explanation:</span>
                    {itemResult.explanation}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {!attemptSummary && (
          <div className="flex justify-end">
            <button
              onClick={() => void handleSubmitStudentQuiz()}
              disabled={submittingAttempt || Object.keys(selectedAnswers).length === 0}
              className="btn-primary text-xs px-6 py-2.5 disabled:opacity-50"
            >
              {submittingAttempt
                ? 'Submitting...'
                : `Submit Quiz (${Object.keys(selectedAnswers).length} / ${activeAttempt.items.length} answered)`}
            </button>
          </div>
        )}
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: Teacher Read-Only Preview Mode (Inside existing center column)
  // =========================================================================
  if (mode === 'preview' && previewTarget) {
    const items = previewTarget.assessment.latest_version?.items || [];
    return (
      <div className="space-y-5">
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-6 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <button
              onClick={() => {
                setPreviewTarget(null);
                setMode('list');
              }}
              className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1 mb-2 cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Quizzes
            </button>
            <p className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
              Faculty Preview · {formatOfferingLabel(previewTarget.offering)}
            </p>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111] mt-0.5">
              {previewTarget.assessment.title}
            </h2>
            {previewTarget.assessment.description && (
              <p className="text-xs text-[#4D5963] mt-1">{previewTarget.assessment.description}</p>
            )}
          </div>
          <span
            className={`text-[11px] font-bold px-2.5 py-1 rounded-full shrink-0 ${
              previewTarget.assessment.status === 'published'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : 'bg-amber-50 text-amber-700 border border-amber-200'
            }`}
          >
            {previewTarget.assessment.status === 'published' ? 'Published' : 'Draft'}
          </span>
        </div>

        <div className="space-y-4">
          {items.map((item, idx) => {
            const options = getMcqOptions(item);
            const answerKey = item.answer_key_json as Record<string, unknown> | undefined | null;
            const correctId = answerKey?.correct_option_id ? String(answerKey.correct_option_id) : '';
            const explanation = answerKey?.explanation ? String(answerKey.explanation) : '';

            return (
              <div key={item.id} className="p-5 sm:p-6 rounded-[16px] border border-[#DCE7EE] bg-white space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <span className="font-bold text-sm text-[#111111]">
                    {idx + 1}. {getMcqQuestionText(item)}
                  </span>
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-[#EDF4F8] text-[#4D5963] shrink-0">
                    {item.marks_available} pts
                  </span>
                </div>

                <div className="space-y-2">
                  {options.map((opt) => {
                    const isCorrect = opt.option_id === correctId;
                    return (
                      <div
                        key={opt.option_id}
                        className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
                          isCorrect
                            ? 'border-emerald-400 bg-emerald-50 text-emerald-900 font-semibold'
                            : 'border-[#DCE7EE] bg-white text-[#4D5963]'
                        }`}
                      >
                        <span>{opt.text}</span>
                        {isCorrect && (
                          <span className="text-[11px] font-bold text-emerald-700 inline-flex items-center gap-1">
                            <Check className="w-3.5 h-3.5" /> Answer Key
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {explanation && (
                  <div className="p-3 rounded-xl bg-[#F8FAFC] border border-[#DCE7EE] text-xs text-[#4D5963]">
                    <span className="font-bold text-[#111111]">Solution Note: </span>
                    {explanation}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 3: Teacher Manual Google-Forms-Style Quiz Builder (Inside same frame)
  // =========================================================================
  if (isTeacher && mode === 'question_bank') {
    const selectedBankQuestions = bankQuestions.filter((question) => bankSelectedIds.includes(question.id));
    return <div className="space-y-5 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><button onClick={() => setMode('list')} className="text-xs font-bold text-[#0A8FF5]">← Back to Quizzes</button><div className="flex gap-2"><button onClick={() => void saveQuestionBankQuiz(false)} disabled={savingQuiz || !selectedBankQuestions.length || !bankTitle.trim()} className="btn-outline text-xs px-4 py-2 disabled:opacity-50">Save Draft</button><button onClick={() => void saveQuestionBankQuiz(true)} disabled={savingQuiz || !selectedBankQuestions.length || !bankTitle.trim()} className="btn-primary text-xs px-4 py-2 disabled:opacity-50">{savingQuiz ? 'Saving…' : 'Publish Practice Paper'}</button></div></div>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
        <h2 className="text-lg font-bold">Build from approved Question Bank records</h2>
        <input value={bankTitle} onChange={(event) => setBankTitle(event.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" aria-label="Practice paper title" />
        <label className="block text-xs font-semibold text-slate-600">Duration in minutes<input type="number" min="1" max="300" value={bankDuration} onChange={(event) => setBankDuration(Number(event.target.value))} className="ml-2 w-24 rounded-lg border border-slate-200 px-2 py-1.5" /></label>
        {bankQuestions.length ? <div className="space-y-2">{bankQuestions.map((question) => { const version = question.latest_version; if (!version) return null; return <label key={question.id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3"><input type="checkbox" checked={bankSelectedIds.includes(question.id)} onChange={(event) => setBankSelectedIds((ids) => event.target.checked ? [...ids, question.id] : ids.filter((id) => id !== question.id))} className="mt-1"/><span className="min-w-0"><span className="block text-sm font-semibold text-slate-900">{version.prompt_text}</span><span className="mt-1 block text-[11px] text-slate-500">{question.origin_type.replace('_', ' ')} · {version.marks_total} marks · {version.difficulty_level} · {version.parts.reduce((n, part) => n + part.concept_allocations.length, 0)} concept mappings</span></span></label>; })}</div> : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">No approved Question Bank records are available for this course.</p>}
      </section>
    </div>;
  }

  if (isTeacher && mode === 'manual_form') {
    return (
      <div className="space-y-5 pb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={() => setMode('list')}
            className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1 cursor-pointer"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Back to Quizzes
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={savingQuiz}
              onClick={() => void handleSaveManualQuiz(false)}
              className="btn-outline text-xs px-4 py-2 cursor-pointer disabled:opacity-50"
            >
              Save as Draft
            </button>
            <button
              type="button"
              disabled={savingQuiz}
              onClick={() => void handleSaveManualQuiz(true)}
              className="btn-primary text-xs px-5 py-2 inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              {savingQuiz ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              Publish Quiz
            </button>
          </div>
        </div>

        {/* Google Forms style header card matching DoubtDesk borders */}
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white overflow-hidden">
          <div className="h-2 bg-[#0A8FF5]" />
          <div className="p-5 sm:p-6 space-y-4">
            <input
              type="text"
              value={manualTitle}
              onChange={(e) => setManualTitle(e.target.value)}
              placeholder="Quiz Title (e.g. Unit 1: Asymptotic Analysis & Recurrences)"
              className="w-full text-xl font-bold text-[#111111] placeholder-slate-400 border-b border-transparent hover:border-[#DCE7EE] focus:border-[#0A8FF5] focus:outline-none pb-1 transition"
            />
            <textarea
              rows={2}
              value={manualDescription}
              onChange={(e) => setManualDescription(e.target.value)}
              placeholder="Quiz description or instructions for students..."
              className="w-full text-xs text-[#4D5963] placeholder-slate-400 border-b border-transparent hover:border-[#DCE7EE] focus:border-[#0A8FF5] focus:outline-none resize-none pb-1 transition"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              <div className="space-y-1">
                <label className="text-[11px] font-bold text-[#71808C] uppercase tracking-wider">
                  Assigned Course
                </label>
                <select
                  value={builderOfferingId}
                  onChange={(e) => setBuilderOfferingId(e.target.value)}
                  className="w-full h-9 px-3 rounded-lg border border-[#DCE7EE] text-xs font-semibold text-[#111111] bg-white focus:outline-none focus:border-[#0A8FF5]"
                >
                  {offerings.map((o) => (
                    <option key={o.id} value={o.id}>
                      {formatOfferingLabel(o)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-[11px] font-bold text-[#71808C] uppercase tracking-wider">
                  Time Limit (Minutes)
                </label>
                <input
                  type="number"
                  min={1}
                  max={180}
                  value={manualTimeLimit}
                  onChange={(e) => setManualTimeLimit(Number(e.target.value))}
                  className="w-full h-9 px-3 rounded-lg border border-[#DCE7EE] text-xs font-semibold text-[#111111] focus:outline-none focus:border-[#0A8FF5]"
                />
              </div>
            </div>
          </div>
        </div>

        {aiSources.length > 0 && <section className="rounded-xl border border-blue-100 bg-blue-50 p-4">
          <h3 className="text-xs font-bold text-slate-900">Retrieved course sources</h3>
          <p className="mt-1 text-[11px] text-slate-600">AI draft generated from reviewed excerpts. Source references are retained here for review.</p>
          <ul className="mt-2 space-y-1">{aiSources.map((source) => <li key={source.source_chunk_id} className="text-[11px] text-slate-700">
            {source.filename}{source.page_number ? ` · page ${source.page_number}` : ''}{source.slide_number ? ` · slide ${source.slide_number}` : ''}
          </li>)}</ul>
        </section>}

        {/* Question Builder Cards */}
        <div className="space-y-4">
          {manualQuestions.map((q, qIdx) => (
            <div key={q.id} className="border border-[#DCE7EE] rounded-[16px] bg-white p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#EDF4F8]">
                <span className="text-xs font-extrabold text-[#0A8FF5] uppercase tracking-wider">
                  Question {qIdx + 1}
                </span>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 text-xs text-[#4D5963]">
                    <span>Marks:</span>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={q.marks}
                      onChange={(e) => {
                        const val = Number(e.target.value);
                        setManualQuestions((prev) =>
                          prev.map((item, idx) => (idx === qIdx ? { ...item, marks: val } : item))
                        );
                      }}
                      className="w-12 h-7 px-1.5 rounded border border-[#DCE7EE] text-center text-xs font-bold"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDuplicateQuestion(qIdx)}
                    className="p-1.5 text-[#71808C] hover:text-[#111111] rounded-lg hover:bg-[#EDF4F8] transition cursor-pointer"
                    title="Duplicate Question"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteQuestion(qIdx)}
                    className="p-1.5 text-[#71808C] hover:text-rose-600 rounded-lg hover:bg-rose-50 transition cursor-pointer"
                    title="Delete Question"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <textarea
                rows={2}
                value={q.statement}
                onChange={(e) => {
                  const val = e.target.value;
                  setManualQuestions((prev) =>
                    prev.map((item, idx) => (idx === qIdx ? { ...item, statement: val } : item))
                  );
                }}
                placeholder="Enter question statement..."
                className="w-full text-sm font-semibold text-[#111111] placeholder-slate-400 p-3 rounded-xl bg-[#F8FAFC] border border-[#DCE7EE] focus:bg-white focus:outline-none focus:border-[#0A8FF5]"
              />

              <div className="space-y-2.5">
                <span className="text-[11px] font-bold text-[#71808C] uppercase tracking-wider block">
                  Options (Click radio circle to mark correct answer)
                </span>
                {q.options.map((opt, optIdx) => (
                  <div key={opt.id} className="flex items-center gap-2.5">
                    <button
                      type="button"
                      onClick={() =>
                        setManualQuestions((prev) =>
                          prev.map((item, idx) =>
                            idx !== qIdx
                              ? item
                              : {
                                  ...item,
                                  options: item.options.map((o) => ({
                                    ...o,
                                    isCorrect: o.id === opt.id,
                                  })),
                                }
                          )
                        )
                      }
                      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition cursor-pointer ${
                        opt.isCorrect
                          ? 'border-emerald-600 bg-emerald-600 text-white'
                          : 'border-slate-300 hover:border-slate-400'
                      }`}
                      title={opt.isCorrect ? 'Correct Answer' : 'Mark as Correct Answer'}
                    >
                      {opt.isCorrect && <Check className="w-3 h-3 stroke-[3]" />}
                    </button>

                    <input
                      type="text"
                      value={opt.text}
                      onChange={(e) => {
                        const val = e.target.value;
                        setManualQuestions((prev) =>
                          prev.map((item, idx) =>
                            idx !== qIdx
                              ? item
                              : {
                                  ...item,
                                  options: item.options.map((o) =>
                                    o.id === opt.id ? { ...o, text: val } : o
                                  ),
                                }
                          )
                        );
                      }}
                      placeholder={`Option ${optIdx + 1}`}
                      className={`flex-1 h-9 px-3 text-xs rounded-lg border focus:outline-none transition ${
                        opt.isCorrect
                          ? 'border-emerald-300 bg-emerald-50/50 text-emerald-900 font-medium'
                          : 'border-[#DCE7EE] text-[#111111] focus:border-[#0A8FF5]'
                      }`}
                    />

                    {q.options.length > 2 && (
                      <button
                        type="button"
                        onClick={() =>
                          setManualQuestions((prev) =>
                            prev.map((item, idx) =>
                              idx !== qIdx
                                ? item
                                : { ...item, options: item.options.filter((o) => o.id !== opt.id) }
                            )
                          )
                        }
                        className="text-[#71808C] hover:text-[#111111] p-1 cursor-pointer"
                        title="Remove Option"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}

                <button
                  type="button"
                  onClick={() =>
                    setManualQuestions((prev) =>
                      prev.map((item, idx) =>
                        idx !== qIdx
                          ? item
                          : {
                              ...item,
                              options: [
                                ...item.options,
                                {
                                  id: `opt-${Date.now()}-${item.options.length + 1}`,
                                  text: '',
                                  isCorrect: false,
                                },
                              ],
                            }
                      )
                    )
                  }
                  className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1 pt-1 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Option
                </button>
              </div>

              <input
                type="text"
                value={q.explanation}
                onChange={(e) => {
                  const val = e.target.value;
                  setManualQuestions((prev) =>
                    prev.map((item, idx) => (idx === qIdx ? { ...item, explanation: val } : item))
                  );
                }}
                placeholder="Solution explanation (shown after student submits)..."
                className="w-full h-8 px-3 text-xs rounded-lg border border-[#DCE7EE] bg-[#F8FAFC] text-[#4D5963] placeholder-slate-400 focus:bg-white focus:outline-none focus:border-[#0A8FF5]"
              />
            </div>
          ))}

          <button
            type="button"
            onClick={() => setManualQuestions((prev) => [...prev, createEmptyQuestion()])}
            className="w-full py-3.5 rounded-[16px] border-2 border-dashed border-[#DCE7EE] hover:border-[#0A8FF5] hover:bg-[#EAF5FF]/40 text-[#4D5963] hover:text-[#0A8FF5] text-xs font-bold flex items-center justify-center gap-2 transition cursor-pointer"
          >
            <Plus className="w-4 h-4" /> Add Question
          </button>
        </div>
      </div>
    );
  }

  // =========================================================================
  // VIEW 4: Default Quizzes List (Reuses standard DoubtDesk strip & cards)
  // =========================================================================
  return (
    <div className="space-y-5">
      {/* Top Action & Filter Strip matching FeedFilters aesthetic */}
      {isTeacher && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="relative inline-flex items-center">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as 'all' | 'published' | 'draft')}
              className="h-10 pl-4 pr-9 rounded-full bg-[#EBF2F7] hover:bg-[#E2ECF2] text-[#111111] text-xs sm:text-[13px] font-bold border-none cursor-pointer focus:outline-none appearance-none transition-colors"
            >
              <option value="all">All quizzes ({quizzes.length})</option>
              <option value="published">
                Published ({quizzes.filter((q) => q.assessment.status === 'published').length})
              </option>
              <option value="draft">
                Drafts ({quizzes.filter((q) => q.assessment.status !== 'published').length})
              </option>
            </select>
            <ChevronDown className="w-4 h-4 text-[#4D5963] absolute right-3 pointer-events-none" />
          </div>

          <div className="flex items-center gap-2.5 flex-wrap">
            <button type="button" disabled={!offerings.length || bankLoading} onClick={() => void openQuestionBankBuilder()} className="btn-outline text-xs px-4 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50">
              {bankLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <FileText className="w-3.5 h-3.5"/>} Question Bank
            </button>
            <button
              type="button"
              disabled={!offerings.length}
              onClick={() => setIsAiModalOpen(true)}
              className="btn-primary text-xs px-4 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" /> Generate Quiz
            </button>
            <button
              type="button"
              disabled={!offerings.length}
              onClick={() => openManualBuilder()}
              className="btn-outline text-xs px-4 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
            >
              <FileText className="w-3.5 h-3.5 text-[#4D5963]" /> Create Manually
            </button>
          </div>
        </div>
      )}

      {/* Quizzes List / Loading / Empty State */}
      {loading ? (
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-10 text-center text-xs text-[#71808C]">
          <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-[#0A8FF5]" />
          Loading quizzes...
        </div>
      ) : visibleQuizzes.length === 0 ? (
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-10 sm:p-14 text-center">
          <div className="w-14 h-14 rounded-full bg-[#F4F7F9] flex items-center justify-center text-[#71808C] mx-auto mb-4 shadow-xs">
            <Award className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-bold text-[#111111] mb-4">
            {isTeacher ? 'No Quizzes Created Yet' : 'No Practice Quizzes Published Yet'}
          </h2>
          {isTeacher ? (
            <div className="flex items-center justify-center gap-3 flex-wrap">
              <button
                type="button"
                disabled={!offerings.length}
                onClick={() => setIsAiModalOpen(true)}
                className="btn-primary text-xs px-5 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" /> Generate Quiz (AI)
              </button>
              <button
                type="button"
                disabled={!offerings.length}
                onClick={() => openManualBuilder()}
                className="btn-outline text-xs px-5 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                <FileText className="w-3.5 h-3.5" /> Create Manually
              </button>
              <button type="button" disabled={!offerings.length || bankLoading} onClick={() => void openQuestionBankBuilder()} className="btn-outline text-xs px-5 py-2.5 inline-flex items-center gap-1.5 disabled:opacity-50">
                {bankLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin"/> : <FileText className="w-3.5 h-3.5"/>} Use Question Bank
              </button>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F4F7F9] text-xs font-semibold text-[#4D5963]">
              <HelpCircle className="w-4 h-4 text-[#0A8FF5]" />
              <span>Faculty has not scheduled any quizzes yet</span>
            </div>
          )}
        </div>
      ) : isTeacher ? (
        <div className="space-y-4">
          {visibleQuizzes.map(({ assessment, offering }) => {
            const items = assessment.latest_version?.items || [];
            const totalMarks = items.reduce((sum, it) => sum + it.marks_available, 0);
            const mins = Math.round((assessment.latest_version?.duration_seconds || 900) / 60);

            return (
              <div
                key={assessment.id}
                className="border border-[#DCE7EE] bg-white rounded-[16px] p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-[#0A8FF5]/50 transition"
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-[#111111]">{assessment.title}</span>
                    <span
                      className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full ${
                        assessment.status === 'published'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {assessment.status === 'published' ? 'Published' : 'Draft'}
                    </span>
                  </div>
                  {assessment.description && (
                    <p className="text-xs text-[#4D5963] line-clamp-1">{assessment.description}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-2.5 text-[11px] text-[#71808C]">
                    <span className="font-semibold text-[#0A8FF5]">{formatOfferingLabel(offering)}</span>
                    <span>•</span>
                    <span>{items.length} Questions ({totalMarks} Marks)</span>
                    <span>•</span>
                    <span>{mins} mins</span>
                    <span>•</span>
                    <span>{new Date(assessment.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setPreviewTarget({ assessment, offering });
                      setMode('preview');
                    }}
                    className="px-3 py-1.5 rounded-full border border-[#DCE7EE] hover:bg-[#F4F7F9] text-xs font-semibold text-[#111111] inline-flex items-center gap-1 transition cursor-pointer"
                  >
                    <Eye className="w-3.5 h-3.5" /> Preview
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleTogglePublish(assessment)}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition cursor-pointer ${
                      assessment.status === 'published'
                        ? 'border border-amber-200 text-amber-700 hover:bg-amber-50'
                        : 'bg-emerald-600 text-white hover:bg-emerald-700'
                    }`}
                  >
                    {assessment.status === 'published' ? 'Unpublish' : 'Publish'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteQuiz(assessment.id)}
                    className="p-1.5 text-[#71808C] hover:text-rose-600 rounded-full hover:bg-rose-50 transition cursor-pointer"
                    title="Delete Quiz"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {visibleQuizzes.map(({ assessment, offering }) => {
            const items = assessment.latest_version?.items || [];
            const totalMarks = items.reduce((sum, it) => sum + it.marks_available, 0);
            const mins = Math.round((assessment.latest_version?.duration_seconds || 900) / 60);

            return (
              <div
                key={assessment.id}
                className="border border-[#DCE7EE] bg-white rounded-[16px] p-5 sm:p-6 flex flex-col justify-between space-y-4 hover:border-[#0A8FF5] transition"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="text-[11px] font-bold text-[#0A8FF5] uppercase tracking-wider truncate">
                      {offering?.subject_name || offering?.official_subject_code || 'Course Quiz'}
                    </span>
                    <span className="text-xs font-semibold text-[#71808C] inline-flex items-center gap-1 shrink-0">
                      <Clock className="w-3.5 h-3.5" /> {mins}m
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-[#111111] leading-snug">{assessment.title}</h3>
                  {assessment.description && (
                    <p className="text-xs text-[#4D5963] mt-1 line-clamp-2">{assessment.description}</p>
                  )}
                </div>

                <div className="pt-3 border-t border-[#EDF4F8] flex items-center justify-between gap-2">
                  <span className="text-xs text-[#4D5963] font-medium">
                    {items.length} Questions • {totalMarks} Marks
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleStartStudentQuiz({ assessment, offering })}
                    className="btn-primary text-xs px-4 py-2 cursor-pointer"
                  >
                    Start Quiz
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!isTeacher && interventions.length > 0 && (
        <section className="rounded-[16px] border border-blue-200 bg-white p-5 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-[#111111]">Targeted Learning Support</h3>
            <p className="text-xs text-[#4D5963] mt-0.5">
              Assigned interventions unlock in order: baseline, targeted practice, then reassessment.
            </p>
          </div>
          <div className="space-y-3">
            {interventions.map((x) => (
              <article key={x.intervention_id} className="rounded-xl border border-[#DCE7EE] p-4 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-[#111111]">{x.title}</h4>
                  <span className="text-[11px] font-semibold capitalize text-[#0A8FF5]">
                    Phase: {x.current_phase.replace(/_/g, ' ')}
                  </span>
                </div>
                {x.description && <p className="text-xs text-[#4D5963]">{x.description}</p>}
                <div className="grid gap-2 sm:grid-cols-3 pt-1">
                  <div className="rounded-lg bg-[#F8FAFC] p-3 text-xs">
                    <p className="font-bold text-[#111111]">A · Baseline</p>
                    <p className="mt-1 text-[#4D5963]">
                      {x.phase_a_completed ? `Completed · score ${x.phase_a_score ?? 'pending'}` : 'Diagnostic assessment'}
                    </p>
                    {x.phase_a_unlocked && !x.phase_a_completed && x.phase_a_assessment_id && (
                      <button
                        type="button"
                        onClick={() =>
                          void handleStartAssessmentById(
                            x.phase_a_assessment_id!,
                            `${x.title} · Baseline`,
                            'intervention_baseline',
                            x.offering
                          )
                        }
                        className="mt-2 font-semibold text-[#0A8FF5] hover:underline cursor-pointer"
                      >
                        Start baseline
                      </button>
                    )}
                  </div>
                  <div className="rounded-lg bg-[#F8FAFC] p-3 text-xs">
                    <p className="font-bold text-[#111111]">B · Targeted practice</p>
                    <p className="mt-1 text-[#4D5963]">
                      {x.phase_b_completed ? 'Practice complete' : x.phase_b_rule_description}
                    </p>
                    {x.phase_b_unlocked && (
                      <>
                        {x.phase_b_primer_content && (
                          <p className="mt-1.5 whitespace-pre-wrap text-[#4D5963]">{x.phase_b_primer_content}</p>
                        )}
                        {x.phase_b_practice_assessment_id && (
                          <button
                            type="button"
                            onClick={() =>
                              void handleStartAssessmentById(
                                x.phase_b_practice_assessment_id!,
                                `${x.title} · Practice`,
                                'intervention_practice',
                                x.offering
                              )
                            }
                            className="mt-2 font-semibold text-[#0A8FF5] hover:underline cursor-pointer"
                          >
                            Start / resume practice
                          </button>
                        )}
                      </>
                    )}
                  </div>
                  <div className="rounded-lg bg-[#F8FAFC] p-3 text-xs">
                    <p className="font-bold text-[#111111]">C · Reassessment</p>
                    <p className="mt-1 text-[#4D5963]">
                      {x.phase_c_completed
                        ? `Completed · score ${x.phase_c_score ?? 'pending'}`
                        : x.phase_c_unlocked
                          ? 'Available after required practice'
                          : 'Locked until practice completion'}
                    </p>
                    {x.phase_c_unlocked && !x.phase_c_completed && x.phase_c_assessment_id && (
                      <button
                        type="button"
                        onClick={() =>
                          void handleStartAssessmentById(
                            x.phase_c_assessment_id!,
                            `${x.title} · Reassessment`,
                            'intervention_post',
                            x.offering
                          )
                        }
                        className="mt-2 font-semibold text-[#0A8FF5] hover:underline cursor-pointer"
                      >
                        Start reassessment
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* AI Quiz Generator Modal (Reuses AskDoubtModal styling) */}
      {isAiModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-[20px] border border-[#DCE7EE] shadow-2xl max-w-[540px] w-full p-6 sm:p-7 relative">
            <div className="flex items-center justify-between pb-4">
              <h2 className="text-lg font-bold text-[#111111] flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#0A8FF5]" /> Generate Quiz with AI
              </h2>
              <button
                type="button"
                onClick={() => !isGenerating && setIsAiModalOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-[#71808C] hover:text-[#111111] hover:bg-[#EDF4F8] transition cursor-pointer"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleGenerateWithAi} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[#111111]">Assigned Course</label>
                <select
                  value={aiOfferingId}
                  onChange={(e) => setAiOfferingId(e.target.value)}
                  className="w-full h-10 px-3.5 rounded-xl border border-[#DCE7EE] bg-[#F8FAFC] text-xs font-semibold text-[#111111] focus:bg-white focus:outline-none focus:border-[#0A8FF5]"
                >
                  {offerings.map((o) => (
                    <option key={o.id} value={o.id}>
                      {formatOfferingLabel(o)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[#111111]">Topic or Concept Focus</label>
                <input
                  type="text"
                  required
                  value={aiTopic}
                  onChange={(e) => {
                    setAiTopic(e.target.value);
                    if (aiError) setAiError(null);
                  }}
                  placeholder="e.g. Dynamic Programming, Dijkstra's Algorithm, Master Theorem"
                  className="w-full h-10 px-3.5 rounded-xl border border-[#DCE7EE] text-xs text-[#111111] placeholder-slate-400 focus:outline-none focus:border-[#0A8FF5]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#111111]">Questions</label>
                  <select
                    value={aiQuestionCount}
                    onChange={(e) => setAiQuestionCount(Number(e.target.value))}
                    className="w-full h-10 px-3 rounded-xl border border-[#DCE7EE] bg-[#F8FAFC] text-xs font-semibold text-[#111111] focus:outline-none focus:border-[#0A8FF5]"
                  >
                    <option value={3}>3 Questions</option>
                    <option value={5}>5 Questions</option>
                    <option value={8}>8 Questions</option>
                    <option value={10}>10 Questions</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#111111]">Difficulty</label>
                  <select
                    value={aiDifficulty}
                    onChange={(e) => setAiDifficulty(e.target.value)}
                    className="w-full h-10 px-3 rounded-xl border border-[#DCE7EE] bg-[#F8FAFC] text-xs font-semibold text-[#111111] focus:outline-none focus:border-[#0A8FF5]"
                  >
                    <option value="Beginner">Beginner</option>
                    <option value="Intermediate">Intermediate</option>
                    <option value="Advanced">Advanced</option>
                  </select>
                </div>
              </div>

              {aiError && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 space-y-2">
                  <p className="font-medium leading-relaxed">{aiError}</p>
                  <button
                    type="button"
                    onClick={() => {
                      const topicTitle = aiTopic.trim();
                      setIsAiModalOpen(false);
                      setAiError(null);
                      openManualBuilder({
                        offeringId: aiOfferingId,
                        title: topicTitle ? `${topicTitle} Quiz` : '',
                      });
                    }}
                    className="inline-flex items-center gap-1.5 font-bold text-[#0A58CA] hover:underline cursor-pointer"
                  >
                    <FileText className="w-3.5 h-3.5" /> Create Manually Instead
                  </button>
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  disabled={isGenerating}
                  onClick={() => setIsAiModalOpen(false)}
                  className="btn-outline text-xs px-4 py-2 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGenerating}
                  className="btn-primary text-xs px-5 py-2 inline-flex items-center gap-1.5 disabled:opacity-60"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" /> Generate Questions
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
