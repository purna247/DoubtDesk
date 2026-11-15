import React, { useEffect, useState } from 'react';
import { BarChart3, Check, Loader2, RefreshCw, TriangleAlert } from 'lucide-react';
import { apiClient } from '../../api/client';
import { MisconceptionReportPanel } from '../../components/academic/MisconceptionReportPanel';
import { useCourseMisconceptions } from '../../hooks/useCourseMisconceptions';
import type { CourseOffering } from '../../types/academics';
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

export const TeacherAnalyticsPage: React.FC<{ offerings: CourseOffering[] }> = ({ offerings }) => {
  const [offeringId, setOfferingId] = useState('');
  const [rows, setRows] = useState<ConceptAnalytics[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [detail, setDetail] = useState<ConceptDetail | null>(null);
  const [activeConceptId, setActiveConceptId] = useState<string | null>(null);
  const [selectedStudents, setSelectedStudents] = useState<string[]>([]);
  const [title, setTitle] = useState('');
  const [primer, setPrimer] = useState('');
  const [phaseAId, setPhaseAId] = useState('');
  const [phaseBId, setPhaseBId] = useState('');
  const [phaseCId, setPhaseCId] = useState('');
  const [report, setReport] = useState<InterventionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingIntervention, setSavingIntervention] = useState(false);
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

  const createIntervention = async () => {
    if (!offeringId || !activeConceptId || !selectedStudents.length || !phaseAId || !phaseBId || !phaseCId || !title.trim()) return;
    setSavingIntervention(true);
    try {
      const intervention = await apiClient.post<Intervention>(`/api/v1/courses/${offeringId}/interventions`, {
        title: title.trim(),
        description: 'Targeted support prepared from teacher-reviewed concept assessment evidence.',
        concept_ids: [activeConceptId],
        student_membership_ids: selectedStudents,
        phase_a_assessment_id: phaseAId,
        phase_b_practice_assessment_id: phaseBId,
        phase_b_primer_content: primer.trim() || null,
        phase_b_completion_rule: 'all_required_items',
        phase_c_assessment_id: phaseCId,
      });
      await apiClient.post(`/api/v1/courses/${offeringId}/interventions/${intervention.id}/publish`, {});
      const updated = await apiClient.get<Intervention[]>(`/api/v1/courses/${offeringId}/interventions`);
      setInterventions(Array.isArray(updated) ? updated : []);
      setTitle('');
      setPrimer('');
      setSelectedStudents([]);
      setMessage('Intervention approved and assigned. Phase A is a formal assessment; Phase C unlocks after all required Phase B items.');
    } catch {
      setMessage('Intervention could not be published. Confirm all assessment phases are configured and Phase A and Phase C use disjoint question sets.');
    } finally {
      setSavingIntervention(false);
    }
  };

  const loadReport = async (id: string) => {
    try {
      setReport(await apiClient.get<InterventionReport>(`/api/v1/courses/${offeringId}/interventions/${id}/report`));
    } catch {
      setMessage('Outcome report could not be loaded.');
    }
  };

  const offering = offerings.find((item) => item.id === offeringId);

  return (
    <section className="space-y-6">
      {/* Header filter & controls bar */}
      <header className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#E8EFF3]">
        <div>
          {offering && (
            <p className="text-xs font-semibold text-slate-700">
              {offering.subject_name || offering.official_subject_code} · Section {offering.section_code} · {offering.term_code || 'Current term'}
            </p>
          )}
        </div>
        <div className="flex gap-2">
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
        </div>
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
          <div className="grid grid-cols-[minmax(0,2fr)_repeat(4,minmax(80px,1fr))] gap-3 border-b border-[#E8EFF3] bg-[#F8FAFC] px-5 py-3.5 text-[11px] font-bold uppercase tracking-wider text-slate-500">
            <span>Concept / sample</span>
            <span>Accuracy</span>
            <span>Assessed</span>
            <span>Weakness</span>
            <span>Misconceptions</span>
          </div>
          {rows.map((item) => {
            const accuracy = item.cohort_pooled_accuracy ?? item.cohort_mean_accuracy;
            return (
              <article
                key={item.concept_id}
                className="grid grid-cols-[minmax(0,2fr)_repeat(4,minmax(80px,1fr))] items-center gap-3 border-b border-[#E8EFF3] px-5 py-4 last:border-0 hover:bg-slate-50/50 transition-colors"
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
                <span className="text-sm font-semibold text-slate-800">
                  {accuracy == null ? '—' : `${Math.round(accuracy * 100)}%`}
                </span>
                <span className="text-sm text-slate-600">
                  {item.assessed_count}/{item.enrolled_count}
                </span>
                <span
                  className={`inline-flex w-fit items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${
                    item.confirmed_weak_count
                      ? 'bg-amber-50 text-amber-800 border border-amber-200'
                      : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}
                >
                  {item.confirmed_weak_count > 0 && <TriangleAlert className="h-3.5 w-3.5" />}
                  {item.confirmed_weak_count} confirmed
                </span>
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
              Select affected students. The sample size and underlying scored question evidence are shown below.
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

          <div className="grid gap-4 md:grid-cols-2 pt-2">
            <label className="text-xs font-semibold text-slate-700">
              Intervention title
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1.5 block w-full rounded-xl border border-[#DCE7EE] bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
                placeholder="Targeted concept intervention"
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Phase A · Baseline pre-test
              <select
                value={phaseAId}
                onChange={(e) => setPhaseAId(e.target.value)}
                className="mt-1.5 block w-full rounded-xl border border-[#DCE7EE] bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
              >
                <option value="">Select diagnostic assessment</option>
                {assessments
                  .filter((a) => a.assessment_type === 'intervention_baseline')
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Phase B · Targeted practice
              <select
                value={phaseBId}
                onChange={(e) => setPhaseBId(e.target.value)}
                className="mt-1.5 block w-full rounded-xl border border-[#DCE7EE] bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
              >
                <option value="">Select practice assessment</option>
                {assessments
                  .filter((a) => a.assessment_type === 'intervention_practice')
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Phase C · Post-test
              <select
                value={phaseCId}
                onChange={(e) => setPhaseCId(e.target.value)}
                className="mt-1.5 block w-full rounded-xl border border-[#DCE7EE] bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
              >
                <option value="">Select comparable reassessment</option>
                {assessments
                  .filter((a) => a.assessment_type === 'intervention_post')
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700 md:col-span-2">
              Phase B · Teacher-approved explanation
              <textarea
                value={primer}
                onChange={(e) => setPrimer(e.target.value)}
                rows={3}
                className="mt-1.5 block w-full rounded-xl border border-[#DCE7EE] bg-white px-3.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#0A8FF5]"
                placeholder="Write the explanation or link the approved material students should study."
              />
            </label>
          </div>

          <p className="text-xs text-slate-500">
            Completion rule: all required practice items. Phase C is gated by completion, not by a passing score. The backend rejects overlapping Phase A and Phase C question sets.
          </p>

          <button
            onClick={() => void createIntervention()}
            disabled={savingIntervention || !selectedStudents.length || !phaseAId || !phaseBId || !phaseCId || !title.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 hover:bg-slate-800 transition cursor-pointer"
          >
            {savingIntervention ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Approve and assign ({selectedStudents.length})
          </button>
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
