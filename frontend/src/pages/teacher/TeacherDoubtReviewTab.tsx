import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Loader2, MessageSquare } from 'lucide-react';
import { apiClient } from '../../api/client';

interface TeacherAnswer {
  id: string;
  body_markdown: string;
  is_teacher_verified: boolean;
  author?: { display_name?: string };
}

interface TeacherDoubt {
  id: string;
  title: string;
  body_markdown: string;
  concept_name?: string | null;
  author?: { display_name?: string; is_anonymous?: boolean };
  created_at: string;
  answers?: TeacherAnswer[];
}

export const TeacherDoubtReviewTab: React.FC = () => {
  const [doubts, setDoubts] = useState<TeacherDoubt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [busyAnswerId, setBusyAnswerId] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const loadDoubts = useCallback(async () => {
    try {
      const rows = await apiClient.get<TeacherDoubt[]>('/api/v1/doubts');
      setDoubts(Array.isArray(rows) ? rows : []);
      setError(false);
    } catch {
      setDoubts([]);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadDoubts(); }, [loadDoubts]);

  const verifyAnswer = async (answerId: string) => {
    setBusyAnswerId(answerId);
    try {
      await apiClient.post(`/api/v1/doubts/answers/${answerId}/verify`, {});
      await loadDoubts();
      setMessage('Answer verified.');
    } catch {
      setMessage('Could not verify this answer. Please try again.');
    } finally {
      setBusyAnswerId(null);
    }
  };

  return (
    <section className="space-y-4">
      <header>
        <p className="text-xs font-bold uppercase tracking-wide text-[#0A8FF5]">Faculty review</p>
        <h1 className="mt-1 text-2xl font-bold text-slate-900">Course doubt review</h1>
        <p className="mt-1 text-sm text-slate-600">Review student questions and verify answers in the current workspace.</p>
      </header>
      {message && <p role="status" className="rounded-xl bg-blue-50 px-4 py-3 text-sm text-blue-800">{message}</p>}
      {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500"><Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" />Loading course doubts…</div>
        : error ? <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">Course doubts could not be loaded. Refresh and try again.</div>
          : doubts.length ? <div className="space-y-4">{doubts.map((doubt) => <article key={doubt.id} className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-500">{doubt.author?.is_anonymous ? 'Anonymous Student' : doubt.author?.display_name || 'Student'} · {doubt.concept_name || 'Unmapped concept'}</span>
              <time className="text-xs text-slate-400">{new Date(doubt.created_at).toLocaleString()}</time>
            </div>
            <h2 className="mt-2 text-base font-bold text-slate-900">{doubt.title}</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{doubt.body_markdown}</p>
            <div className="mt-4 border-t border-slate-100 pt-3">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Answers ({doubt.answers?.length ?? 0})</h3>
              {doubt.answers?.length ? <div className="space-y-2">{doubt.answers.map((answer) => <div key={answer.id} className="rounded-xl border border-slate-200 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-700">{answer.author?.display_name || 'Community member'}</span>
                  {answer.is_teacher_verified ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />Verified</span> : <button onClick={() => verifyAnswer(answer.id)} disabled={busyAnswerId !== null} className="rounded-lg border border-emerald-200 px-3 py-1.5 text-xs font-semibold text-emerald-700 disabled:opacity-50">{busyAnswerId === answer.id ? 'Verifying…' : 'Verify answer'}</button>}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">{answer.body_markdown}</p>
              </div>)}</div> : <p className="flex items-center gap-2 text-sm text-slate-500"><MessageSquare className="h-4 w-4" />No answers have been submitted yet.</p>}
            </div>
          </article>)}</div> : <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center"><MessageSquare className="mx-auto mb-2 h-8 w-8 text-slate-300" /><p className="font-semibold text-slate-800">No course doubts yet</p><p className="mt-1 text-sm text-slate-500">Student questions will appear here when submitted.</p></div>}
    </section>
  );
};
