import { useState } from 'react';
import { Check, Loader2, Plus, Sparkles, Trash2 } from 'lucide-react';
import { apiClient, ApiError } from '../../api/client';
import type { Assessment } from '../../types/assessments';

interface Question {
  statement: string;
  options: string[];
  correct_index: number;
  explanation?: string;
  marks: number;
  difficulty_level: string;
  cognitive_level: string;
  source_chunk_ids: string[];
  origin_type: string;
}
interface Draft {
  concept_id: string;
  title: string;
  study_guide: string;
  baseline: Question[];
  practice: Question[];
  reassessment: Question[];
  sources?: { source_chunk_id: string; filename: string; page?: number | null; slide?: number | null; text: string }[];
}
type QuestionSection = 'baseline' | 'practice' | 'reassessment';
const blankQuestion = (): Question => ({ statement: '', options: ['', '', '', ''], correct_index: 0,
  explanation: '', marks: 1, difficulty_level: 'medium', cognitive_level: 'understand', source_chunk_ids: [], origin_type: 'teacher_authored' });
const inputClass = 'w-full rounded-lg border border-[#DCE7EE] bg-white px-3 py-2 text-sm';

function validation(draft: Draft): string | null {
  if (draft.title.trim().length < 3) return 'Enter an intervention title of at least 3 characters.';
  if (!draft.study_guide.trim()) return 'Add a study guide explaining what students should review.';
  if (!draft.baseline.length || !draft.reassessment.length) return 'Add baseline and reassessment questions.';
  for (const q of [...draft.baseline, ...draft.practice, ...draft.reassessment]) {
    if (q.statement.trim().length < 3 || q.options.some((o) => !o.trim())) return 'Complete each question and its answer options.';
    if (new Set(q.options.map((o) => o.trim().toLowerCase())).size !== q.options.length) return 'Each answer option must be distinct.';
    if (!Number.isFinite(q.marks) || q.marks <= 0) return 'Each question needs positive marks.';
  }
  const profile = (questions: Question[]) => questions.map((q) => `${q.marks}:${q.difficulty_level}:${q.cognitive_level}`).sort().join('|');
  if (profile(draft.baseline) !== profile(draft.reassessment)) return 'Match baseline and reassessment question counts, marks, difficulty and cognitive levels.';
  const prompts = [...draft.baseline, ...draft.reassessment].map((q) => q.statement.toLowerCase().trim().replace(/\s+/g, ' '));
  if (new Set(prompts).size !== prompts.length) return 'Use different questions in the baseline and reassessment.';
  return null;
}

