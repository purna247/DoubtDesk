import React, { useEffect, useState } from 'react';
import { AlertCircle, BarChart3, Check, Loader2, RefreshCw, TriangleAlert } from 'lucide-react';
import { apiClient } from '../../api/client';
import { MisconceptionReportPanel } from '../../components/academic/MisconceptionReportPanel';
import { useCourseMisconceptions } from '../../hooks/useCourseMisconceptions';
import type { CourseOffering } from '../../types/academics';
import { InterventionAuthoringPanel } from '../../components/academic/InterventionAuthoringPanel';
import type { Assessment } from '../../types/assessments';

interface ConceptAnalytics {
  concept_id: string;
  concept_code?: string | null;
  concept_name?: string | null;
  enrolled_count: number;
  assessed_count: number;
  confirmed_weak_count: number;
  candidate_weak_count: number;
  insufficient_evidence_count: number;
  cohort_mean_accuracy?: number | null;
  cohort_pooled_accuracy?: number | null;
  tagged_misconception_count: number;
  practice_attempt_count: number;
  practice_struggle_count: number;
  practice_hints_used: number;
  doubt_count: number;
  doubt_unanswered_count: number;
  triangulated_risk_level: 'critical' | 'moderate' | 'healthy' | 'insufficient_evidence';
  computed_at: string;
}

interface SupportingEvidence {
  assessment_title: string;
  attempt_number: number;
  marks_awarded: number;
  marks_available: number;
  submitted_at: string;
}

interface StudentEvidence {
  student_membership_id: string;
  student_name?: string | null;
  student_reg_number?: string | null;
  concept_id: string;
  distinct_question_count: number;
  awarded_marks: number;
  available_marks: number;
  accuracy?: number | null;
  diagnostic_status: string;
  supporting_evidence: SupportingEvidence[];
}

interface ConceptDetail {
  students: StudentEvidence[];
}

interface Intervention {
  id: string;
  title: string;
  status: string;
  assigned_students_count: number;
  target_concepts: { concept_id: string; canonical_name?: string | null }[];
}

interface InterventionReport {
  title: string;
  total_assigned_count: number;
  phase_a_completed_count: number;
  phase_b_completed_count: number;
  phase_c_completed_count: number;
  matched_completed_count: number;
  improved_count: number;
  unchanged_count: number;
  declined_count: number;
  incomplete_count: number;
  average_phase_a_score?: number | null;
  average_phase_c_score?: number | null;
  average_observed_change?: number | null;
  disclaimer: string;
}

export interface CreateAssessmentIntent {
  offeringId: string;
  conceptId?: string;
  conceptName?: string;
  assessmentType: 'intervention_baseline' | 'intervention_practice' | 'intervention_post';
  defaultTitle?: string;
}

