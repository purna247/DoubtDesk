import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eye,
  HelpCircle,
  Layers,
  Lightbulb,
  Loader2,
  Pencil,
  Plus,
  Save,
  Send,
  Settings,
  Sparkles,
  Trash2,
  X,
  Zap,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/Button';
import { useStartAcademicExtraction } from '../../hooks/useStartAcademicExtraction';
import { useTeacherLearningWorkspace } from '../../hooks/useTeacherLearningWorkspace';
import type { ReviewSummary } from '../../api/teacherLearningWorkspace';
import type { CourseOffering } from '../../types/academics';
import type { LearningNode } from '../../types/learning';

const EMPTY_SUMMARY: ReviewSummary = {
  run_status: 'waiting_for_documents',
  generation_status: 'waiting_for_documents',
  sources_ready: false,
  publish_ready: false,
  approved_syllabus_count: 0,
  has_warnings: false,
  warnings_count: 0,
  modules_count: 0,
  topics_count: 0,
  concepts_count: 0,
  approved_concepts_count: 0,
  questions_count: 0,
  draft_nodes_count: 0,
  approved_concepts: [],
  flagged_items: [],
};

interface ActivityVersionData {
  id: string;
  version_number: number;
  activity_type: string;
  title: string;
  student_payload_json?: any;
  answer_key_json?: any;
  scoring_config_json?: any;
  approval_status: string;
}

interface ActivityItem {
  id: string;
  learning_node_id: string;
  status: string;
  created_at: string;
  latest_version?: ActivityVersionData | null;
}

type WorkspaceTab = 'questions' | 'author' | 'settings';