export function InterventionAuthoringPanel({ offeringId, conceptId, conceptName, studentIds, assessments, onAssigned }: {
  offeringId: string; conceptId: string; conceptName: string; studentIds: string[];
  assessments: Assessment[]; onAssigned: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<Draft>({ concept_id: conceptId, title: `${conceptName} support`.slice(0, 255), study_guide: '', baseline: [], practice: [], reassessment: [] });
  const [mode, setMode] = useState<'draft' | 'existing'>('draft');
  const [count, setCount] = useState(3);
  const [includePractice, setIncludePractice] = useState(false);
  const [ids, setIds] = useState({ baseline: '', practice: '', reassessment: '' });
  const [busy, setBusy] = useState<'generate' | 'save' | null>(null);
  const [message, setMessage] = useState('');
  const [assigned, setAssigned] = useState(false);
  const issue = mode === 'draft' ? validation(draft) : !ids.baseline || !ids.reassessment || draft.title.trim().length < 3 || !draft.study_guide.trim()
    ? 'Choose a baseline, a reassessment and add a study guide and title.' : null;
  const base = `/api/v1/courses/${offeringId}/interventions`;

  const generate = async () => {
    setBusy('generate'); setMessage('');
    try {
      const result = await apiClient.post<Draft>(`${base}/generate-draft`, { concept_id: conceptId, question_count: count, include_practice: includePractice });
      setDraft(result); setAssigned(false);
      setMessage('Draft ready. Review the guide, questions and correct answers before approving.');
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'Draft generation failed. Please retry.'); }
    finally { setBusy(null); }
  };
  const approve = async () => {
    if (issue || !studentIds.length || busy) return;
    setBusy('save'); setMessage('');
    try {
      if (mode === 'draft') {
        await apiClient.post(`${base}/approve-draft`, { ...draft, student_membership_ids: studentIds });
      } else {
        await apiClient.post(`${base}/approve-existing`, {
          title: draft.title.trim(), concept_ids: [conceptId], student_membership_ids: studentIds,
          phase_a_assessment_id: ids.baseline, phase_b_practice_assessment_id: ids.practice || null,
          phase_c_assessment_id: ids.reassessment, phase_b_primer_content: draft.study_guide.trim(),
          require_primer_acknowledgment: true,
        });
      }
      setAssigned(true);
      setMessage('Intervention approved and assigned. Students will complete the baseline, study guide and any practice before reassessment.');
      await onAssigned();
    } catch (error) { setMessage(error instanceof ApiError ? error.message : 'Could not assign the intervention. Please retry.'); }
    finally { setBusy(null); }
  };
  const editQuestion = (section: QuestionSection, index: number, update: Partial<Question>) => {
    setDraft((current) => ({ ...current, [section]: current[section].map((q, i) => i === index ? { ...q, ...update } : q) }));
    setAssigned(false);
  };
  const questionEditor = (section: QuestionSection, label: string) => (
    <section className="space-y-3 rounded-xl border border-[#DCE7EE] p-4">
      <h4 className="font-semibold text-slate-900">{label}</h4>
      {draft[section].map((q, index) => (
        <div key={index} className="space-y-3 rounded-lg bg-slate-50 p-3">
          <div className="flex items-center justify-between"><span className="text-xs font-semibold">Question {index + 1}</span>
            <button type="button" aria-label={`Remove ${section} question ${index + 1}`} onClick={() => setDraft({ ...draft, [section]: draft[section].filter((_, i) => i !== index) })}><Trash2 className="h-4 w-4 text-slate-500" /></button></div>
          <label className="block text-xs">Question text<textarea className={inputClass} value={q.statement} onChange={(e) => editQuestion(section, index, { statement: e.target.value })} /></label>
          <div className="grid gap-2 sm:grid-cols-2">{q.options.map((option, optionIndex) => (
            <label key={optionIndex} className="text-xs">Option {optionIndex + 1}<input className={inputClass} value={option} onChange={(e) => editQuestion(section, index, { options: q.options.map((o, i) => i === optionIndex ? e.target.value : o) })} /></label>
          ))}</div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs">Correct answer<select className={inputClass} value={q.correct_index} onChange={(e) => editQuestion(section, index, { correct_index: Number(e.target.value) })}>{q.options.map((_, i) => <option key={i} value={i}>Option {i + 1}</option>)}</select></label>
            <label className="text-xs">Marks<input className={inputClass} type="number" min={0.5} max={100} step={0.5} value={q.marks} onChange={(e) => editQuestion(section, index, { marks: Number(e.target.value) })} /></label>
            <label className="text-xs">Difficulty<select className={inputClass} value={q.difficulty_level} onChange={(e) => editQuestion(section, index, { difficulty_level: e.target.value })}>{['easy', 'medium', 'hard'].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label className="text-xs">Cognitive level<select className={inputClass} value={q.cognitive_level} onChange={(e) => editQuestion(section, index, { cognitive_level: e.target.value })}>{['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'].map((value) => <option key={value}>{value}</option>)}</select></label>
          </div>
          <label className="block text-xs">Answer explanation<textarea className={inputClass} value={q.explanation || ''} onChange={(e) => editQuestion(section, index, { explanation: e.target.value })} /></label>
          {!!q.source_chunk_ids.length && <div className="space-y-1 text-xs text-slate-500">{q.source_chunk_ids.map((id) => {
            const source = draft.sources?.find((s) => s.source_chunk_id === id);
            return source ? <details key={id}><summary className="cursor-pointer font-semibold">{source.filename}{source.slide != null ? ` · Slide ${source.slide}` : source.page != null ? ` · Page ${source.page}` : ''}</summary><p className="mt-1 whitespace-pre-wrap">{source.text}</p></details> : <p key={id}>Approved course reference</p>;
          })}</div>}
        </div>
      ))}
      <button type="button" disabled={draft[section].length >= 10} className="inline-flex items-center gap-1 text-sm font-semibold text-[#0A8FF5]" onClick={() => setDraft({ ...draft, [section]: [...draft[section], blankQuestion()] })}><Plus className="h-4 w-4" /> Add question</button>
    </section>
  );
  const assessmentSelect = (section: QuestionSection, label: string, type: string) => (
    <label className="block text-sm font-semibold">{label}
      <select aria-label={label} className={`${inputClass} mt-2`} value={ids[section]} onChange={(e) => { setIds({ ...ids, [section]: e.target.value }); setAssigned(false); }}>
        <option value="">{section === 'practice' ? 'No practice quiz' : 'Choose published assessment'}</option>
        {assessments.filter((a) => a.assessment_type === type && a.status === 'published').map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
      </select>
    </label>
  );

  return <fieldset disabled={!!busy || assigned} className="space-y-5 border-t border-slate-200 pt-5 disabled:opacity-75">
    <div><h3 className="text-lg font-bold text-slate-900">Prepare targeted support</h3><p className="mt-1 text-sm text-slate-500">Review and edit the whole intervention here, then approve it for {studentIds.length} selected student(s).</p></div>
    <div className="flex flex-wrap gap-2" aria-label="Authoring method">
      <button type="button" aria-pressed={mode === 'draft'} className={`rounded-lg px-3 py-2 text-sm ${mode === 'draft' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100'}`} onClick={() => { setMode('draft'); setAssigned(false); }}>Generate or write questions</button>
      <button type="button" aria-pressed={mode === 'existing'} className={`rounded-lg px-3 py-2 text-sm ${mode === 'existing' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100'}`} onClick={() => { setMode('existing'); setAssigned(false); }}>Use existing assessments</button>
    </div>
    {mode === 'draft' && <div className="flex flex-wrap items-end gap-3 rounded-xl bg-blue-50 p-4">
      <label className="text-xs font-semibold">Questions per quiz<select className={`${inputClass} mt-1`} value={count} onChange={(e) => setCount(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</select></label>
      <label className="flex items-center gap-2 py-2 text-sm"><input type="checkbox" checked={includePractice} onChange={(e) => setIncludePractice(e.target.checked)} /> Include practice quiz</label>
      <button type="button" disabled={!studentIds.length} onClick={() => void generate()} className="inline-flex items-center gap-2 rounded-lg bg-[#0A8FF5] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy === 'generate' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{draft.baseline.length ? 'Regenerate draft' : 'Generate intervention draft'}</button>
      <p className="w-full text-xs text-slate-600">Generation uses approved course material and student doubts. Regenerating replaces the draft below. You can also write questions manually.</p>
    </div>}
    <label className="block text-sm font-semibold">Intervention title<input maxLength={255} className={`${inputClass} mt-2`} value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
    {mode === 'draft' ? questionEditor('baseline', '1 · Before learning — baseline quiz') : assessmentSelect('baseline', '1 · Before learning — baseline quiz', 'intervention_baseline')}
    <section className="space-y-3 rounded-xl border border-[#DCE7EE] p-4">
      <h4 className="font-semibold text-slate-900">2 · Study and practise</h4>
      <label className="block text-sm font-semibold">Remedial study guide<textarea rows={9} className={`${inputClass} mt-2 font-normal`} value={draft.study_guide} onChange={(e) => setDraft({ ...draft, study_guide: e.target.value })} placeholder="Explain the concept, address misconceptions, and include a worked example or approved reading links." /></label>
      <p className="text-xs text-slate-500">Students acknowledge reviewing this guide before reassessment. Add practice when helpful; completion is required if you include it.</p>
      {mode === 'draft' ? questionEditor('practice', 'Practice quiz (optional)') : assessmentSelect('practice', 'Practice quiz (optional)', 'intervention_practice')}
    </section>
    {mode === 'draft' ? questionEditor('reassessment', '3 · Check progress — matched reassessment') : assessmentSelect('reassessment', '3 · Check progress — matched reassessment', 'intervention_post')}
    <p className={`text-sm ${issue ? 'text-amber-800' : 'text-emerald-700'}`}>{issue || (mode === 'draft' ? 'Quiz structure matches. Review the content and ensure questions assess comparable understanding.' : 'The server will check that your selected quizzes are comparable and use different questions.')}</p>
    {!studentIds.length && <p className="text-sm text-amber-800">Select students with confirmed weakness evidence to assign this intervention.</p>}
    <button type="button" onClick={() => void approve()} disabled={!!issue || !studentIds.length} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Approve and assign ({studentIds.length})</button>
    {message && <p role="status" className="text-sm text-slate-700">{message}</p>}
  </fieldset>;
}
