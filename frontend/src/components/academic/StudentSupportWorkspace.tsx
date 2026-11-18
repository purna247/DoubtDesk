import React, { useState } from 'react';
import {
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  AlertCircle,
} from 'lucide-react';
import type { StudentIntervention } from '../../types/interventions';
import type { CourseOffering } from '../../types/academics';

interface StudentSupportWorkspaceProps {
  intervention: StudentIntervention;
  step: 'study' | 'results';
  onBack: () => void;
  onAcknowledgeGuide: (interventionId: string) => Promise<void>;
  onStartAssessment: (assessmentId: string, title: string, interventionContext: { interventionId: string; offeringId: string; step: string }) => void;
  isAcknowledging?: boolean;
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

// Safe markdown renderer for study guides (no raw dangerouslySetInnerHTML)
const SafeMarkdownContent: React.FC<{ content: string }> = ({ content }) => {
  const lines = content.split('\n');

  return (
    <div className="space-y-3 text-sm text-[#111111] leading-relaxed">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={idx} className="text-sm font-bold text-[#111111] mt-4 mb-1">
              {trimmed.replace(/^###\s+/, '')}
            </h4>
          );
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={idx} className="text-base font-bold text-[#111111] mt-5 mb-1.5 border-b border-slate-100 pb-1">
              {trimmed.replace(/^##\s+/, '')}
            </h3>
          );
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={idx} className="text-lg font-extrabold text-[#111111] mt-6 mb-2">
              {trimmed.replace(/^#\s+/, '')}
            </h2>
          );
        }
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <li key={idx} className="ml-5 list-disc text-xs sm:text-sm text-[#333333]">
              {renderFormattedText(trimmed.replace(/^[-*]\s+/, ''))}
            </li>
          );
        }
        return (
          <p key={idx} className="text-xs sm:text-sm text-[#333333]">
            {renderFormattedText(trimmed)}
          </p>
        );
      })}
    </div>
  );
};