export const TeacherLearnWorkspace: React.FC<{
  offerings: CourseOffering[];
  selectedSubject?: string;
}> = ({ offerings, selectedSubject }) => {
  const [offeringId, setOfferingId] = useState(offerings[0]?.id ?? '');
  const [selectedId, setSelectedId] = useState('');
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('questions');

  useEffect(() => {
    if (selectedSubject && selectedSubject !== 'all') {
      const match = offerings.find(
        (o) => o.id === selectedSubject || o.curriculum_subject_entry_id === selectedSubject
      );
      if (match) {
        setOfferingId(match.id);
        return;
      }
    }
    if (!offeringId && offerings[0]?.id) {
      setOfferingId(offerings[0].id);
    }
  }, [selectedSubject, offerings, offeringId]);

  const currentOffering = useMemo(
    () => offerings.find((o) => o.id === offeringId) || offerings[0],
    [offerings, offeringId]
  );

  // Topic form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [sequence, setSequence] = useState(1);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [editorDirty, setEditorDirty] = useState(false);
  const [editorConflict, setEditorConflict] = useState(false);
  const editorNodeId = useRef('');
  const editorBaseRevision = useRef<number | null>(null);

  // Practice bank state
  const [nodeActivities, setNodeActivities] = useState<ActivityItem[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [isGeneratingPractice, setIsGeneratingPractice] = useState(false);
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);
  const [activityTypeFilter, setActivityTypeFilter] = useState<string>('all');
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  // Authoring Form State
  const [authorType, setAuthorType] = useState<'mcq' | 'true_false' | 'fill_blank' | 'one_word'>('mcq');
  const [mcqPrompt, setMcqPrompt] = useState('');
  const [optA, setOptA] = useState('');
  const [optB, setOptB] = useState('');
  const [optC, setOptC] = useState('');
  const [optD, setOptD] = useState('');
  const [correctMcq, setCorrectMcq] = useState<'opt_1' | 'opt_2' | 'opt_3' | 'opt_4'>('opt_1');

  const [tfPrompt, setTfPrompt] = useState('');
  const [tfValue, setTfValue] = useState<'true' | 'false'>('true');

  const [blankTemplate, setBlankTemplate] = useState('');
  const [blankAnswers, setBlankAnswers] = useState('');

  const [oneWordPrompt, setOneWordPrompt] = useState('');
  const [oneWordAnswers, setOneWordAnswers] = useState('');

  const [authorDifficulty, setAuthorDifficulty] = useState<'easy' | 'medium' | 'hard'>('easy');
  const [authorHint, setAuthorHint] = useState('');
  const [authorExplanation, setAuthorExplanation] = useState('');
  const [authorCitation, setAuthorCitation] = useState('');

  // In-place editing state
  const [editingActivityId, setEditingActivityId] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editForm, setEditForm] = useState<{
    activity_type: string;
    prompt: string;
    optA: string;
    optB: string;
    optC: string;
    optD: string;
    correctMcq: 'opt_1' | 'opt_2' | 'opt_3' | 'opt_4';
    tfValue: 'true' | 'false';
    blankTemplate: string;
    blankAnswers: string;
    oneWordPrompt: string;
    oneWordAnswers: string;
    difficulty: 'easy' | 'medium' | 'hard';
    hint: string;
    explanation: string;
    citation: string;
  } | null>(null);

  const toggleCardExpanded = (id: string) => {
    setExpandedCards((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const startEditingActivity = (act: ActivityItem) => {
    const ver = act.latest_version;
    const payload = ver?.student_payload_json || {};
    const key = ver?.answer_key_json || {};
    const cfg = ver?.scoring_config_json || {};
    const actType = ver?.activity_type || 'mcq';

    let rawOptA = '';
    let rawOptB = '';
    let rawOptC = '';
    let rawOptD = '';
    const rawCorrect = (key.correct_option_id || 'opt_1') as 'opt_1' | 'opt_2' | 'opt_3' | 'opt_4';

    if (actType === 'mcq' && Array.isArray(payload.options)) {
      rawOptA = payload.options[0]?.text || '';
      rawOptB = payload.options[1]?.text || '';
      rawOptC = payload.options[2]?.text || '';
      rawOptD = payload.options[3]?.text || '';
    }

    let blanksText = '';
    if (actType === 'fill_blank' && key.blanks) {
      const list = Object.values(key.blanks).flatMap((b: any) => b.accepted_answers || []);
      blanksText = list.join(', ');
    }

    let oneWordText = '';
    if (actType === 'one_word' && key.accepted_answers) {
      oneWordText = (key.accepted_answers || []).join(', ');
    }

    setEditingActivityId(act.id);
    setEditForm({
      activity_type: actType,
      prompt: payload.question || payload.template || ver?.title || '',
      optA: rawOptA,
      optB: rawOptB,
      optC: rawOptC,
      optD: rawOptD,
      correctMcq: rawCorrect,
      tfValue: key.correct_option_id === 'false' ? 'false' : 'true',
      blankTemplate: payload.template || payload.question || '',
      blankAnswers: blanksText,
      oneWordPrompt: payload.question || '',
      oneWordAnswers: oneWordText,
      difficulty: (cfg.difficulty || 'easy') as 'easy' | 'medium' | 'hard',
      hint: cfg.hint || '',
      explanation: key.explanation || cfg.explanation || '',
      citation: key.citation || cfg.citation || '',
    });
  };

  const cancelEditingActivity = () => {
    setEditingActivityId(null);
    setEditForm(null);
  };

  const saveActivityEdit = async (activityId: string) => {
    if (!editForm) return;
    setIsSavingEdit(true);
    try {
      let authoringPayload: any = {};
      let titleStr = editForm.prompt.trim().slice(0, 240);

      if (editForm.activity_type === 'mcq') {
        const optionsList = [
          { option_id: 'opt_1', text: editForm.optA.trim() },
          { option_id: 'opt_2', text: editForm.optB.trim() },
        ];
        if (editForm.optC.trim()) optionsList.push({ option_id: 'opt_3', text: editForm.optC.trim() });
        if (editForm.optD.trim()) optionsList.push({ option_id: 'opt_4', text: editForm.optD.trim() });
        authoringPayload = {
          question: editForm.prompt.trim(),
          options: optionsList,
          correct_option_id: editForm.correctMcq,
        };
      } else if (editForm.activity_type === 'true_false') {
        authoringPayload = {
          question: editForm.prompt.trim(),
          correct_option_id: editForm.tfValue,
          options: [
            { option_id: 'true', text: 'True' },
            { option_id: 'false', text: 'False' },
          ],
        };
      } else if (editForm.activity_type === 'fill_blank') {
        titleStr = editForm.blankTemplate.trim().slice(0, 240);
        const accepted = editForm.blankAnswers.split(',').map((s) => s.trim()).filter(Boolean);
        authoringPayload = {
          template: editForm.blankTemplate.trim(),
          blanks: [{ blank_id: 'blank_1', accepted_answers: accepted, explanation: editForm.explanation.trim() }],
        };
      } else if (editForm.activity_type === 'one_word') {
        titleStr = editForm.oneWordPrompt.trim().slice(0, 240);
        const accepted = editForm.oneWordAnswers.split(',').map((s) => s.trim()).filter(Boolean);
        authoringPayload = {
          question: editForm.oneWordPrompt.trim(),
          accepted_answers: accepted,
        };
      } else {
        authoringPayload = {
          question: editForm.prompt.trim(),
        };
      }

      await apiClient.patch(`/api/v1/activities/${activityId}`, {
        activity_type: editForm.activity_type,
        title: titleStr,
        instructions: 'Answer based directly on lecture notes and syllabus concepts.',
        authoring_payload: {
          ...authoringPayload,
          explanation: editForm.explanation.trim(),
        },
        scoring_config: {
          max_marks: 1.0,
          difficulty: editForm.difficulty,
          hint: editForm.hint.trim(),
          citation: editForm.citation.trim() || undefined,
          edited_by_teacher: true,
        },
      });

      setMessage('Practice question updated and live for students!');
      setEditingActivityId(null);
      setEditForm(null);
      if (selectedNode) await fetchNodeActivities(selectedNode.id);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Could not save question changes.');
    } finally {
      setIsSavingEdit(false);
    }
  };

  const academicExtraction = useStartAcademicExtraction();
  const workspaceQuery = useTeacherLearningWorkspace(offeringId);
  const nodes = workspaceQuery.data?.nodes ?? [];
  const summary = workspaceQuery.data?.summary ?? EMPTY_SUMMARY;
  const loading = workspaceQuery.isLoading;

  useEffect(() => {
    if (!offerings.some((offering) => offering.id === offeringId)) {
      setOfferingId(offerings[0]?.id ?? '');
    }
  }, [offerings, offeringId]);

  useEffect(() => {
    const rows = workspaceQuery.data?.nodes ?? [];
    setSelectedId((current) => (rows.some((node) => node.id === current) ? current : rows[0]?.id ?? ''));
  }, [workspaceQuery.data?.nodes]);

  const selectedNode = nodes.find((node) => node.id === selectedId);

  useEffect(() => {
    if (!selectedNode) return;
    if (editorNodeId.current !== selectedNode.id) {
      editorNodeId.current = selectedNode.id;
      editorBaseRevision.current = selectedNode.revision;
      setTitle(selectedNode.title);
      setDescription(selectedNode.description ?? '');
      setSequence(selectedNode.sequence_no);
      setEditorDirty(false);
      setEditorConflict(false);
      setPreview(false);
      return;
    }
    if (selectedNode.revision !== editorBaseRevision.current) {
      if (editorDirty) {
        setEditorConflict(true);
        return;
      }
      editorBaseRevision.current = selectedNode.revision;
      setTitle(selectedNode.title);
      setDescription(selectedNode.description ?? '');
      setSequence(selectedNode.sequence_no);
      setEditorConflict(false);
    }
  }, [selectedNode?.id, selectedNode?.revision, editorDirty]);

  // Load activities whenever the active node changes
  const fetchNodeActivities = useCallback(async (nodeId: string) => {
    if (!nodeId) return;
    setLoadingActivities(true);
    try {
      const data = await apiClient.get<ActivityItem[]>(`/api/v1/learning-nodes/${nodeId}/activities`);
      setNodeActivities(Array.isArray(data) ? data : []);
    } catch {
      setNodeActivities([]);
    } finally {
      setLoadingActivities(false);
    }
  }, []);

  useEffect(() => {
    if (selectedNode?.id) {
      void fetchNodeActivities(selectedNode.id);
    } else {
      setNodeActivities([]);
    }
  }, [selectedNode?.id, fetchNodeActivities]);

  const saveNode = async () => {
    if (!selectedNode || selectedNode.status !== 'draft' || editorConflict) return;
    setBusy(true);
    try {
      const saved = await apiClient.patch<LearningNode>(`/api/v1/learning-nodes/${selectedNode.id}`, {
        title: title.trim(),
        description: description.trim() || null,
        sequence_no: Number(sequence),
        expected_revision: selectedNode.revision,
      });
      editorBaseRevision.current = saved.revision;
      setEditorDirty(false);
      setEditorConflict(false);
      setMessage('Draft saved successfully.');
      await workspaceQuery.refetch();
    } catch (err: unknown) {
      setEditorConflict(true);
      setMessage(err instanceof Error ? err.message : 'Could not save topic edits.');
    } finally {
      setBusy(false);
    }
  };

  const publishCurrentNode = async () => {
    if (!selectedNode || busy) return;
    setBusy(true);
    try {
      await apiClient.post(`/api/v1/learning-nodes/${selectedNode.id}/publish`, {});
      await workspaceQuery.refetch();
      setMessage(`"${selectedNode.title}" is now published and live for enrolled students!`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Could not publish this topic.');
    } finally {
      setBusy(false);
    }
  };

  const publishAll = async () => {
    if (
      busy ||
      !offeringId ||
      !summary.course_content_version_id ||
      !summary.publish_ready ||
      ['queued', 'running', 'retrying'].includes(summary.generation_status)
    )
      return;
    setBusy(true);
    try {
      const res = await apiClient.post<{ published_nodes: number }>(
        `/api/v1/courses/${offeringId}/academic-review/publish-all`,
        {}
      );
      await workspaceQuery.refetch();
      setMessage(
        `All course topics (${res.published_nodes ?? summary.draft_nodes_count}) are now published and live for students!`
      );
    } catch (err: unknown) {
      setMessage(
        err instanceof Error
          ? err.message
          : 'Could not publish course content. Please verify all extraction runs completed.'
      );
    } finally {
      setBusy(false);
    }
  };

  const startExtraction = async () => {
    if (!offeringId || !summary.sources_ready || academicExtraction.isPending) return;
    setMessage('');
    try {
      const job = await academicExtraction.mutateAsync(offeringId);
      setMessage(
        job.already_queued
          ? 'Roadmap generation is already queued for these materials.'
          : 'Roadmap generation queued. Completed topics will appear as they are processed.'
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'Academic extraction could not be queued. Check material processing status.'
      );
    }
  };

  // Generate Practice Bank for Selected Node
  const generateNodePractice = async () => {
    if (!selectedNode || isGeneratingPractice) return;
    setIsGeneratingPractice(true);
    setMessage('');
    try {
      const generated = await apiClient.post<ActivityItem[]>(
        `/api/v1/learning-nodes/${selectedNode.id}/generate-practice-questions`,
        {}
      );
      setNodeActivities(Array.isArray(generated) ? generated : []);
      setMessage(`Successfully generated ${generated.length} practice questions — published & live for students!`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Practice questions could not be generated.');
    } finally {
      setIsGeneratingPractice(false);
    }
  };

  // Generate All Practice Questions Course-Wide
  const generateAllCoursePractice = async () => {
    if (!offeringId || isGeneratingAll) return;
    setIsGeneratingAll(true);
    setMessage('');
    try {
      const res = await apiClient.post<{ nodes_count: number; total_questions: number }>(
        `/api/v1/courses/${offeringId}/generate-all-practice-questions`,
        {}
      );
      if (selectedNode) {
        await fetchNodeActivities(selectedNode.id);
      }
      setMessage(`Generated ${res.total_questions} practice questions across ${res.nodes_count} roadmap topics!`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Course-wide practice generation failed.');
    } finally {
      setIsGeneratingAll(false);
    }
  };

  // Delete / Archive Activity
  const deleteActivity = async (activityId: string) => {
    if (!confirm('Are you sure you want to remove this practice item?')) return;
    try {
      await apiClient.delete(`/api/v1/activities/${activityId}`);
      if (selectedNode) await fetchNodeActivities(selectedNode.id);
      setMessage('Practice item archived.');
    } catch {
      setMessage('Could not delete practice question.');
    }
  };

  // Author Practice Question Submit
  const createPractice = async () => {
    if (!selectedNode) return;
    setBusy(true);
    try {
      let payload: any = {};
      let titleStr = '';

      if (authorType === 'mcq') {
        if (!mcqPrompt.trim() || !optA.trim() || !optB.trim()) {
          setMessage('Please provide a prompt and at least Option A and Option B.');
          setBusy(false);
          return;
        }
        titleStr = mcqPrompt.trim().slice(0, 240);
        const optionsList = [
          { option_id: 'opt_1', text: optA.trim() },
          { option_id: 'opt_2', text: optB.trim() },
        ];
        if (optC.trim()) optionsList.push({ option_id: 'opt_3', text: optC.trim() });
        if (optD.trim()) optionsList.push({ option_id: 'opt_4', text: optD.trim() });
        payload = {
          question: mcqPrompt.trim(),
          options: optionsList,
          correct_option_id: correctMcq,
        };
      } else if (authorType === 'true_false') {
        if (!tfPrompt.trim()) {
          setMessage('Please provide a True/False statement.');
          setBusy(false);
          return;
        }
        titleStr = tfPrompt.trim().slice(0, 240);
        payload = {
          question: tfPrompt.trim(),
          correct_option_id: tfValue,
          options: [
            { option_id: 'true', text: 'True' },
            { option_id: 'false', text: 'False' },
          ],
        };
      } else if (authorType === 'fill_blank') {
        if (!blankTemplate.trim() || !blankAnswers.trim()) {
          setMessage('Please provide a sentence template with [blank_1] and accepted answer(s).');
          setBusy(false);
          return;
        }
        titleStr = blankTemplate.trim().slice(0, 240);
        const accepted = blankAnswers.split(',').map((s) => s.trim()).filter(Boolean);
        payload = {
          template: blankTemplate.trim(),
          blanks: [{ blank_id: 'blank_1', accepted_answers: accepted, explanation: authorExplanation.trim() }],
        };
      } else if (authorType === 'one_word') {
        if (!oneWordPrompt.trim() || !oneWordAnswers.trim()) {
          setMessage('Please provide a question prompt and accepted keyword answer(s).');
          setBusy(false);
          return;
        }
        titleStr = oneWordPrompt.trim().slice(0, 240);
        const accepted = oneWordAnswers.split(',').map((s) => s.trim()).filter(Boolean);
        payload = {
          question: oneWordPrompt.trim(),
          accepted_answers: accepted,
        };
      }

      await apiClient.post(`/api/v1/learning-nodes/${selectedNode.id}/activities`, {
        activity_type: authorType,
        title: titleStr,
        instructions: 'Answer based directly on lecture notes and syllabus concepts.',
        authoring_payload: {
          ...payload,
          explanation: authorExplanation.trim() || `Key concept in ${selectedNode.title}`,
        },
        scoring_config: {
          max_marks: 1.0,
          difficulty: authorDifficulty,
          hint: authorHint.trim(),
          citation: authorCitation.trim() || undefined,
        },
      });

      setMessage('Practice item saved! Evaluated deterministically with 0 LLM tokens.');
      setMcqPrompt('');
      setOptA('');
      setOptB('');
      setOptC('');
      setOptD('');
      setTfPrompt('');
      setBlankTemplate('');
      setBlankAnswers('');
      setOneWordPrompt('');
      setOneWordAnswers('');
      setAuthorHint('');
      setAuthorExplanation('');
      setAuthorCitation('');
      setMessage('Practice question authored and published to students!');
      await fetchNodeActivities(selectedNode.id);
      setActiveTab('questions'); // Return directly to practice bank tab
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Could not save practice item.');
    } finally {
      setBusy(false);
    }
  };

  const groupedNodes = useMemo(() => {
    const groups = new Map<string, LearningNode[]>();
    for (const node of nodes) {
      const moduleTitle = node.module_title || 'Other course topics';
      groups.set(moduleTitle, [...(groups.get(moduleTitle) ?? []), node]);
    }
    return [...groups.entries()];
  }, [nodes]);

  const filteredActivities = useMemo(() => {
    if (activityTypeFilter === 'all') return nodeActivities;
    return nodeActivities.filter((act) => act.latest_version?.activity_type === activityTypeFilter);
  }, [nodeActivities, activityTypeFilter]);

  const countsByType = useMemo(() => {
    const counts: Record<string, number> = { mcq: 0, true_false: 0, fill_blank: 0, one_word: 0 };
    for (const act of nodeActivities) {
      const t = act.latest_version?.activity_type;
      if (t && counts[t] !== undefined) counts[t]++;
    }
    return counts;
  }, [nodeActivities]);

  const generationActive = ['queued', 'running', 'retrying'].includes(summary.generation_status);
  const canGenerateRoadmap = summary.sources_ready && ['ready', 'failed'].includes(summary.generation_status);
  const allNodesPublished = nodes.length > 0 && nodes.every((n) => n.status === 'published');

  const selectNode = (nodeId: string) => {
    if (editorDirty && nodeId !== selectedId) {
      setMessage('Save your changes on the current topic before switching.');
      return;
    }
    setSelectedId(nodeId);
  };

  const reloadLatestNode = () => {
    setEditorDirty(false);
    setEditorConflict(false);
    void workspaceQuery.refetch();
  };

  return (
    <div className="space-y-4 pb-12">
      {/* Unified Course Action Bar */}
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white px-5 py-4 rounded-[16px] border border-[#DCE7EE] shadow-xs">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-[#111111]">
            {[currentOffering?.official_subject_code, currentOffering?.subject_name].filter(Boolean).join(' · ') || 'Course Roadmap'}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-xs text-[#71808C] flex-wrap">
            <span>{summary.modules_count || 4} modules</span>
            <span>·</span>
            <span>{nodes.length} topics</span>
            <span>·</span>
            <span>{summary.questions_count || 0} questions</span>
            <span>·</span>
            {allNodesPublished ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-0.5 text-[11px] font-semibold">
                <Check className="h-3 w-3" /> All Published
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-0.5 text-[11px] font-semibold">
                {summary.draft_nodes_count} in Draft
              </span>
            )}
          </div>
        </div>

        {/* Global Primary Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {canGenerateRoadmap && (
            <Button
              type="button"
              variant="outline"
              onClick={() => void startExtraction()}
              disabled={busy || loading || academicExtraction.isPending}
              className="text-xs h-9 px-3.5 border-[#DCE7EE] text-[#111111] hover:bg-[#F4F7F9]"
            >
              {academicExtraction.isPending ? 'Queueing…' : 'Generate Roadmap'}
            </Button>
          )}

          <Button
            type="button"
            variant="outline"
            onClick={() => void generateAllCoursePractice()}
            disabled={busy || loading || isGeneratingAll || !nodes.length}
            className="text-xs h-9 px-3.5 border-[#DCE7EE] text-[#111111] hover:bg-[#F4F7F9]"
          >
            {isGeneratingAll ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                Generating Bank…
              </>
            ) : (
              <>
                <Zap className="mr-1.5 h-3.5 w-3.5 text-amber-500" />
                Generate All Questions
              </>
            )}
          </Button>

          <Button
            type="button"
            onClick={() => void publishAll()}
            disabled={busy || loading || allNodesPublished || generationActive}
            className={`text-xs h-9 px-4 font-semibold ${
              allNodesPublished
                ? 'bg-[#F4F7F9] text-[#71808C] border border-[#DCE7EE] cursor-default'
                : 'btn-primary'
            }`}
          >
            {allNodesPublished ? (
              <>
                <Check className="mr-1 h-3.5 w-3.5" /> Published
              </>
            ) : (
              <>
                <Send className="mr-1 h-3.5 w-3.5" /> Publish All Content
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Alert / Notification Banner */}
      {message && (
        <div className="flex items-center justify-between rounded-xl bg-[#EAF5FF] border border-[#B8D9F5] px-4 py-2.5 text-sm text-[#0A8FF5]">
          <p className="font-medium">{message}</p>
          <button onClick={() => setMessage('')} className="text-[#0A8FF5] hover:opacity-75 cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Main 2-Column Split Workspace */}
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[320px_minmax(0,1fr)] items-start">
        {/* Left Column: Clean Roadmap Topic Outline */}
        <nav
          aria-label="Roadmap Outline"
          className="rounded-[16px] border border-[#DCE7EE] bg-white p-3.5 shadow-xs space-y-3 max-h-[calc(100vh-190px)] overflow-y-auto"
        >
          <div className="flex items-center justify-between px-2 pb-2 border-b border-[#DCE7EE]">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#71808C] flex items-center gap-1.5">
              <BookOpen className="h-3.5 w-3.5 text-[#0A8FF5]" />
              Roadmap Topics ({nodes.length})
            </h2>
          </div>

          {loading ? (
            <div className="py-8 text-center text-slate-400 flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              <span className="text-xs">Loading topics…</span>
            </div>
          ) : groupedNodes.length ? (
            <div className="space-y-4">
              {groupedNodes.map(([moduleTitle, moduleNodes]) => (
                <div key={moduleTitle} className="space-y-1">
                  <p className="px-1 text-2xs font-bold uppercase tracking-wide text-slate-400 truncate" title={moduleTitle}>
                    {moduleTitle}
                  </p>
                  <div className="space-y-1">
                    {moduleNodes.map((node) => {
                      const isSelected = selectedId === node.id;
                      const isPublished = node.status === 'published';
                      return (
                        <button
                          key={node.id}
                          onClick={() => selectNode(node.id)}
                          className={`w-full rounded-xl px-3 py-2.5 text-left transition flex items-start gap-2.5 cursor-pointer ${
                            isSelected
                              ? 'bg-[#EAF5FF] text-[#0A8FF5] font-semibold border border-[#B8D9F5]'
                              : 'text-[#111111] hover:bg-[#F4F7F9] border border-transparent'
                          }`}
                        >
                          <span className="text-[11px] font-mono text-[#71808C] mt-0.5">{node.sequence_no}.</span>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs leading-snug line-clamp-2">{node.title}</p>
                            <div className="mt-1 flex items-center gap-1.5">
                              <span
                                className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                                  isPublished
                                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                    : 'bg-amber-50 text-amber-800 border border-amber-200'
                                }`}
                              >
                                {isPublished ? 'Published' : 'Draft'}
                              </span>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="p-3 text-xs text-[#71808C] text-center">No roadmap nodes available.</p>
          )}
        </nav>

        {/* Right Column: Selected Topic Workspace with Tabs */}
        <main className="space-y-4">
          {selectedNode ? (
            <>
              {/* Topic Header Card */}
              <div className="rounded-[16px] border border-[#DCE7EE] bg-white p-5 shadow-xs">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
                        {selectedNode.module_title || 'Roadmap Topic'}
                      </span>
                      <span className="text-xs text-[#71808C]">·</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                          selectedNode.status === 'published'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-800 border border-amber-200'
                        }`}
                      >
                        {selectedNode.status === 'published' ? 'Published to Students' : 'Draft'}
                      </span>
                    </div>
                    <h2 className="mt-1.5 text-lg sm:text-xl font-bold text-[#111111]">{selectedNode.title}</h2>
                    {selectedNode.description && (
                      <p className="mt-1 text-xs text-[#71808C] line-clamp-2 leading-relaxed">
                        {selectedNode.description}
                      </p>
                    )}
                  </div>

                  {/* Header Actions */}
                  <div className="flex items-center gap-2">
                    {selectedNode.status === 'draft' ? (
                      <Button
                        type="button"
                        onClick={() => void publishCurrentNode()}
                        disabled={busy}
                        className="text-xs h-8 bg-emerald-600 text-white hover:bg-emerald-700"
                      >
                        <Send className="mr-1 h-3.5 w-3.5" /> Publish This Topic
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        onClick={() => void publishCurrentNode()}
                        disabled={busy}
                        className="text-xs h-8 bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                        title="Topic and practice questions are live to students. Click to re-sync."
                      >
                        <CheckCircle2 className="mr-1 h-3.5 w-3.5 text-emerald-600" /> Published to Students
                      </Button>
                    )}

                    <button
                      type="button"
                      onClick={() => setPreview((v) => !v)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[#DCE7EE] bg-white px-3 py-1.5 text-xs font-semibold text-[#111111] hover:bg-[#F4F7F9] transition cursor-pointer"
                    >
                      <Eye className="h-3.5 w-3.5 text-[#71808C]" />
                      {preview ? 'Exit Student Preview' : 'Student Preview'}
                    </button>
                  </div>
                </div>

                {/* Tab Navigation */}
                <div className="flex items-center gap-2 border-b border-[#DCE7EE] mt-5 pt-1">
                  <button
                    onClick={() => setActiveTab('questions')}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs font-bold border-b-2 transition cursor-pointer ${
                      activeTab === 'questions'
                        ? 'border-[#0A8FF5] text-[#0A8FF5]'
                        : 'border-transparent text-[#71808C] hover:text-[#111111]'
                    }`}
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                    Practice Bank ({nodeActivities.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('author')}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs font-bold border-b-2 transition cursor-pointer ${
                      activeTab === 'author'
                        ? 'border-[#0A8FF5] text-[#0A8FF5]'
                        : 'border-transparent text-[#71808C] hover:text-[#111111]'
                    }`}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Author Question
                  </button>
                  <button
                    onClick={() => setActiveTab('settings')}
                    className={`flex items-center gap-1.5 px-3 py-2 text-xs font-bold border-b-2 transition cursor-pointer ${
                      activeTab === 'settings'
                        ? 'border-[#0A8FF5] text-[#0A8FF5]'
                        : 'border-transparent text-[#71808C] hover:text-[#111111]'
                    }`}
                  >
                    <Settings className="h-3.5 w-3.5" />
                    Topic Settings
                  </button>
                </div>
              </div>

              {/* Student Preview Modal/Box */}
              {preview && (
                <div className="rounded-xl border border-[#B8D9F5] bg-[#EAF5FF]/40 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5] flex items-center gap-1">
                      <Eye className="h-3.5 w-3.5" /> Student View Simulation
                    </span>
                    <button
                      onClick={() => setPreview(false)}
                      className="text-[#71808C] hover:text-[#111111] text-xs font-semibold cursor-pointer"
                    >
                      Close
                    </button>
                  </div>
                  <h3 className="text-base font-bold text-[#111111]">{title}</h3>
                  <p className="text-xs text-[#4D5963] leading-relaxed whitespace-pre-wrap">
                    {description || 'No objective or syllabus description set for this topic.'}
                  </p>
                </div>
              )}

              {/* TAB 1: PRACTICE BANK */}
              {activeTab === 'questions' && (
                <div className="space-y-4">
                  {/* Filter & Action Toolbar */}
                  <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3.5 rounded-[16px] border border-[#DCE7EE] shadow-xs">
                    {/* Filter Pills */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      {[
                        { key: 'all', label: `All (${nodeActivities.length})` },
                        { key: 'mcq', label: `MCQ (${countsByType.mcq})` },
                        { key: 'true_false', label: `True/False (${countsByType.true_false})` },
                        { key: 'fill_blank', label: `Blanks (${countsByType.fill_blank})` },
                        { key: 'one_word', label: `One Word (${countsByType.one_word})` },
                      ].map((item) => (
                        <button
                          key={item.key}
                          onClick={() => setActivityTypeFilter(item.key)}
                          className={`rounded-full px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                            activityTypeFilter === item.key
                              ? 'bg-[#111111] text-white shadow-xs'
                              : 'bg-[#EDF4F8] text-[#4D5963] hover:bg-[#E2ECF2]'
                          }`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      {selectedNode.status === 'published' && (
                        <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Live to Students ({nodeActivities.length})
                        </span>
                      )}

                      <Button
                        type="button"
                        onClick={() => void generateNodePractice()}
                        disabled={isGeneratingPractice || busy}
                        className="btn-primary text-xs h-8.5 inline-flex items-center gap-1"
                      >
                        {isGeneratingPractice ? (
                          <>
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                            Regenerating…
                          </>
                        ) : (
                          <>
                            <Sparkles className="mr-1.5 h-3.5 w-3.5 text-amber-300" />
                            AI Generate Practice Bank
                          </>
                        )}
                      </Button>

                      <Button
                        type="button"
                        onClick={() => setActiveTab('author')}
                        className="btn-outline text-xs h-8.5 inline-flex items-center gap-1"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        Add Question
                      </Button>
                    </div>
                  </div>

                  {/* Question Cards List */}
                  {loadingActivities ? (
                    <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2 bg-white rounded-xl border border-slate-200/90">
                      <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                      <span className="text-xs">Loading practice items…</span>
                    </div>
                  ) : filteredActivities.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center space-y-2">
                      <HelpCircle className="h-8 w-8 text-slate-300 mx-auto" />
                      <p className="text-sm font-semibold text-slate-700">No questions match this filter.</p>
                      <p className="text-xs text-slate-500 max-w-sm mx-auto">
                        Click <strong>AI Generate Practice Bank</strong> to ground questions in lecture slides, or author
                        custom questions.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {filteredActivities.map((act, index) => {
                        const ver = act.latest_version;
                        const payload = ver?.student_payload_json || {};
                        const key = ver?.answer_key_json || {};
                        const cfg = ver?.scoring_config_json || {};
                        const actType = ver?.activity_type || 'mcq';
                        const diff = cfg.difficulty || 'easy';
                        const citation = key.citation || cfg.citation;
                        const explanation = key.explanation || cfg.explanation;
                        const hint = cfg.hint;
                        const isExpanded = !!expandedCards[act.id];

                        const typeBadgeStyle: Record<string, string> = {
                          mcq: 'bg-blue-50 text-blue-700 border-blue-200',
                          true_false: 'bg-indigo-50 text-indigo-700 border-indigo-200',
                          fill_blank: 'bg-amber-50 text-amber-800 border-amber-200',
                          one_word: 'bg-purple-50 text-purple-700 border-purple-200',
                          matching_pairs: 'bg-emerald-50 text-emerald-700 border-emerald-200',
                          ordering: 'bg-pink-50 text-pink-700 border-pink-200',
                        };

                        // IN-PLACE EDIT MODE
                        if (editingActivityId === act.id && editForm) {
                          return (
                            <div
                              key={act.id}
                              className="rounded-xl border-2 border-blue-500 bg-blue-50/20 p-4 space-y-3 shadow-xs"
                            >
                              <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                                <span className="text-xs font-bold text-blue-700 flex items-center gap-1.5">
                                  <Pencil className="h-3.5 w-3.5" />
                                  Edit Question #{index + 1} ({actType.replace(/_/g, ' ')})
                                </span>
                                <button
                                  type="button"
                                  onClick={cancelEditingActivity}
                                  className="text-slate-400 hover:text-slate-600"
                                >
                                  <X className="h-4 w-4" />
                                </button>
                              </div>

                              <div>
                                <label className="block text-2xs font-semibold text-slate-600 mb-1">
                                  {actType === 'fill_blank' ? 'Template with [blank_1]' : 'Question Prompt'}
                                </label>
                                <input
                                  value={actType === 'fill_blank' ? editForm.blankTemplate : editForm.prompt}
                                  onChange={(e) => {
                                    if (actType === 'fill_blank') {
                                      setEditForm({ ...editForm, blankTemplate: e.target.value, prompt: e.target.value });
                                    } else {
                                      setEditForm({ ...editForm, prompt: e.target.value });
                                    }
                                  }}
                                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs"
                                />
                              </div>

                              {actType === 'mcq' && (
                                <div className="space-y-1.5">
                                  <label className="block text-2xs font-semibold text-slate-600">Options & Correct Answer</label>
                                  <div className="grid gap-2 sm:grid-cols-2">
                                    {[
                                      ['opt_1', editForm.optA, (v: string) => setEditForm({ ...editForm, optA: v }), 'Option A'],
                                      ['opt_2', editForm.optB, (v: string) => setEditForm({ ...editForm, optB: v }), 'Option B'],
                                      ['opt_3', editForm.optC, (v: string) => setEditForm({ ...editForm, optC: v }), 'Option C (optional)'],
                                      ['opt_4', editForm.optD, (v: string) => setEditForm({ ...editForm, optD: v }), 'Option D (optional)'],
                                    ].map(([optId, val, setter, placeholder]) => (
                                      <div key={optId as string} className="flex items-center gap-2">
                                        <input
                                          type="radio"
                                          name={`editMcq_${act.id}`}
                                          checked={editForm.correctMcq === optId}
                                          onChange={() => setEditForm({ ...editForm, correctMcq: optId as any })}
                                        />
                                        <input
                                          value={val as string}
                                          onChange={(e) => (setter as (v: string) => void)(e.target.value)}
                                          className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs"
                                          placeholder={placeholder as string}
                                        />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {actType === 'true_false' && (
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-1">Correct Choice</label>
                                  <div className="flex items-center gap-4 text-xs font-semibold">
                                    <label className="flex items-center gap-1 cursor-pointer">
                                      <input
                                        type="radio"
                                        name={`editTf_${act.id}`}
                                        checked={editForm.tfValue === 'true'}
                                        onChange={() => setEditForm({ ...editForm, tfValue: 'true' })}
                                      />
                                      True
                                    </label>
                                    <label className="flex items-center gap-1 cursor-pointer">
                                      <input
                                        type="radio"
                                        name={`editTf_${act.id}`}
                                        checked={editForm.tfValue === 'false'}
                                        onChange={() => setEditForm({ ...editForm, tfValue: 'false' })}
                                      />
                                      False
                                    </label>
                                  </div>
                                </div>
                              )}

                              {actType === 'fill_blank' && (
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-1">Accepted Answers (comma separated)</label>
                                  <input
                                    value={editForm.blankAnswers}
                                    onChange={(e) => setEditForm({ ...editForm, blankAnswers: e.target.value })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-mono"
                                  />
                                </div>
                              )}

                              {actType === 'one_word' && (
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-1">Accepted Keyword(s)</label>
                                  <input
                                    value={editForm.oneWordAnswers}
                                    onChange={(e) => setEditForm({ ...editForm, oneWordAnswers: e.target.value })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-mono"
                                  />
                                </div>
                              )}

                              <div className="grid gap-2 sm:grid-cols-2">
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Difficulty</label>
                                  <select
                                    value={editForm.difficulty}
                                    onChange={(e) => setEditForm({ ...editForm, difficulty: e.target.value as any })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs"
                                  >
                                    <option value="easy">Easy (Foundational)</option>
                                    <option value="medium">Medium (Conceptual)</option>
                                    <option value="hard">Hard (Applied)</option>
                                  </select>
                                </div>
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Lecture Citation</label>
                                  <input
                                    value={editForm.citation}
                                    onChange={(e) => setEditForm({ ...editForm, citation: e.target.value })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs"
                                    placeholder="e.g. Module 1 PPT · Slide 4"
                                  />
                                </div>
                              </div>

                              <div className="grid gap-2 sm:grid-cols-2">
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Hint</label>
                                  <input
                                    value={editForm.hint}
                                    onChange={(e) => setEditForm({ ...editForm, hint: e.target.value })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs"
                                  />
                                </div>
                                <div>
                                  <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Explanation</label>
                                  <input
                                    value={editForm.explanation}
                                    onChange={(e) => setEditForm({ ...editForm, explanation: e.target.value })}
                                    className="w-full rounded-lg border border-slate-300 bg-white px-2 py-1 text-xs"
                                  />
                                </div>
                              </div>

                              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200">
                                <Button type="button" variant="outline" onClick={cancelEditingActivity} disabled={isSavingEdit} className="text-xs h-7">
                                  Cancel
                                </Button>
                                <Button type="button" onClick={() => void saveActivityEdit(act.id)} disabled={isSavingEdit} className="text-xs h-7 bg-blue-600 text-white">
                                  {isSavingEdit ? 'Saving…' : 'Save Changes'}
                                </Button>
                              </div>
                            </div>
                          );
                        }

                        // STANDARD COMPACT DISPLAY MODE
                        return (
                          <div
                            key={act.id}
                            className="rounded-[14px] border border-[#DCE7EE] bg-white p-4 sm:p-5 space-y-3 shadow-xs hover:border-[#0A8FF5]/40 transition"
                          >
                            {/* Card Top Strip */}
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-mono font-bold text-[#71808C]">#{index + 1}</span>
                                <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase border ${typeBadgeStyle[actType] || 'bg-slate-100 text-slate-700'}`}>
                                  {actType.replace(/_/g, ' ')}
                                </span>
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize border ${
                                    diff === 'hard'
                                      ? 'bg-rose-50 text-rose-700 border-rose-200'
                                      : diff === 'medium'
                                      ? 'bg-amber-50 text-amber-700 border-amber-200'
                                      : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  }`}
                                >
                                  {diff}
                                </span>
                                {cfg.edited_by_teacher && (
                                  <span className="rounded bg-sky-50 border border-sky-200 px-1.5 py-0.2 text-3xs font-semibold text-sky-800">
                                    ✏️ Faculty Edited
                                  </span>
                                )}
                                {selectedNode.status === 'published' && (
                                  <span className="rounded bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 text-3xs font-semibold text-emerald-800 inline-flex items-center gap-1">
                                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-600" />
                                    Live to Students
                                  </span>
                                )}
                              </div>

                              {/* Action Buttons */}
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={() => startEditingActivity(act)}
                                  className="text-slate-400 hover:text-blue-600 p-1 transition"
                                  title="Edit practice question"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void deleteActivity(act.id)}
                                  className="text-slate-400 hover:text-rose-600 p-1 transition"
                                  title="Delete question"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>

                            {/* Question Prompt */}
                            <p className="text-sm font-semibold text-[#111111] leading-snug">
                              {payload.question || payload.template || ver?.title}
                            </p>

                            {/* Answer Display */}
                            {actType === 'mcq' && Array.isArray(payload.options) && (
                              <div className="grid gap-2 sm:grid-cols-2 pt-1">
                                {payload.options.map((opt: any) => {
                                  const isCorrect = opt.option_id === key.correct_option_id;
                                  return (
                                    <div
                                      key={opt.option_id}
                                      className={`rounded-xl border px-3 py-2 text-xs flex items-center justify-between ${
                                        isCorrect
                                          ? 'border-emerald-300 bg-emerald-50 text-emerald-900 font-semibold'
                                          : 'border-[#DCE7EE] bg-[#F8FAFC] text-[#4D5963]'
                                      }`}
                                    >
                                      <span className="truncate">{opt.text}</span>
                                      {isCorrect && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0 ml-1.5" />}
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {actType === 'true_false' && (
                              <div className="flex items-center gap-2 pt-0.5 text-2xs">
                                <span
                                  className={`rounded-lg border px-3 py-1 font-semibold ${
                                    key.correct_option_id === 'true'
                                      ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                                      : 'border-slate-200 bg-slate-50 text-slate-500'
                                  }`}
                                >
                                  True {key.correct_option_id === 'true' && '✓'}
                                </span>
                                <span
                                  className={`rounded-lg border px-3 py-1 font-semibold ${
                                    key.correct_option_id === 'false'
                                      ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                                      : 'border-slate-200 bg-slate-50 text-slate-500'
                                  }`}
                                >
                                  False {key.correct_option_id === 'false' && '✓'}
                                </span>
                              </div>
                            )}

                            {actType === 'fill_blank' && key.blanks && (
                              <div className="rounded-lg bg-amber-50/50 border border-amber-200/70 px-2.5 py-1 text-2xs space-y-0.5">
                                <span className="font-semibold text-amber-900">Accepted Blanks: </span>
                                <span className="font-mono text-amber-950 font-bold">
                                  {Object.values(key.blanks)
                                    .flatMap((b: any) => b.accepted_answers || [])
                                    .join(', ')}
                                </span>
                              </div>
                            )}

                            {actType === 'one_word' && key.accepted_answers && (
                              <div className="rounded-lg bg-purple-50/50 border border-purple-200/70 px-2.5 py-1 text-2xs space-y-0.5">
                                <span className="font-semibold text-purple-900">Keyword: </span>
                                <span className="font-mono text-purple-950 font-bold">
                                  {key.accepted_answers.join(', ')}
                                </span>
                              </div>
                            )}

                            {/* Collapsible Details Bar (Hint, Explanation, Slide Citation) */}
                            {(hint || explanation || citation) && (
                              <div className="pt-1">
                                <button
                                  type="button"
                                  onClick={() => toggleCardExpanded(act.id)}
                                  className="inline-flex items-center gap-1 text-3xs font-semibold text-slate-500 hover:text-blue-600 transition"
                                >
                                  {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                  {isExpanded ? 'Hide Details' : 'View Hints, Explanation & Citation'}
                                </button>

                                {isExpanded && (
                                  <div className="mt-2 rounded-lg bg-slate-50 p-2.5 space-y-1.5 text-2xs border border-slate-200/70">
                                    {hint && (
                                      <p className="text-amber-900 flex items-start gap-1">
                                        <Lightbulb className="h-3 w-3 text-amber-500 shrink-0 mt-0.5" />
                                        <span><strong>Hint:</strong> {hint}</span>
                                      </p>
                                    )}
                                    {explanation && (
                                      <p className="text-slate-700 leading-relaxed">
                                        <strong>Explanation:</strong> {explanation}
                                      </p>
                                    )}
                                    {citation && (
                                      <p className="text-blue-700 font-medium">
                                        📖 <strong>Reference:</strong> {citation}
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: DEDICATED AUTHORING WORKSPACE */}
              {activeTab === 'author' && (
                <div className="rounded-xl border border-slate-200/90 bg-white p-4 space-y-4 shadow-2xs">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Author Custom Practice Question</h3>
                    <p className="text-xs text-slate-500">
                      Evaluated on the backend with deterministic algorithms and 0 LLM tokens.
                    </p>
                  </div>

                  {/* Question Type Selector */}
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      ['mcq', 'Multiple Choice (MCQ)'],
                      ['true_false', 'True / False'],
                      ['fill_blank', 'Fill in Blank'],
                      ['one_word', 'One Word Answer'],
                    ].map(([typeVal, label]) => (
                      <button
                        key={typeVal}
                        type="button"
                        onClick={() => setAuthorType(typeVal as any)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-semibold border transition ${
                          authorType === typeVal
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>

                  {/* MCQ Form */}
                  {authorType === 'mcq' && (
                    <div className="space-y-3">
                      <input
                        value={mcqPrompt}
                        onChange={(e) => setMcqPrompt(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs"
                        placeholder="Question prompt, e.g. Which instrument records electrical brain activity from the scalp?"
                      />
                      <div className="grid gap-2 sm:grid-cols-2">
                        {[
                          { optId: 'opt_1' as const, val: optA, setter: setOptA, placeholder: 'Option A (required)' },
                          { optId: 'opt_2' as const, val: optB, setter: setOptB, placeholder: 'Option B (required)' },
                          { optId: 'opt_3' as const, val: optC, setter: setOptC, placeholder: 'Option C (optional)' },
                          { optId: 'opt_4' as const, val: optD, setter: setOptD, placeholder: 'Option D (optional)' },
                        ].map(({ optId, val, setter, placeholder }) => (
                          <div key={optId} className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="mcqCorrect"
                              checked={correctMcq === optId}
                              onChange={() => setCorrectMcq(optId)}
                            />
                            <input
                              value={val}
                              onChange={(e) => setter(e.target.value)}
                              className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                              placeholder={placeholder}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* True / False Form */}
                  {authorType === 'true_false' && (
                    <div className="space-y-3">
                      <input
                        value={tfPrompt}
                        onChange={(e) => setTfPrompt(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs"
                        placeholder="Statement, e.g. Non-invasive BCIs require surgical implantation inside the skull."
                      />
                      <div className="flex items-center gap-4 text-xs font-semibold">
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name="tfVal"
                            checked={tfValue === 'true'}
                            onChange={() => setTfValue('true')}
                          />
                          True is correct
                        </label>
                        <label className="flex items-center gap-1.5 cursor-pointer">
                          <input
                            type="radio"
                            name="tfVal"
                            checked={tfValue === 'false'}
                            onChange={() => setTfValue('false')}
                          />
                          False is correct
                        </label>
                      </div>
                    </div>
                  )}

                  {/* Fill in Blank Form */}
                  {authorType === 'fill_blank' && (
                    <div className="space-y-3">
                      <input
                        value={blankTemplate}
                        onChange={(e) => setBlankTemplate(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs"
                        placeholder="Sentence template with [blank_1], e.g. Brain activity is recorded via [blank_1]."
                      />
                      <input
                        value={blankAnswers}
                        onChange={(e) => setBlankAnswers(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-mono"
                        placeholder="Accepted answer(s) comma-separated, e.g. EEG, electroencephalography"
                      />
                    </div>
                  )}

                  {/* One Word Form */}
                  {authorType === 'one_word' && (
                    <div className="space-y-3">
                      <input
                        value={oneWordPrompt}
                        onChange={(e) => setOneWordPrompt(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs"
                        placeholder="Prompt, e.g. Name the 3-letter acronym for electroencephalography:"
                      />
                      <input
                        value={oneWordAnswers}
                        onChange={(e) => setOneWordAnswers(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-mono"
                        placeholder="Accepted keywords comma-separated, e.g. EEG, electroencephalography"
                      />
                    </div>
                  )}

                  {/* Additional Metadata Fields */}
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Difficulty</label>
                      <select
                        value={authorDifficulty}
                        onChange={(e) => setAuthorDifficulty(e.target.value as any)}
                        className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs"
                      >
                        <option value="easy">Easy (Foundational)</option>
                        <option value="medium">Medium (Conceptual)</option>
                        <option value="hard">Hard (Applied/Analytical)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-2xs font-semibold text-slate-600 mb-0.5">Slide Citation (optional)</label>
                      <input
                        value={authorCitation}
                        onChange={(e) => setAuthorCitation(e.target.value)}
                        className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                        placeholder="e.g. Module 1 PPT · Slide 4"
                      />
                    </div>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2">
                    <input
                      value={authorHint}
                      onChange={(e) => setAuthorHint(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                      placeholder="Remediation hint (shown to student if stuck)"
                    />
                    <input
                      value={authorExplanation}
                      onChange={(e) => setAuthorExplanation(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs"
                      placeholder="Post-answer explanation"
                    />
                  </div>

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setActiveTab('questions')}
                      className="text-xs h-8"
                    >
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      onClick={() => void createPractice()}
                      disabled={busy}
                      className="text-xs h-8 bg-blue-600 text-white"
                    >
                      <Save className="h-3.5 w-3.5 mr-1" />
                      Save Practice Question
                    </Button>
                  </div>
                </div>
              )}

              {/* TAB 3: TOPIC SETTINGS & OBJECTIVE */}
              {activeTab === 'settings' && (
                <div className="rounded-xl border border-slate-200/90 bg-white p-4 space-y-4 shadow-2xs">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">Topic Configuration</h3>
                    <p className="text-xs text-slate-500">
                      Configure topic title, learning objective description, and display sequence.
                    </p>
                  </div>

                  {editorConflict && (
                    <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" role="alert">
                      This topic was updated on the server. Unsaved edits were preserved.{' '}
                      <Button type="button" variant="outline" onClick={reloadLatestNode} className="text-xs ml-2">
                        Load latest version
                      </Button>
                    </div>
                  )}

                  <div className="space-y-3">
                    <div>
                      <label className="block text-2xs font-semibold text-slate-600 mb-1">Topic Title</label>
                      <input
                        disabled={selectedNode.status !== 'draft'}
                        value={title}
                        onChange={(e) => {
                          setTitle(e.target.value);
                          setEditorDirty(true);
                        }}
                        className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>

                    <div>
                      <label className="block text-2xs font-semibold text-slate-600 mb-1">
                        Learning Objective / Description
                      </label>
                      <textarea
                        disabled={selectedNode.status !== 'draft'}
                        value={description}
                        onChange={(e) => {
                          setDescription(e.target.value);
                          setEditorDirty(true);
                        }}
                        rows={4}
                        className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs disabled:bg-slate-50 disabled:text-slate-500"
                      />
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                      <label className="text-xs font-semibold text-slate-600 flex items-center gap-2">
                        Display Sequence:
                        <input
                          disabled={selectedNode.status !== 'draft'}
                          type="number"
                          min="1"
                          value={sequence}
                          onChange={(e) => {
                            setSequence(Number(e.target.value));
                            setEditorDirty(true);
                          }}
                          className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-xs"
                        />
                      </label>

                      <div className="flex items-center gap-2">
                        {selectedNode.status === 'draft' ? (
                          <>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => void saveNode()}
                              disabled={busy || editorConflict}
                              className="text-xs h-7.5"
                            >
                              <Save className="h-3.5 w-3.5 mr-1" />
                              Save Draft Edits
                            </Button>
                            <Button
                              type="button"
                              onClick={() => void publishCurrentNode()}
                              disabled={busy}
                              className="text-xs h-7.5 bg-emerald-600 text-white"
                            >
                              <Send className="h-3.5 w-3.5 mr-1" />
                              Publish Topic
                            </Button>
                          </>
                        ) : (
                          <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md px-2.5 py-1">
                            ✓ Published & Visible to Students
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500">
              <Layers className="h-10 w-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-semibold">No topic selected</p>
              <p className="text-xs text-slate-400 mt-1">Select a topic from the roadmap on the left to review its practice questions.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
