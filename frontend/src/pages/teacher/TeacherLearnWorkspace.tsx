import React, { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, Eye, Loader2, Save } from 'lucide-react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/Button';
import { useStartAcademicExtraction } from '../../hooks/useStartAcademicExtraction';
import { useTeacherLearningWorkspace } from '../../hooks/useTeacherLearningWorkspace';
import type { ReviewSummary } from '../../api/teacherLearningWorkspace';
import type { CourseOffering } from '../../types/academics';
import type { LearningNode } from '../../types/learning';

const EMPTY_SUMMARY: ReviewSummary = { run_status: 'waiting_for_documents', generation_status: 'waiting_for_documents', sources_ready: false, publish_ready: false, approved_syllabus_count: 0, has_warnings: false, warnings_count: 0, modules_count: 0, topics_count: 0, concepts_count: 0, approved_concepts_count: 0, questions_count: 0, draft_nodes_count: 0, approved_concepts: [], flagged_items: [] };

export const TeacherLearnWorkspace: React.FC<{ offerings: CourseOffering[] }> = ({ offerings }) => {
  const [offeringId, setOfferingId] = useState(offerings[0]?.id ?? '');
  const [selectedId, setSelectedId] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [sequence, setSequence] = useState(1);
  const [conceptId, setConceptId] = useState('');
  const [activityQuestion, setActivityQuestion] = useState('');
  const [optionA, setOptionA] = useState('');
  const [optionB, setOptionB] = useState('');
  const [correctOption, setCorrectOption] = useState<'opt_a' | 'opt_b'>('opt_b');
  const [activityVersionId, setActivityVersionId] = useState('');
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [editorDirty, setEditorDirty] = useState(false);
  const [editorConflict, setEditorConflict] = useState(false);
  const editorNodeId = useRef('');
  const editorBaseRevision = useRef<number | null>(null);
  const academicExtraction = useStartAcademicExtraction();
  const workspaceQuery = useTeacherLearningWorkspace(offeringId);
  const nodes = workspaceQuery.data?.nodes ?? [];
  const summary = workspaceQuery.data?.summary ?? EMPTY_SUMMARY;
  const loading = workspaceQuery.isLoading;

  useEffect(() => { if (!offerings.some((offering) => offering.id === offeringId)) setOfferingId(offerings[0]?.id ?? ''); }, [offerings, offeringId]);
  useEffect(() => {
    const rows = workspaceQuery.data?.nodes ?? [];
    setSelectedId((current) => rows.some((node) => node.id === current) ? current : rows[0]?.id ?? '');
  }, [workspaceQuery.data?.nodes]);

  const selectedNode = nodes.find((node) => node.id === selectedId);
  useEffect(() => {
    if (!selectedNode) return;
    if (editorNodeId.current !== selectedNode.id) {
      editorNodeId.current = selectedNode.id;
      editorBaseRevision.current = selectedNode.revision;
      setTitle(selectedNode.title); setDescription(selectedNode.description ?? '');
      setSequence(selectedNode.sequence_no); setConceptId(selectedNode.concept_ids[0] ?? '');
      setEditorDirty(false); setEditorConflict(false); setPreview(false);
      return;
    }
    if (selectedNode.revision !== editorBaseRevision.current) {
      if (editorDirty) { setEditorConflict(true); return; }
      editorBaseRevision.current = selectedNode.revision;
      setTitle(selectedNode.title); setDescription(selectedNode.description ?? '');
      setSequence(selectedNode.sequence_no); setConceptId(selectedNode.concept_ids[0] ?? '');
      setEditorConflict(false);
    }
  }, [selectedNode?.id, selectedNode?.revision, editorDirty]);

  const saveNode = async () => {
    if (!selectedNode || selectedNode.status !== 'draft' || editorConflict) return;
    setBusy(true);
    try {
      const saved = await apiClient.patch<LearningNode>(`/api/v1/learning-nodes/${selectedNode.id}`, { title: title.trim(), description: description.trim() || null, sequence_no: Number(sequence), expected_revision: selectedNode.revision });
      editorBaseRevision.current = saved.revision; setEditorDirty(false); setEditorConflict(false); setMessage('Draft saved.');
      await workspaceQuery.refetch();
    } catch { setEditorConflict(true); setMessage('This draft changed elsewhere. Your unsaved text is preserved; reload the latest version before saving.'); }
    finally { setBusy(false); }
  };

  const publishAll = async () => {
    if (busy || !offeringId || !summary.course_content_version_id || !summary.publish_ready || ['queued','running','retrying'].includes(summary.generation_status)) return;
    setBusy(true);
    try {
      await apiClient.post(`/api/v1/courses/${offeringId}/academic-review/publish-all`, {});
      await workspaceQuery.refetch(); setMessage('Validated course content and draft nodes are published. Flagged items remain hidden.');
    } catch { setMessage('Nothing validated is ready to publish yet. Check the flagged items and try again.'); }
    finally { setBusy(false); }
  };

  const startExtraction = async () => {
    if (!offeringId || !summary.sources_ready || academicExtraction.isPending) return;
    setMessage('');
    try {
      const job = await academicExtraction.mutateAsync(offeringId);
      setMessage(job.already_queued ? 'Roadmap generation is already queued for these materials.' : 'Roadmap generation queued. Completed nodes will appear as they are saved.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Academic extraction could not be queued. Check the material processing status.');
    }
  };

  const createPractice = async () => {
    if (!selectedNode || !activityQuestion.trim() || !optionA.trim() || !optionB.trim()) return;
    setBusy(true);
    try {
      const activity = await apiClient.post<{ latest_version?: { id: string } }>(`/api/v1/learning-nodes/${selectedNode.id}/activities`, { activity_type: 'mcq', title: activityQuestion.trim().slice(0, 255), instructions: 'Choose the best answer.', authoring_payload: { question: activityQuestion.trim(), options: [{ option_id: 'opt_a', text: optionA.trim() }, { option_id: 'opt_b', text: optionB.trim() }], correct_option_id: correctOption }, scoring_config: { max_marks: 1, partial_credit: false } });
      setActivityVersionId(activity.latest_version?.id ?? ''); setMessage('Practice item saved with its answer key stored by the backend.');
    } catch { setMessage('Practice item could not be saved.'); }
    finally { setBusy(false); }
  };

  const publishPractice = async () => {
    if (!selectedNode || selectedNode.status !== 'published' || !activityVersionId || !conceptId) return;
    setBusy(true);
    try {
      const assessment = await apiClient.post<{ id: string }>(`/api/v1/courses/${offeringId}/assessments`, { learning_node_id: selectedNode.id, assessment_type: 'node_practice', title: `${selectedNode.title} · Practice`, description: 'Teacher-approved structured practice for this learning node.', version: { items: [{ activity_version_id: activityVersionId, sequence_no: 1, marks_available: 1, concept_allocations: [{ concept_id: conceptId, marks_available: 1 }] }] } });
      await apiClient.post(`/api/v1/assessments/${assessment.id}/publish`, {}); setActivityVersionId(''); setActivityQuestion(''); setOptionA(''); setOptionB(''); setMessage('Practice assessment published for students.');
    } catch { setMessage('Practice could not be published. The node must be published and mapped to a concept.'); }
    finally { setBusy(false); }
  };

  const groupedNodes = useMemo(() => {
    const groups = new Map<string, LearningNode[]>();
    for (const node of nodes) {
      const moduleTitle = node.module_title || 'Other course nodes';
      groups.set(moduleTitle, [...(groups.get(moduleTitle) ?? []), node]);
    }
    return [...groups.entries()];
  }, [nodes]);

  const generationActive = ['queued','running','retrying'].includes(summary.generation_status);
  const canGenerateRoadmap = summary.sources_ready && ['ready','failed'].includes(summary.generation_status);
  const generationStatusMessage = summary.generation_status === 'queued'
    ? 'Roadmap generation is queued.'
    : summary.generation_status === 'retrying'
      ? (summary.generation_message || 'Roadmap generation is waiting to resume.')
      : `Generating${summary.generation_stage ? ` · ${summary.generation_stage.replace(/_/g,' ')}` : ''}.`;

  const selectNode = (nodeId: string) => {
    if (editorDirty && nodeId !== selectedId) {
      setMessage('Save the current node before switching to another one.');
      return;
    }
    setSelectedId(nodeId);
  };

  const reloadLatestNode = () => {
    setEditorDirty(false);
    setEditorConflict(false);
    void workspaceQuery.refetch();
  };

  return <div className="space-y-5">
    <header><p className="text-xs font-bold uppercase tracking-wide text-[#0A8FF5]">Faculty learning workspace</p><h1 className="mt-1 text-2xl font-bold text-slate-900">Course roadmap</h1><p className="mt-1 text-sm text-slate-600">Review the course extraction summary, resolve flagged items, then publish validated learning content.</p></header>
    <label className="block text-xs font-semibold text-slate-600">Assigned course<select value={offeringId} onChange={(event) => setOfferingId(event.target.value)} className="mt-1 block w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm">{offerings.map((offering) => <option key={offering.id} value={offering.id}>{[offering.official_subject_code, offering.subject_name, offering.section_code].filter(Boolean).join(' · ')}</option>)}</select></label>
    {workspaceQuery.isError && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800" role="alert">Course roadmap could not be loaded. <Button type="button" variant="outline" onClick={() => void workspaceQuery.refetch()}>Retry</Button></p>}
    {message && <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800" role="status">{message}</p>}
    <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-bold uppercase text-blue-600">Roadmap generation · {summary.generation_status.replace(/_/g,' ')}</p><h2 className="mt-1 text-lg font-bold">Course draft summary</h2><p className="mt-1 text-sm text-slate-600">AI-proposed content stays private until published. Low-confidence and invalid items remain flagged and hidden from students.</p></div><div className="flex flex-wrap gap-2">{canGenerateRoadmap && <Button type="button" onClick={() => void startExtraction()} disabled={busy || loading || academicExtraction.isPending}>{academicExtraction.isPending ? 'Queueing roadmap…' : summary.generation_status === 'failed' ? 'Retry roadmap generation' : 'Generate Learning Roadmap'}</Button>}<Button type="button" variant="outline" onClick={() => void publishAll()} disabled={busy || loading || !summary.publish_ready || generationActive}>{summary.publish_ready ? 'Publish all validated content' : 'Nothing ready to publish'}</Button></div></div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">{[['Modules',summary.modules_count],['Topics',summary.topics_count],['Approved concepts',summary.approved_concepts_count],['Questions',summary.questions_count],['Draft nodes',summary.draft_nodes_count]].map(([label,value])=><div key={label} className="rounded-xl bg-slate-50 p-3"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-bold">{value}</p></div>)}</div>
      {generationActive && <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800" role="status">{generationStatusMessage} {summary.draft_nodes_count} node(s) are saved so far. You can edit and save these nodes while generation continues.</p>}
      {summary.flagged_items.length > 0 ? <div className="space-y-2"><h3 className="font-semibold text-amber-800">Extraction diagnostics · {summary.flagged_items.length}</h3>{summary.flagged_items.map((batch)=><article key={batch.id} className="rounded-xl border border-amber-200 bg-amber-50 p-3"><p className="text-sm font-semibold">{batch.stage.replace(/_/g,' ')}{batch.item_count ? ` · ${batch.item_count} flagged item(s)` : ' · processing failure'}</p><p className="mt-1 text-xs text-amber-900">{batch.message}</p>{batch.item_count===0 && batch.source_chunk_count>0 && <p className="mt-1 text-xs text-slate-600">The failed analysis used {batch.source_chunk_count} source chunks; no extracted items were accepted.</p>}{batch.items.slice(0,5).map((item,index)=><p className="mt-1 text-xs text-slate-700" key={`${batch.id}-${index}`}>{item.kind}: {item.label}{item.confidence != null ? ` · confidence ${(item.confidence*100).toFixed(0)}%` : ''}</p>)}{batch.item_count>5 && <p className="mt-1 text-xs text-slate-500">and {batch.item_count-5} more flagged items</p>}</article>)}</div> : <p className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">No unresolved extraction warnings.</p>}
      {summary.generation_status === 'failed' && summary.generation_message && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800" role="alert">{summary.generation_message}</p>}
      {summary.course_content_version_id && !summary.publish_ready && !generationActive && summary.generation_status !== 'failed' && <p className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{summary.sources_ready ? 'Both materials are processed, but the roadmap has not been generated yet. Use Generate Learning Roadmap above.' : 'There are no approved syllabus items to publish. Upload and process both the syllabus and question paper for this course.'}</p>}
      {!summary.course_content_version_id && <p className="text-sm text-slate-500">Upload both a syllabus and a question paper in Course Studio to build a course draft.</p>}
    </section>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"><div className="flex items-center gap-2"><BookOpen className="h-5 w-5 text-blue-600"/><h2 className="font-bold">Roadmap nodes</h2></div>
        {loading ? <Loader2 className="h-5 w-5 animate-spin text-blue-600"/> : groupedNodes.length ? <div className="space-y-5">{groupedNodes.map(([moduleTitle,moduleNodes])=><section key={moduleTitle} className="space-y-2"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-500">{moduleTitle}</h3><ol className="space-y-2">{moduleNodes.map((node)=><li key={node.id}><button onClick={()=>selectNode(node.id)} className={`w-full rounded-xl border p-3 text-left ${selectedId===node.id?'border-blue-400 bg-blue-50':'border-slate-200'}`}><span className="block text-xs text-slate-500">{node.difficulty_rank ? `Difficulty ${node.difficulty_rank} · ` : ''}{node.status} · revision {node.revision}</span><span className="mt-1 block font-semibold text-slate-900">{node.title}</span></button></li>)}</ol></section>)}</div> : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">{generationActive ? `Roadmap generation is in progress. ${summary.draft_nodes_count} completed node(s) will appear here as soon as they are saved.` : summary.sources_ready ? 'No roadmap yet. Select Generate Learning Roadmap above to build it from the processed course materials.' : 'Process a course syllabus and question paper to generate the learning roadmap.'}</p>}
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">{selectedNode ? <><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase text-slate-500">{selectedNode.status} · revision {selectedNode.revision}</p><h2 className="mt-1 font-bold">{preview?'Student preview':'Edit learning node'}</h2></div><button onClick={()=>setPreview(v=>!v)} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold"><Eye className="h-4 w-4"/>{preview?'Edit':'Preview'}</button></div>
        {editorConflict && <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900" role="alert">This node changed on the server. Your unsaved edits are preserved and were not submitted. <Button type="button" variant="outline" onClick={reloadLatestNode}>Load latest version</Button></div>}
        {preview ? <article className="rounded-xl bg-slate-50 p-5"><p className="text-xs text-slate-500">Student preview · {selectedNode.status==='published'?'visible to students':'draft preview only'}</p><h3 className="mt-2 text-xl font-bold">{title}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{description||'No objective added.'}</p></article> : <><input disabled={selectedNode.status!=='draft'} value={title} onChange={(e)=>{setTitle(e.target.value);setEditorDirty(true);}} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"/><textarea disabled={selectedNode.status!=='draft'} value={description} onChange={(e)=>{setDescription(e.target.value);setEditorDirty(true);}} rows={7} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"/><label className="text-xs font-semibold text-slate-600">Sequence <input disabled={selectedNode.status!=='draft'} type="number" min="1" value={sequence} onChange={(e)=>{setSequence(Number(e.target.value));setEditorDirty(true);}} className="ml-2 w-24 rounded-lg border border-slate-200 px-2 py-1.5"/></label><div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={()=>void saveNode()} disabled={busy||editorConflict||selectedNode.status!=='draft'}><Save className="h-4 w-4"/>Save draft edit</Button></div></>}
        <div className="border-t border-slate-100 pt-4 space-y-3"><h3 className="font-bold">Structured practice</h3><input value={activityQuestion} onChange={(e)=>setActivityQuestion(e.target.value)} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Multiple-choice question"/><div className="grid gap-2 sm:grid-cols-2"><input value={optionA} onChange={(e)=>setOptionA(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Option A"/><input value={optionB} onChange={(e)=>setOptionB(e.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm" placeholder="Option B"/></div><div className="flex flex-wrap items-center gap-2"><select value={correctOption} onChange={(e)=>setCorrectOption(e.target.value as 'opt_a'|'opt_b')} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"><option value="opt_a">A is correct</option><option value="opt_b">B is correct</option></select><button onClick={()=>void createPractice()} disabled={busy||selectedNode.status!=='draft'||!activityQuestion.trim()||!optionA.trim()||!optionB.trim()} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold disabled:opacity-50">Save practice item</button>{activityVersionId&&<button onClick={()=>void publishPractice()} disabled={busy||selectedNode.status!=='published'} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">Publish practice paper</button>}</div></div>
      </> : <p className="rounded-xl bg-slate-50 p-8 text-sm text-slate-500">Select a node to review it.</p>}</section>
    </div>
  </div>;
};
