import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileText, Loader2, UploadCloud } from 'lucide-react';
import { apiClient } from '../../api/client';
import type { CourseOffering } from '../../types/academics';

interface SourceDocument {
  id: string;
  original_filename: string;
  source_type: string;
  status: string;
  publication_status: 'pending_review' | 'published' | 'rejected';
  review_status: 'pending_review' | 'approved' | 'rejected';
  created_at: string;
}

interface LibraryMaterial extends SourceDocument {
  course_offering_id: string;
  job_id?: string | null;
  job_status?: string | null;
  job_stage?: string | null;
  job_progress_percent?: number | null;
  job_error_summary?: string | null;
}

interface SourceChunk {
  id: string;
  chunk_index: number;
  page_number?: number | null;
  section_path?: string | null;
  chunk_type: string;
  content_text: string;
}

interface Extraction {
  id: string;
  extractor_name?: string;
  status: string;
  warnings_json?: string[] | null;
  safe_error_summary?: string | null;
  chunks?: SourceChunk[] | null;
}

interface JobStatus {
  status: string;
  current_stage: string;
  progress_percent: number;
  attempt_count?: number;
  error_code?: string | null;
  safe_error_summary?: string | null;
  events?: { message_safe: string; stage_name?: string | null; progress_percent?: number | null; created_at: string }[];
}


