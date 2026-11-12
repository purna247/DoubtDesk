import React from 'react';
import type { MisconceptionReport } from '../../types/analytics';

interface MisconceptionReportPanelProps {
  report?: MisconceptionReport;
  isLoading: boolean;
  hasError: boolean;
}

export const MisconceptionReportPanel: React.FC<MisconceptionReportPanelProps> = ({ report, isLoading, hasError }) => (
  <section aria-labelledby="misconception-report-title" className="space-y-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
    <div>
      <p className="text-xs font-bold uppercase tracking-wide text-[var(--color-primary)]">Explicit response evidence</p>
      <h3 id="misconception-report-title" className="mt-1 text-lg font-bold">Misconception patterns</h3>
      <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Counts include submitted wrong answers linked to teacher-approved misconception tags.</p>
    </div>
    {isLoading ? <div role="status" className="rounded-xl bg-[var(--color-surface-soft)] p-4 text-sm text-[var(--color-text-secondary)]">Loading misconception evidence…</div>
      : hasError ? <div role="alert" className="rounded-xl bg-[var(--color-danger-soft)] p-4 text-sm text-[var(--color-danger)]">Misconception evidence could not be loaded. Retry by changing courses or reopening Analytics.</div>
        : report?.misconceptions.length ? <ul className="divide-y divide-[var(--color-border-light)]">{report.misconceptions.map((item) => <li key={item.misconception_id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0"><div><p className="text-sm font-semibold">{item.concept_title || 'Course concept'} · {item.code}</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{item.description}</p></div><span className="rounded-full bg-[var(--color-gold-soft)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">{item.occurrence_count} {item.occurrence_count === 1 ? 'response' : 'responses'}</span></li>)}</ul>
          : <p className="rounded-xl bg-[var(--color-surface-soft)] p-4 text-sm text-[var(--color-text-secondary)]">No tagged misconception responses yet. A generic incorrect answer is not assigned a misconception.</p>}
  </section>
);
