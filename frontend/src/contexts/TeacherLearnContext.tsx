import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';
import type { CourseOffering } from '../types/academics';
import type { LearningNode } from '../types/learning';
import type { ReviewSummary } from '../api/teacherLearningWorkspace';
import { useTeacherLearningWorkspace } from '../hooks/useTeacherLearningWorkspace';
import { useStartAcademicExtraction } from '../hooks/useStartAcademicExtraction';
import { apiClient } from '../api/client';

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

export interface TeacherLearnContextValue {
  offerings: CourseOffering[];
  offeringId: string;
  setOfferingId: (id: string) => void;
  currentOffering: CourseOffering | undefined;
  nodes: LearningNode[];
  groupedNodes: [string, LearningNode[]][];
  summary: ReviewSummary;
  selectedId: string;
  setSelectedId: (id: string) => void;
  selectedNode: LearningNode | undefined;
  selectNode: (id: string) => void;
  loading: boolean;
  isError: boolean;
  message: string;
  setMessage: (msg: string) => void;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  publishCurrentNode: () => Promise<void>;
  deleteCurrentNode: () => Promise<void>;
  publishAll: () => Promise<void>;
  startExtraction: () => Promise<void>;
  generateAllCoursePractice: () => Promise<void>;
  academicExtraction: ReturnType<typeof useStartAcademicExtraction>;
  canGenerateRoadmap: boolean;
  allNodesPublished: boolean;
  generationActive: boolean;
  isGeneratingAll: boolean;
  refetchWorkspace: () => Promise<any>;
}

const TeacherLearnContext = createContext<TeacherLearnContextValue | null>(null);

export const useTeacherLearn = () => {
  const context = useContext(TeacherLearnContext);
  if (!context) {
    throw new Error('useTeacherLearn must be used within a TeacherLearnProvider');
  }
  return context;
};

interface TeacherLearnProviderProps {
  children: React.ReactNode;
  offerings: CourseOffering[];
  selectedSubject?: string;
}

export const TeacherLearnProvider: React.FC<TeacherLearnProviderProps> = ({
  children,
  offerings,
  selectedSubject,
}) => {
  const [offeringId, setOfferingId] = useState(() => offerings[0]?.id ?? '');
  const [selectedId, setSelectedId] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);

  // Sync with selectedSubject from parent or route
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

  const academicExtraction = useStartAcademicExtraction();
  const workspaceQuery = useTeacherLearningWorkspace(offeringId);
  const nodes = workspaceQuery.data?.nodes ?? [];
  const summary = workspaceQuery.data?.summary ?? EMPTY_SUMMARY;
  const loading = workspaceQuery.isLoading;
  const isError = workspaceQuery.isError;

  // Auto-select first node if current selection is invalid
  useEffect(() => {
    const rows = workspaceQuery.data?.nodes ?? [];
    setSelectedId((current) => (rows.some((node) => node.id === current) ? current : rows[0]?.id ?? ''));
  }, [workspaceQuery.data?.nodes]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedId),
    [nodes, selectedId]
  );

  const selectNode = (id: string) => {
    setSelectedId(id);
  };

  const groupedNodes = useMemo(() => {
    const groups = new Map<string, LearningNode[]>();
    for (const node of nodes) {
      const moduleTitle = node.module_title || 'Other course topics';
      groups.set(moduleTitle, [...(groups.get(moduleTitle) ?? []), node]);
    }
    return [...groups.entries()];
  }, [nodes]);

  const canGenerateRoadmap =
    summary.sources_ready && ['not_started', 'ready', 'failed'].includes(summary.generation_status);
  const allNodesPublished = nodes.length > 0 && nodes.every((n) => n.status === 'published');
  const generationActive = ['queued', 'running', 'retrying'].includes(summary.generation_status);

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

  const deleteCurrentNode = async () => {
    if (!selectedNode || busy) return;
    setBusy(true);
    try {
      await apiClient.delete(`/api/v1/learning-nodes/${selectedNode.id}`);
      await workspaceQuery.refetch();
      setMessage(`Topic "${selectedNode.title}" was deleted.`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Could not delete topic.');
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

  const generateAllCoursePractice = async () => {
    if (!offeringId || isGeneratingAll || !nodes.length) return;
    setIsGeneratingAll(true);
    setMessage('');
    try {
      const res = await apiClient.post<{ total_questions: number; nodes_count: number }>(
        `/api/v1/courses/${offeringId}/generate-all-practice-questions`,
        {}
      );
      await workspaceQuery.refetch();
      setMessage(`Generated ${res.total_questions} practice questions across ${res.nodes_count} roadmap topics!`);
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : 'Course-wide practice generation failed.');
    } finally {
      setIsGeneratingAll(false);
    }
  };

  const value: TeacherLearnContextValue = {
    offerings,
    offeringId,
    setOfferingId,
    currentOffering,
    nodes,
    groupedNodes,
    summary,
    selectedId,
    setSelectedId,
    selectedNode,
    selectNode,
    loading,
    isError,
    message,
    setMessage,
    busy,
    setBusy,
    publishCurrentNode,
    deleteCurrentNode,
    publishAll,
    startExtraction,
    generateAllCoursePractice,
    academicExtraction,
    canGenerateRoadmap,
    allNodesPublished,
    generationActive,
    isGeneratingAll,
    refetchWorkspace: workspaceQuery.refetch,
  };

  return <TeacherLearnContext.Provider value={value}>{children}</TeacherLearnContext.Provider>;
};
