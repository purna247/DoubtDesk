import React, { useState } from 'react';
import {
  CheckCircle2,
  Clock,
  BookOpen,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react';
import type { StudentIntervention } from '../../types/interventions';
import type { CourseOffering } from '../../types/academics';

interface StudentSupportCardProps {
  intervention: StudentIntervention;
  onAction: (actionKind: string, intervention: StudentIntervention) => void;
  isLoadingAction?: boolean;
}

const formatOfferingLabel = (offering?: CourseOffering): string => {
  if (!offering) return 'Assigned Course';
  return [
    offering.official_subject_code,
    offering.subject_name,
    offering.section_code && `Sec ${offering.section_code}`,
  ]
    .filter(Boolean)
    .join(' · ');
};

export const StudentSupportCard: React.FC<StudentSupportCardProps> = ({
  intervention,
  onAction,
  isLoadingAction = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const nextAction = intervention.next_action;
  const isCompleted = intervention.current_phase === 'completed';

  // Step 1: Baseline
  const baselineDone = intervention.phase_a_completed;
  const baselineInProgress = intervention.baseline_attempt_state === 'in_progress';

  // Step 2: Study (Guide + Practice)
  const guideDone = intervention.phase_b_primer_acknowledged;
  const practiceDone = intervention.phase_b_completed;
  const studyDone = Boolean(baselineDone && guideDone && (!intervention.phase_b_practice_assessment_id || practiceDone));
  const studyInProgress = Boolean(baselineDone && !studyDone);

  // Step 3: Check Progress (Reassessment)
  const reassessDone = intervention.phase_c_completed;
  const reassessInProgress = intervention.reassessment_attempt_state === 'in_progress';
  const reassessUnlocked = intervention.phase_c_unlocked;

  const actionKind = nextAction?.action_kind || (
    !baselineDone
      ? (baselineInProgress ? 'resume_baseline' : 'start_baseline')
      : !guideDone
      ? 'open_guide'
      : intervention.phase_b_practice_assessment_id && !practiceDone
      ? (intervention.practice_attempt_state === 'in_progress' ? 'resume_practice' : 'start_practice')
      : !reassessDone
      ? (reassessInProgress ? 'resume_reassessment' : 'start_reassessment')
      : 'view_results'
  );

  const actionLabel = nextAction?.label || (
    actionKind === 'resume_baseline' ? 'Resume baseline' :
    actionKind === 'start_baseline' ? 'Start baseline' :
    actionKind === 'open_guide' ? 'Read study guide' :
    actionKind === 'acknowledge_guide' ? "I've reviewed the study guide" :
    actionKind === 'resume_practice' ? 'Resume practice' :
    actionKind === 'start_practice' ? 'Start practice' :
    actionKind === 'resume_reassessment' ? 'Resume reassessment' :
    actionKind === 'start_reassessment' ? 'Start reassessment' :
    actionKind === 'view_results' ? 'View results' : 'Continue support'
  );

  return (
    <article
      className={`rounded-2xl border transition-all ${
        isCompleted
          ? 'bg-slate-50/70 border-slate-200'
          : 'bg-white border-[#DCE7EE] shadow-sm hover:border-[#0A8FF5]/40'
      }`}
    >
      <div className="p-5 sm:p-6 space-y-4">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
                {formatOfferingLabel(intervention.offering)}
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EAF5FF] text-[#0A8FF5]">
                <Sparkles className="w-3 h-3 mr-1" /> Targeted Support
              </span>
            </div>
            <h4 className="text-base font-bold text-[#111111] leading-snug">
              {intervention.title}
            </h4>
            {intervention.description && (
              <p className="text-xs text-[#4D5963] line-clamp-2">
                {intervention.description}
              </p>
            )}
          </div>

          {/* Primary Action Button */}
          <div className="shrink-0 pt-1">
            <button
              type="button"
              disabled={isLoadingAction || actionKind === 'unavailable'}
              onClick={() => onAction(actionKind, intervention)}
              className={`text-xs px-5 py-2.5 rounded-xl font-bold transition flex items-center gap-1.5 shadow-sm cursor-pointer ${
                isCompleted
                  ? 'btn-outline text-slate-700'
                  : 'bg-[#0A8FF5] hover:bg-[#0980DC] text-white'
              }`}
            >
              <span>{isLoadingAction ? 'Loading...' : actionLabel}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* 3-Step Journey Indicator: Baseline → Study → Check progress */}
        <div className="grid grid-cols-3 gap-2 pt-2">
          {/* Step 1: Baseline */}
          <div
            className={`p-3 rounded-xl border text-xs space-y-1 transition ${
              baselineDone
                ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                : baselineInProgress
                ? 'bg-blue-50/60 border-blue-200 text-blue-900'
                : 'bg-slate-50 border-slate-200 text-slate-600'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span>1. Baseline</span>
              {baselineDone ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              ) : baselineInProgress ? (
                <Clock className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
              ) : null}
            </div>
            <p className="text-[11px] opacity-80">
              {baselineDone
                ? `Completed · ${intervention.phase_a_score ?? 0} pts`
                : baselineInProgress
                ? 'In progress (answers saved)'
                : 'Short diagnostic check'}
            </p>
          </div>

          {/* Step 2: Study */}
          <div
            className={`p-3 rounded-xl border text-xs space-y-1 transition ${
              studyDone
                ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                : studyInProgress
                ? 'bg-blue-50/60 border-blue-200 text-blue-900'
                : 'bg-slate-50 border-slate-200 text-slate-400'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span>2. Study</span>
              {studyDone ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              ) : studyInProgress ? (
                <BookOpen className="w-3.5 h-3.5 text-blue-600" />
              ) : null}
            </div>
            <p className="text-[11px] opacity-80">
              {studyDone
                ? 'Guide & practice complete'
                : studyInProgress
                ? guideDone
                  ? 'Guide reviewed'
                  : 'Review study guide'
                : 'Unlocks after baseline'}
            </p>
          </div>

          {/* Step 3: Check progress */}
          <div
            className={`p-3 rounded-xl border text-xs space-y-1 transition ${
              reassessDone
                ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                : reassessUnlocked
                ? 'bg-blue-50/60 border-blue-200 text-blue-900'
                : 'bg-slate-50 border-slate-200 text-slate-400'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span>3. Check progress</span>
              {reassessDone ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              ) : reassessInProgress ? (
                <Clock className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
              ) : null}
            </div>
            <p className="text-[11px] opacity-80">
              {reassessDone
                ? `Completed · ${intervention.phase_c_score ?? 0} pts`
                : reassessUnlocked
                ? 'Ready for reassessment'
                : 'Unlocks after study'}
            </p>
          </div>
        </div>

        {/* Expandable score history and details */}
        <div className="border-t border-slate-100 pt-2 flex items-center justify-between text-xs">
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-slate-500 hover:text-slate-800 font-semibold inline-flex items-center gap-1 cursor-pointer"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-3.5 h-3.5" /> Hide details
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5" /> View step details & scores
              </>
            )}
          </button>

          {isCompleted && intervention.observed_score_change !== null && intervention.observed_score_change !== undefined && (
            <span
              className={`font-black text-xs px-2.5 py-0.5 rounded-full ${
                intervention.observed_score_change > 0
                  ? 'bg-emerald-100 text-emerald-800'
                  : intervention.observed_score_change === 0
                  ? 'bg-slate-100 text-slate-700'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              Score change: {intervention.observed_score_change > 0 ? `+${intervention.observed_score_change}` : intervention.observed_score_change} pts
            </span>
          )}
        </div>

        {/* Expanded Panel */}
        {isExpanded && (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-3">
            <div className="grid sm:grid-cols-3 gap-3">
              <div>
                <span className="font-bold text-slate-700 block">Baseline check</span>
                <span className="text-slate-600">
                  {baselineDone ? `Score: ${intervention.phase_a_score ?? 0} pts` : 'Not submitted'}
                </span>
              </div>
              <div>
                <span className="font-bold text-slate-700 block">Study & Practice</span>
                <span className="text-slate-600">
                  {guideDone ? 'Guide acknowledged' : 'Guide pending'}
                  {intervention.phase_b_practice_assessment_id ? ` · ${intervention.phase_b_items_completed} items completed` : ' · No extra practice required'}
                </span>
              </div>
              <div>
                <span className="font-bold text-slate-700 block">Reassessment</span>
                <span className="text-slate-600">
                  {reassessDone ? `Score: ${intervention.phase_c_score ?? 0} pts` : 'Not submitted'}
                </span>
              </div>
            </div>

            {isCompleted && (
              <p className="text-[11px] text-slate-500 italic border-t border-slate-200 pt-2">
                Observed pre/post score change across matched student completions. Does not constitute causal evidence of mastery or intervention impact.
              </p>
            )}
          </div>
        )}
      </div>
    </article>
  );
};