export const TeacherAnalyticsPage: React.FC<{
  offerings: CourseOffering[];
  onCreateAssessment?: (intent: CreateAssessmentIntent) => void;
}> = ({ offerings }) => {
  const [offeringId, setOfferingId] = useState('');
  const [rows, setRows] = useState<ConceptAnalytics[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [activeConceptId, setActiveConceptId] = useState<string | null>(null);
  const [selectedStudents, setSelectedStudents] = useState<string[]>([]);
  const [report, setReport] = useState<InterventionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const {
    data: misconceptionReport,
    isLoading: misconceptionsLoading,
    isError: misconceptionsError,
    refetch: refetchMisconceptions,
  } = useCourseMisconceptions(offeringId);

  useEffect(() => {
    setOfferingId((current) => (offerings.some((row) => row.id === current) ? current : offerings[0]?.id || ''));
  }, [offerings]);

  const loadAnalytics = async (refresh = false) => {
    if (!offeringId) return;
    setLoading(true);
    try {
      const [data, courseAssessments, courseInterventions] = await Promise.all([
        apiClient.get<ConceptAnalytics[]>(`/api/v1/courses/${offeringId}/analytics/concepts${refresh ? '?refresh=true' : ''}`),
        apiClient.get<Assessment[]>(`/api/v1/courses/${offeringId}/assessments`),
        apiClient.get<Intervention[]>(`/api/v1/courses/${offeringId}/interventions`),
      ]);
      setRows(Array.isArray(data) ? data : []);
      setAssessments(Array.isArray(courseAssessments) ? courseAssessments : []);
      setInterventions(Array.isArray(courseInterventions) ? courseInterventions : []);
      setMessage('');
    } catch {
      setRows([]);
      setMessage('Course analytics or intervention data could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setDetail(null);
    setActiveConceptId(null);
    setSelectedStudents([]);
    setReport(null);
    void loadAnalytics();
  }, [offeringId]);

  const runAnalytics = async () => {
    if (!offeringId) return;
    setLoading(true);
    try {
      await apiClient.post(`/api/v1/courses/${offeringId}/analytics/runs`, {});
      await Promise.all([loadAnalytics(true), refetchMisconceptions()]);
      setMessage('Analytics recomputed from persisted scored attempts.');
    } catch {
      setMessage('Analytics run could not be completed.');
      setLoading(false);
    }
  };

  const inspectConcept = async (conceptId: string) => {
    setActiveConceptId(conceptId);
    setDetail(null);
    setSelectedStudents([]);
    setReport(null);
    try {
      setDetail(await apiClient.get<ConceptDetail>(`/api/v1/courses/${offeringId}/analytics/concepts/${conceptId}`));
    } catch {
      setMessage('Student evidence could not be loaded for this concept.');
    }
  };

  const toggleStudent = (id: string) =>
    setSelectedStudents((current) => (current.includes(id) ? current.filter((value) => value !== id) : [...current, id]));

  const loadReport = async (id: string) => {
    try {
      setReport(await apiClient.get<InterventionReport>(`/api/v1/courses/${offeringId}/interventions/${id}/report`));
    } catch {
      setMessage('Outcome report could not be loaded.');
    }
  };

  return (
    <section className="space-y-6">
      {/* Header filter & controls bar */}
      <header className="flex items-center justify-end gap-2">
        <select
          value={offeringId}
          onChange={(event) => setOfferingId(event.target.value)}
          className="rounded-xl border border-[#DCE7EE] bg-white px-3 py-2 text-xs font-medium focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
        >
          {offerings.map((item) => (
            <option key={item.id} value={item.id}>
              {[item.official_subject_code, item.subject_name, item.section_code].filter(Boolean).join(' · ')}
            </option>
          ))}
        </select>
        <button
          onClick={() => void runAnalytics()}
          disabled={!offeringId || loading}
          className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition disabled:opacity-50 cursor-pointer"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Recompute
        </button>
      </header>

      {message && (
        <p role="status" className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800">
          {message}
        </p>
      )}

      {/* Main Concept Analytics Table / Empty State */}
      {loading && !rows.length ? (
        <div className="border border-[#DCE7EE] rounded-2xl bg-white p-12 text-center text-sm text-slate-500 shadow-xs">
          <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-[#0A8FF5]" />
          Loading course analytics…
        </div>
      ) : rows.length ? (
        <div className="overflow-hidden rounded-2xl border border-[#DCE7EE] bg-white shadow-xs">
          <div className="grid grid-cols-[minmax(0,2fr)_minmax(120px,1fr)_minmax(90px,1fr)_minmax(110px,1fr)_minmax(100px,1fr)_minmax(80px,1fr)] gap-3 border-b border-[#E8EFF3] bg-[#F8FAFC] px-5 py-3.5 text-[11px] font-bold uppercase tracking-wider text-slate-500">
            <span>Concept / Scope</span>
            <span>Triangulated Risk</span>
            <span>Quiz Accuracy</span>
            <span>Practice Struggle</span>
            <span>Student Doubts</span>
            <span>Misconceptions</span>
          </div>
          {rows.map((item) => {
            const accuracy = item.cohort_pooled_accuracy ?? item.cohort_mean_accuracy;
            return (
              <article
                key={item.concept_id}
                className="grid grid-cols-[minmax(0,2fr)_minmax(120px,1fr)_minmax(90px,1fr)_minmax(110px,1fr)_minmax(100px,1fr)_minmax(80px,1fr)] items-center gap-3 border-b border-[#E8EFF3] px-5 py-4 last:border-0 hover:bg-slate-50/50 transition-colors"
              >
                <div className="min-w-0 overflow-hidden">
                  <button
                    onClick={() => void inspectConcept(item.concept_id)}
                    title={item.concept_name || item.concept_code || 'Unnamed concept'}
                    className="block w-full truncate text-left text-sm font-semibold text-[#0A8FF5] hover:underline cursor-pointer"
                  >
                    {item.concept_name || item.concept_code || 'Unnamed concept'} · Inspect evidence
                  </button>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {item.enrolled_count} enrolled · {item.insufficient_evidence_count} with insufficient evidence
                  </p>
                </div>

                <div>
                  {item.triangulated_risk_level === 'critical' ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                      <TriangleAlert className="h-3.5 w-3.5 text-rose-600" />
                      Critical Risk
                    </span>
                  ) : item.triangulated_risk_level === 'moderate' ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                      <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                      Moderate Risk
                    </span>
                  ) : item.triangulated_risk_level === 'healthy' ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                      Healthy
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold bg-slate-50 text-slate-600 border border-slate-200">
                      Insufficient Data
                    </span>
                  )}
                </div>

                <div>
                  <span className="text-sm font-semibold text-slate-800">
                    {accuracy == null ? '—' : `${Math.round(accuracy * 100)}%`}
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    {item.assessed_count} assessed · {item.confirmed_weak_count} weak
                  </span>
                </div>

                <div>
                  <span className={`text-sm font-semibold ${item.practice_struggle_count > 0 ? 'text-amber-700' : 'text-slate-700'}`}>
                    {item.practice_struggle_count} struggles
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    {item.practice_hints_used} hints · {item.practice_attempt_count} attempts
                  </span>
                </div>

                <div>
                  <span className={`text-sm font-semibold ${item.doubt_count > 0 ? 'text-indigo-700' : 'text-slate-700'}`}>
                    {item.doubt_count} doubts
                  </span>
                  <span className="block text-[11px] text-slate-500">
                    {item.doubt_unanswered_count > 0 ? `${item.doubt_unanswered_count} open` : 'all answered'}
                  </span>
                </div>

                <span className="text-sm font-medium text-slate-700">{item.tagged_misconception_count}</span>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="border border-[#DCE7EE] rounded-2xl bg-white p-12 text-center shadow-xs">
          <BarChart3 className="mx-auto mb-3 h-9 w-9 text-slate-300" />
          <h3 className="font-semibold text-slate-900 text-base">No analytics evidence yet</h3>
          <p className="mt-1.5 text-sm text-slate-500 max-w-md mx-auto">
            A recompute uses persisted scored student attempts and the configured course evidence threshold.
          </p>
        </div>
      )}

      {/* Misconception patterns card */}
      <MisconceptionReportPanel report={misconceptionReport} isLoading={misconceptionsLoading} hasError={misconceptionsError} />

      {/* Concept detail / Assessment evidence */}
      {detail && activeConceptId && (
        <section className="space-y-4 rounded-2xl border border-[#DCE7EE] bg-white p-6 shadow-xs">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-[#0A8FF5]">Assessment evidence</p>
            <h3 className="mt-1 text-lg font-bold text-slate-900">
              {rows.find((row) => row.concept_id === activeConceptId)?.concept_name || 'Selected concept'}
            </h3>
            <p className="mt-1 text-xs text-slate-500">
              Select students with confirmed weakness evidence. Students with insufficient evidence need more diagnostic assessment first.
            </p>
          </div>

          <div className="space-y-2">
            {detail.students.map((student) => (
              <label
                key={student.student_membership_id}
                className="flex cursor-pointer items-start gap-3 rounded-xl border border-[#E8EFF3] p-3.5 hover:bg-slate-50 transition-colors"
              >
                <input
                  type="checkbox"
                  disabled={student.diagnostic_status !== 'confirmed_weakness'}
                  checked={selectedStudents.includes(student.student_membership_id)}
                  onChange={() => toggleStudent(student.student_membership_id)}
                  className="mt-1 rounded accent-[#0A8FF5]"
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-slate-900">
                    {student.student_name || student.student_reg_number || 'Enrolled student'}
                  </span>
                  <span className="block text-xs text-slate-600 mt-0.5">
                    {student.diagnostic_status.replace(/_/g, ' ')} · {student.distinct_question_count} distinct questions ·{' '}
                    {student.awarded_marks}/{student.available_marks} marks ·{' '}
                    {student.accuracy == null ? 'no accuracy' : `${Math.round(student.accuracy * 100)}%`}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500">
                    {student.supporting_evidence.map((e) => `${e.assessment_title} ${e.marks_awarded}/${e.marks_available}`).join(' · ') ||
                      'No question evidence'}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <InterventionAuthoringPanel
            key={`${offeringId}:${activeConceptId}`}
            offeringId={offeringId}
            conceptId={activeConceptId}
            conceptName={rows.find((row) => row.concept_id === activeConceptId)?.concept_name || 'Selected concept'}
            studentIds={selectedStudents}
            assessments={assessments}
            onAssigned={async () => { await loadAnalytics(); setSelectedStudents([]); }}
          />
        </section>
      )}

      {/* Active and prior interventions */}
      {interventions.length > 0 && (
        <section className="space-y-3 rounded-2xl border border-[#DCE7EE] bg-white p-6 shadow-xs">
          <h3 className="font-bold text-slate-900">Active and prior interventions</h3>
          {interventions.map((item) => (
            <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#E8EFF3] p-3.5 hover:bg-slate-50 transition-colors">
              <div>
                <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {item.status} · {item.assigned_students_count} assigned
                </p>
              </div>
              <button
                onClick={() => void loadReport(item.id)}
                className="rounded-lg border border-[#DCE7EE] bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition cursor-pointer"
              >
                View outcome report
              </button>
            </div>
          ))}
        </section>
      )}

      {/* Outcome report */}
      {report && (
        <section className="rounded-2xl border border-blue-200 bg-blue-50/70 p-6 shadow-xs">
          <h3 className="font-bold text-blue-950">Observed outcome · {report.title}</h3>
          <p className="mt-2 text-sm text-blue-900">
            Assigned {report.total_assigned_count} · Baseline {report.phase_a_completed_count} · Practice {report.phase_b_completed_count} · Reassessment {report.phase_c_completed_count} · Matched {report.matched_completed_count}
          </p>
          <p className="mt-1 text-sm text-blue-900">
            Improved {report.improved_count} · No change {report.unchanged_count} · Declined {report.declined_count} · Incomplete {report.incomplete_count}
          </p>
          <p className="mt-1 text-sm font-medium text-blue-950">
            Matched mean marks: {report.average_phase_a_score ?? '—'} → {report.average_phase_c_score ?? '—'} (observed change {report.average_observed_change ?? '—'})
          </p>
          <p className="mt-3 text-xs text-blue-700">{report.disclaimer}</p>
        </section>
      )}
    </section>
  );
};
