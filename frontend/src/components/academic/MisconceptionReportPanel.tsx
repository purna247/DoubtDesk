import React from 'react';
import type { MisconceptionReport } from '../../types/analytics';

interface MisconceptionReportPanelProps {
  report?: MisconceptionReport;
  isLoading: boolean;
  hasError: boolean;
}

export const MisconceptionReportPanel: React.FC<MisconceptionReportPanelProps> = ({ report, isLoading, hasError }) => (
  <section aria-labelledby="misconception-report-title" className="space-y-3 rounded-2xl border border-[#DCE7EE] bg-white p-6 shadow-xs">
    <div>
      <p className="text-xs font-bold uppercase tracking-wider text-[#0A8FF5]">Explicit response evidence</p>
      <h3 id="misconception-report-title" className="mt-1 text-base font-bold text-[#111111]">Misconception patterns</h3>
      <p className="mt-1 text-xs text-slate-500">Counts include submitted wrong answers linked to teacher-approved misconception tags.</p>
    </div>
    {isLoading ? (
      <div role="status" className="rounded-xl bg-[#F8FAFC] border border-[#E8EFF3] p-4 text-sm text-slate-500">
        Loading misconception evidence…
      </div>
    ) : hasError ? (
      <div role="alert" className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">
        Misconception evidence could not be loaded. Retry by changing courses or reopening Analytics.
      </div>
    ) : report?.misconceptions.length ? (
      <ul className="divide-y divide-[#E8EFF3]">
        {report.misconceptions.map((item) => (
          <li key={item.misconception_id} className="flex flex-wrap items-start justify-between gap-3 py-3.5 first:pt-0 last:pb-0">
            <div>
              <p className="text-sm font-semibold text-[#111111]">{item.concept_title || 'Course concept'} · {item.code}</p>
              <p className="mt-1 text-xs text-slate-600">{item.description}</p>
            </div>
            <span className="rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-semibold text-amber-800">
              {item.occurrence_count} {item.occurrence_count === 1 ? 'response' : 'responses'}
            </span>
          </li>
        ))}
      </ul>
    ) : (
      <p className="rounded-xl bg-[#F8FAFC] border border-[#E8EFF3] p-4 text-sm text-slate-500">
        No tagged misconception responses yet. A generic incorrect answer is not assigned a misconception.
      </p>
    )}
  </section>
);