function renderFormattedText(text: string): React.ReactNode {
  // Simple bold and code formatter
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-bold text-[#111111]">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="px-1.5 py-0.5 rounded bg-slate-100 text-[#0A8FF5] font-mono text-[12px]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export const StudentSupportWorkspace: React.FC<StudentSupportWorkspaceProps> = ({
  intervention,
  step,
  onBack,
  onAcknowledgeGuide,
  onStartAssessment,
  isAcknowledging = false,
}) => {
  const [guideError, setGuideError] = useState('');

  const isGuideAcknowledged = intervention.phase_b_primer_acknowledged;
  const hasPractice = Boolean(intervention.phase_b_practice_assessment_id);
  const isPracticeDone = intervention.phase_b_completed;
  const isReassessUnlocked = intervention.phase_c_unlocked;
  const isCompleted = intervention.current_phase === 'completed';

  const handleAcknowledge = async () => {
    setGuideError('');
    try {
      await onAcknowledgeGuide(intervention.intervention_id);
    } catch {
      setGuideError('Could not record acknowledgment. Please try again.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="border border-[#DCE7EE] rounded-2xl bg-white p-5 sm:p-6 space-y-3">
        <button
          type="button"
          onClick={onBack}
          className="text-xs font-bold text-[#0A8FF5] hover:underline inline-flex items-center gap-1.5 cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Quizzes
        </button>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5]">
              {formatOfferingLabel(intervention.offering)}
            </span>
            <h2 className="text-lg sm:text-xl font-bold text-[#111111]">
              {intervention.title}
            </h2>
            {intervention.description && (
              <p className="text-xs text-[#4D5963]">{intervention.description}</p>
            )}
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-[#EAF5FF] text-[#0A8FF5]">
            <Sparkles className="w-4 h-4" />
            <span>Targeted Support · Step 2: Study & Practice</span>
          </div>
        </div>
      </div>

      {step === 'results' ? (
        /* Results View */
        <div className="border border-[#DCE7EE] rounded-2xl bg-white p-6 sm:p-8 space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Support Journey Completed</h3>
            <p className="text-xs text-slate-500">
              You completed the diagnostic baseline, study guide, and reassessment check.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-4 max-w-lg mx-auto">
            <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-center space-y-1">
              <span className="text-xs font-semibold text-slate-500">Baseline Score</span>
              <div className="text-2xl font-black text-slate-800">
                {intervention.phase_a_score ?? 0} pts
              </div>
            </div>

            <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50 text-center space-y-1">
              <span className="text-xs font-semibold text-emerald-700">Reassessment Score</span>
              <div className="text-2xl font-black text-emerald-900">
                {intervention.phase_c_score ?? 0} pts
              </div>
            </div>
          </div>

          {intervention.observed_score_change !== null && intervention.observed_score_change !== undefined && (
            <div className="p-4 rounded-xl bg-blue-50 border border-blue-200 max-w-lg mx-auto text-center space-y-1">
              <span className="text-xs font-bold text-blue-900">
                Observed Score Change: {intervention.observed_score_change > 0 ? `+${intervention.observed_score_change}` : intervention.observed_score_change} pts
              </span>
              <p className="text-[11px] text-blue-700">
                Observed pre/post score change across matched student completions. Does not constitute causal evidence of mastery or intervention impact.
              </p>
            </div>
          )}

          <div className="flex justify-center pt-2">
            <button
              type="button"
              onClick={onBack}
              className="btn-primary text-xs px-6 py-2.5 cursor-pointer"
            >
              Return to Quizzes
            </button>
          </div>
        </div>
      ) : (
        /* Study Guide & Practice Workspace */
        <div className="space-y-6">
          {/* Study Guide Content Card */}
          <div className="border border-[#DCE7EE] rounded-2xl bg-white p-6 sm:p-8 space-y-5">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <BookOpen className="w-5 h-5 text-[#0A8FF5]" />
              <h3 className="text-base font-bold text-slate-900">Study Guide & Worked Examples</h3>
            </div>

            {intervention.phase_b_primer_content ? (
              <div data-testid="study-guide-content" className="prose-sm max-w-none">
                <SafeMarkdownContent content={intervention.phase_b_primer_content} />
              </div>
            ) : (
              <div className="p-6 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
                No study guide content is attached to this support activity.
              </div>
            )}

            {guideError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2 text-xs text-red-700">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{guideError}</span>
              </div>
            )}

            {/* Acknowledgment Action */}
            <div className="border-t border-slate-100 pt-4 flex flex-wrap items-center justify-between gap-3">
              {isGuideAcknowledged ? (
                <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>Study guide reviewed and acknowledged</span>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={isAcknowledging}
                  onClick={() => void handleAcknowledge()}
                  className="bg-[#0A8FF5] hover:bg-[#0980DC] text-white text-xs px-6 py-2.5 rounded-xl font-bold transition flex items-center gap-2 shadow-sm disabled:opacity-50 cursor-pointer"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{isAcknowledging ? 'Saving acknowledgment...' : "I've reviewed the study guide"}</span>
                </button>
              )}

              {/* Next step teaser */}
              <span className="text-xs text-slate-500">
                {hasPractice && !isPracticeDone
                  ? 'Next step: Practice questions'
                  : 'Next step: Check progress (Reassessment)'}
              </span>
            </div>
          </div>

          {/* Practice Section (If Attached) */}
          {hasPractice && isGuideAcknowledged && (
            <div className="border border-[#DCE7EE] rounded-2xl bg-white p-6 sm:p-8 space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-slate-900">Assigned Practice</h3>
                  <p className="text-xs text-slate-500">
                    {intervention.phase_b_rule_description}
                  </p>
                </div>
                {isPracticeDone && (
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Practice completed
                  </span>
                )}
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => {
                    if (intervention.phase_b_practice_assessment_id) {
                      onStartAssessment(
                        intervention.phase_b_practice_assessment_id,
                        `${intervention.title} · Practice`,
                        {
                          interventionId: intervention.intervention_id,
                          offeringId: intervention.offering?.id || '',
                          step: 'practice',
                        }
                      );
                    }
                  }}
                  className="btn-primary text-xs px-6 py-2.5 cursor-pointer inline-flex items-center gap-1.5"
                >
                  <span>{isPracticeDone ? 'Review Practice' : 'Start Practice'}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}

          {/* Reassessment Ready Banner */}
          {isReassessUnlocked && !isCompleted && (
            <div className="border border-blue-200 rounded-2xl bg-[#EAF5FF] p-6 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-blue-900">Ready to Check What You Learned</h4>
                <p className="text-xs text-blue-700">
                  You have completed the required study preparation. Take the progress check now.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (intervention.phase_c_assessment_id) {
                    onStartAssessment(
                      intervention.phase_c_assessment_id,
                      `${intervention.title} · Check Progress`,
                      {
                        interventionId: intervention.intervention_id,
                        offeringId: intervention.offering?.id || '',
                        step: 'reassessment',
                      }
                    );
                  }
                }}
                className="bg-[#0A8FF5] hover:bg-[#0980DC] text-white text-xs px-6 py-2.5 rounded-xl font-bold transition flex items-center gap-1.5 shadow-sm cursor-pointer"
              >
                <span>Start Reassessment</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