export const TeacherMaterialsPage: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [offerings, setOfferings] = useState<CourseOffering[]>([]);
  const [offeringId, setOfferingId] = useState('');
  const [document, setDocument] = useState<SourceDocument | null>(null);
  const [materials, setMaterials] = useState<LibraryMaterial[]>([]);
  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<JobStatus | null>(null);
  const [jobQueuedAt, setJobQueuedAt] = useState<number | null>(null);
  const [queueWaitSeconds, setQueueWaitSeconds] = useState(0);
  const [extractions, setExtractions] = useState<Extraction[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [sourceType, setSourceType] = useState('lecture_notes');
  const [materialTypeFilter, setMaterialTypeFilter] = useState('all');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const chunks = useMemo(
    () => extractions.flatMap((extraction) => extraction.chunks ?? []),
    [extractions],
  );

  const loadMaterials = useCallback(async (selectedOfferingId = offeringId) => {
    if (!selectedOfferingId) { setMaterials([]); return; }
    try {
      const rows = await apiClient.get<LibraryMaterial[]>(`/api/v1/sources/teacher/materials?course_offering_id=${selectedOfferingId}`);
      setMaterials(Array.isArray(rows) ? rows : []);
    } catch { setMessage('The course material library could not be loaded.'); }
  }, [offeringId]);

  useEffect(() => {
    if (!offeringId) return;
    void loadMaterials(offeringId);
    const timer = setInterval(() => void loadMaterials(offeringId), 5000);
    return () => clearInterval(timer);
  }, [offeringId, loadMaterials]);
  useEffect(() => {
    apiClient.get<CourseOffering[]>('/api/v1/academics/teacher/offerings')
      .then((rows) => {
        setOfferings(Array.isArray(rows) ? rows : []);
        setOfferingId((current) => current || rows?.[0]?.id || '');
      })
      .catch(() => setMessage('Could not load your assigned course offerings.'));
  }, []);


  const refreshExtractions = async (documentId: string) => {
    const rows = await apiClient.get<Extraction[]>(`/api/v1/sources/${documentId}/extractions`);
    setExtractions(Array.isArray(rows) ? rows : []);
  };

  const uploadMaterial = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedFiles.length || !offeringId) return;
    setBusy(true);
    setMessage(`Uploading ${selectedFiles.length} file${selectedFiles.length === 1 ? '' : 's'}…`);
    setExtractions([]);
    try {
      const results = [];
      for (const file of selectedFiles) {
        const body = new FormData();
        body.append('file', file);
        body.append('source_type', sourceType);
        body.append('visibility', 'course');
        body.append('course_offering_id', offeringId);
        results.push(await apiClient.post<{ document: SourceDocument; job_id?: string | null; already_uploaded: boolean; message: string }>(
          '/api/v1/sources/upload', body,
        ));
      }
      const result = results[results.length - 1];
      setDocument(result.document);
      setJobId(result.job_id || '');
      setJob(null);
      setJobQueuedAt(Date.now());
      setQueueWaitSeconds(0);
      setMessage(`${results.length} file${results.length === 1 ? '' : 's'} uploaded or reused. Processing continues in the background.`);
      if (result.already_uploaded && result.document.status === 'processed') {
        await refreshExtractions(result.document.id);
      }
      setSelectedFiles([]);
      const input = window.document.querySelector<HTMLInputElement>('#teacher-material-file');
      if (input) input.value = '';
      await loadMaterials(offeringId);
    } catch {
      setMessage('Upload failed. Check the file and course assignment, then try again.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!jobId || !document) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const status = await apiClient.get<JobStatus>(`/api/v1/jobs/${jobId}`);
        if (cancelled) return;
        setJob(status);
        if (status.status === 'queued') {
          const queuedSeconds = jobQueuedAt === null ? 0 : Math.floor((Date.now() - jobQueuedAt) / 1000);
          setMessage(queuedSeconds >= 15
            ? 'Still queued: no backend worker has claimed this job yet. Check that the worker service is running.'
            : 'Upload is queued. Waiting for the backend worker to start preprocessing.');
        } else if (status.status === 'running') {
          setMessage(`Preprocessing is running: ${status.current_stage.replace(/_/g, ' ')} (${Math.round(status.progress_percent)}%).`);
        }
        if (['succeeded', 'completed', 'failed', 'dead_letter'].includes(status.status)) {
          if (status.status === 'succeeded' || status.status === 'completed') {
            await refreshExtractions(document.id);
            setMessage('Preprocessing complete.');
          } else {
            setMessage(status.safe_error_summary || 'Preprocessing failed.');
          }
          return;
        }
        timer = setTimeout(poll, 1800);
      } catch {
        if (!cancelled) setMessage('Could not retrieve preprocessing status.');
      }
    };
    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId, document?.id, jobQueuedAt]);

  useEffect(() => {
    if (jobQueuedAt === null) return;
    const intervalId = setInterval(() => {
      setQueueWaitSeconds(Math.floor((Date.now() - jobQueuedAt) / 1000));
    }, 1000);
    return () => clearInterval(intervalId);
  }, [jobQueuedAt]);

  const selectedOffering = offerings.find((offering) => offering.id === offeringId);
  const isProcessing = Boolean(job && !['succeeded', 'completed', 'failed', 'dead_letter'].includes(job.status));

  return (
    <div className={embedded ? 'contents' : 'space-y-5'}>
      <header className={embedded ? 'col-span-full' : undefined}>
        <p className="text-xs font-bold uppercase tracking-wide text-[#0A8FF5]">Faculty course studio</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Course materials</h1>
        <p className="mt-1 text-sm text-slate-600">Upload once and continue teaching. Successfully processed materials appear for enrolled students automatically.</p>
      </header>

      <div className={embedded ? 'contents' : 'grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-5 items-start'}>
        <div className="space-y-5 min-w-0">
          <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4">
            <h2 className="font-bold text-slate-900">Upload course material</h2>
            <label className="block text-xs font-semibold text-slate-600" htmlFor="teacher-material-course">Assigned course</label>
            <select id="teacher-material-course" value={offeringId} onChange={(event) => {
              setOfferingId(event.target.value); setDocument(null); setJobId(''); setJob(null); setExtractions([]);
            }} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm">
              <option value="">Choose an assigned course</option>
              {offerings.map((offering) => <option key={offering.id} value={offering.id}>
                {[offering.official_subject_code, offering.subject_name, offering.section_code].filter(Boolean).join(' · ')}
              </option>)}
            </select>
            <label className="block text-xs font-semibold text-slate-600" htmlFor="teacher-material-type">Material type</label>
            <select id="teacher-material-type" value={sourceType} onChange={(event) => {
              setSourceType(event.target.value);
              setDocument(null); setJobId(''); setJob(null); setJobQueuedAt(null);
              setExtractions([]); setMessage('');
            }} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm">
              <option value="lecture_notes">Lecture notes</option>
              <option value="slides">Lecture slides</option>
              <option value="lab_manual">Lab manual</option>
              <option value="syllabus">Syllabus</option>
              <option value="question_paper">Question paper / PYQ</option>
              <option value="reference_material">Reference material</option>
            </select>
            <form onSubmit={uploadMaterial} className="space-y-3">
              <input id="teacher-material-file" type="file" multiple accept=".pdf,.docx,.pptx,.txt,.md" onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))} className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:font-semibold" />
              {selectedFiles.length > 0 && <p className="text-xs text-slate-500">{selectedFiles.length} file{selectedFiles.length === 1 ? '' : 's'} selected: {selectedFiles.map((file) => file.name).join(', ')}</p>}
              <button type="submit" disabled={busy || !offeringId || !selectedFiles.length} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                Upload and preprocess
              </button>
            </form>
            <div className="border-t border-slate-100 pt-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-bold text-slate-900">Course material library</h3><select aria-label="Filter materials by type" value={materialTypeFilter} onChange={(event) => setMaterialTypeFilter(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs"><option value="all">All material types</option><option value="syllabus">Syllabus</option><option value="question_paper">Question papers / PYQs</option><option value="lecture_notes">Lecture notes</option><option value="slides">Slides</option><option value="lab_manual">Lab manuals</option><option value="reference_material">Reference material</option></select></div>
              {materials.filter((material) => materialTypeFilter === 'all' || material.source_type === materialTypeFilter).length ? <div className="space-y-2">{materials.filter((material) => materialTypeFilter === 'all' || material.source_type === materialTypeFilter).map((material) => <button key={material.id} onClick={() => { setDocument(material); setJobId(material.job_id || ''); setJob(material.job_status ? { status: material.job_status, current_stage: material.job_stage || material.job_status, progress_percent: material.job_progress_percent || 0, safe_error_summary: material.job_error_summary } : null); void refreshExtractions(material.id); }} className={`w-full rounded-xl border p-3 text-left ${document?.id === material.id ? 'border-blue-400 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}><div className="flex flex-wrap items-start justify-between gap-2"><span className="break-all text-sm font-semibold text-slate-900">{material.original_filename}</span><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${material.status === 'processed' ? 'bg-emerald-50 text-emerald-700' : material.status === 'failed' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-800'}`}>{material.status === 'processed' ? 'Ready for students' : (material.job_status || material.status).replace('_', ' ')}</span></div><div className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-slate-500"><span>{material.source_type.replace('_', ' ')}</span>{material.job_stage && <span>{material.job_stage.replace(/_/g, ' ')}</span>}{material.job_progress_percent !== null && material.job_progress_percent !== undefined && <span>{Math.round(material.job_progress_percent)}%</span>}</div>{material.job_error_summary && <p className="mt-1 text-xs text-rose-700">{material.job_error_summary}</p>}</button>)}</div> : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">No materials are recorded for this course yet.</p>}
            </div>
            {message && <p className="text-sm text-slate-600" role="status">{message}</p>}
            {job && <div className="space-y-1">
              <div className="flex justify-between text-xs text-slate-500"><span>{job.current_stage.replace(/_/g, ' ')}</span><span>{Math.round(job.progress_percent)}%</span></div>
              <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-[#0A8FF5]" style={{ width: `${Math.max(0, Math.min(100, job.progress_percent))}%` }} /></div>
              <p className="pt-1 text-[11px] text-slate-500">Job {jobId.slice(0, 8)} · attempt {job.attempt_count ?? 0}</p>
              {job.error_code && <p className="text-[11px] text-rose-700">Diagnostic code: {job.error_code}</p>}
              {job.events?.length ? <details className="pt-1"><summary className="cursor-pointer text-[11px] font-semibold text-slate-600">Processing event log ({job.events.length})</summary><ol className="mt-2 max-h-40 space-y-1 overflow-y-auto">{job.events.map((event, index) => <li key={`${event.created_at}-${index}`} className="text-[11px] leading-relaxed text-slate-500">{new Date(event.created_at).toLocaleTimeString()} · {event.stage_name?.replace(/_/g, ' ') || 'update'}{event.progress_percent != null ? ` · ${Math.round(event.progress_percent)}%` : ''} · {event.message_safe}</li>)}</ol></details> : null}
              {job.status === 'queued' && queueWaitSeconds >= 15 && <p className="mt-2 rounded-lg bg-amber-50 p-2.5 text-xs leading-relaxed text-amber-900">
                No worker has claimed this job yet. In local development run <code>python -m app.worker</code> from the backend, or start the Compose worker service.
              </p>}
              {job.status === 'failed' && job.safe_error_summary && <p role="alert" className="mt-2 rounded-lg bg-rose-50 p-2.5 text-xs text-rose-800">{job.safe_error_summary}</p>}
            </div>}
            {job && ['succeeded', 'completed'].includes(job.status) && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-900">Processing complete. This course material is now available to enrolled students.</p>}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
            <h2 className="font-bold text-slate-900">Processing status</h2>
            <p className="text-sm leading-relaxed text-slate-600">Text, tables, headings, and source references are processed in the background. Job progress and extraction diagnostics are available here; no teacher approval is needed for this uploaded file.</p>
            {chunks.length > 0 && <p className="text-xs text-slate-500">{chunks.length} extracted source blocks are available in the Preprocessor result panel.</p>}
          </section>
        </div>

        <aside className="rounded-2xl border border-slate-200 bg-white p-5 xl:sticky xl:top-5 max-h-[calc(100vh-2.5rem)] overflow-y-auto">
          <div className="flex items-start gap-3 mb-4">
            <span className="rounded-xl bg-blue-50 p-2 text-blue-600"><FileText className="h-5 w-5" /></span>
            <div><h2 className="font-bold text-slate-900">Processing details</h2><p className="mt-1 text-xs text-slate-500">Optional diagnostics for teachers and developers.</p></div>
          </div>
          {document ? <div className="mb-4 rounded-xl bg-slate-50 p-3 text-xs">
            <p className="font-semibold text-slate-800 break-words">{document.original_filename}</p>
            <p className="mt-1 text-slate-500">{job?.status || document.status}{selectedOffering ? ` · ${selectedOffering.subject_name || selectedOffering.official_subject_code}` : ''}</p>
            {document.status === 'processed' && <p className="mt-2 text-[11px] text-emerald-700">Available to enrolled students.</p>}
          </div> : <p className="mb-4 rounded-xl bg-slate-50 p-4 text-xs text-slate-500">Upload a document to see its extraction here.</p>}
          {isProcessing && <p className={`mb-3 flex items-center gap-2 text-xs ${job?.status === 'queued' ? 'text-amber-700' : 'text-blue-600'}`}>
            <Loader2 className="h-4 w-4 animate-spin" />
            {job?.status === 'queued' ? `Queued for ${queueWaitSeconds}s · waiting for a worker` : `Preprocessing · ${job?.current_stage.replace(/_/g, ' ')}`}
          </p>}
          {extractions.map((extraction) => <div key={extraction.id} className="mb-4">
            <div className="mb-2 flex items-center justify-between text-xs"><span className="font-semibold text-slate-700">{extraction.extractor_name} · {extraction.status}</span><span className="text-slate-400">{extraction.chunks?.length ?? 0} text blocks</span></div>
            {extraction.safe_error_summary && <p className="mb-2 rounded-lg bg-rose-50 p-2 text-xs text-rose-700">{extraction.safe_error_summary}</p>}
            {extraction.warnings_json?.map((warning, index) => <p key={`${extraction.id}-warning-${index}`} className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">{warning}</p>)}
          </div>)}
          {chunks.length ? <div className="space-y-3">{chunks.map((chunk) => <article key={chunk.id} className="rounded-xl border border-slate-200 p-3">
            <div className="mb-1 flex items-center justify-between gap-2"><h3 className="text-xs font-bold text-slate-800 truncate">{chunk.section_path || `Extracted section ${chunk.chunk_index + 1}`}</h3><span className="shrink-0 text-[10px] text-slate-400">{chunk.page_number ? `p. ${chunk.page_number}` : chunk.chunk_type}</span></div>
            <p className="text-xs leading-relaxed text-slate-600 whitespace-pre-wrap line-clamp-8">{chunk.content_text}</p>
          </article>)}</div> : document && ['succeeded', 'completed'].includes(job?.status ?? '') && <p className="text-xs text-slate-500">Preprocessing finished, but this document produced no text sections.</p>}
        </aside>
      </div>
    </div>
  );
};
