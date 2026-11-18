import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BookOpen,
  ArrowRight,
  Sparkles,
  RefreshCw,
  AlertCircle,
  FileText,
} from 'lucide-react';
import type { StudentProgressSummaryResponse } from '../../types/interventions';

interface StudentLearningProgressSidebarProps {
  summary: StudentProgressSummaryResponse | null;
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  selectedSubject?: string;
  isCompact?: boolean;
}

export const StudentLearningProgressSidebar: React.FC<StudentLearningProgressSidebarProps> = ({
  summary,
  isLoading,
  error,
  onRetry,
  selectedSubject = 'all',
  isCompact = false,
}) => {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <aside className={`space-y-4 ${isCompact ? 'w-full mb-4' : 'w-full'}`}>
        <div className="bg-white border border-[#DCE7EE] rounded-2xl p-5 text-center space-y-2">
          <RefreshCw className="w-5 h-5 text-[#0A8FF5] animate-spin mx-auto" />
          <p className="text-xs font-semibold text-slate-500">Loading learning progress...</p>
        </div>
      </aside>
    );
  }

  if (error || !summary) {
    return (
      <aside className={`space-y-4 ${isCompact ? 'w-full mb-4' : 'w-full'}`}>
        <div className="bg-white border border-rose-200 rounded-2xl p-5 text-center space-y-2">
          <AlertCircle className="w-5 h-5 text-rose-500 mx-auto" />
          <p className="text-xs font-semibold text-rose-700">
            {error || 'Could not load learning progress'}
          </p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="text-xs font-bold text-[#0A8FF5] hover:underline cursor-pointer"
            >
              Retry loading progress
            </button>
          )}
        </div>
      </aside>
    );
  }

  const { learning_topics, teacher_material_practice, remaining_support, continue_learning } = summary;

  return (
    <aside className={`space-y-4 ${isCompact ? 'w-full mb-4' : 'w-full'}`}>
      {/* 1. Continue Learning Card */}
      {continue_learning && continue_learning.action_kind !== 'all_caught_up' && (
        <div className="bg-gradient-to-br from-[#0A8FF5] to-[#0770C5] text-white rounded-2xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider bg-white/20 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> Continue Learning
            </span>
            {continue_learning.course_name && (
              <span className="text-[11px] font-semibold text-blue-100 truncate max-w-[130px]">
                {continue_learning.course_name}
              </span>
            )}
          </div>

          <div>
            <h4 className="text-sm font-bold leading-snug line-clamp-2">
              {continue_learning.title}
            </h4>
            {continue_learning.concept_name && (
              <p className="text-[11px] text-blue-100 mt-0.5 truncate">
                {continue_learning.concept_name}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={() => navigate(continue_learning.destination_url)}
            className="w-full bg-white text-[#0A8FF5] hover:bg-blue-50 py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-sm cursor-pointer"
          >
            <span>{continue_learning.action_label}</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Learning Topics Progress Card */}
      <div className="bg-white border border-[#DCE7EE] rounded-2xl p-5 space-y-3 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-[#0A8FF5]" />
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Learning Topics
            </h4>
          </div>
          {learning_topics.status === 'available' && (
            <span className="text-xs font-black text-slate-800">
              {learning_topics.completed_count} / {learning_topics.eligible_count}
            </span>
          )}
        </div>

        {learning_topics.status === 'available' ? (
          <div className="space-y-1.5">
            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-[#0A8FF5] rounded-full transition-all duration-500"
                style={{ width: `${learning_topics.percentage ?? 0}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500">
              <span>Roadmap progress</span>
              <span className="font-bold text-slate-700">{learning_topics.percentage ?? 0}%</span>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500 text-center">
            {learning_topics.reason || 'No published learning topics found.'}
          </div>
        )}

        <button
          type="button"
          onClick={() => {
            const subjectParam = selectedSubject !== 'all' ? `?subject=${selectedSubject}` : '';
            navigate(`/courses${subjectParam}`);
          }}
          className="w-full btn-outline text-xs py-2 rounded-xl font-bold cursor-pointer inline-flex items-center justify-center gap-1"
        >
          <span>View learning roadmap</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      {/* 3. Teacher-Material Practice Card */}
      <div className="bg-white border border-[#DCE7EE] rounded-2xl p-5 space-y-3 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#0A8FF5]" />
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Teacher Practice Questions
            </h4>
          </div>
          {teacher_material_practice.status === 'available' && (
            <span className="text-xs font-black text-slate-800">
              {teacher_material_practice.attempted_count} / {teacher_material_practice.eligible_count}
            </span>
          )}
        </div>

        {teacher_material_practice.status === 'available' ? (
          <div className="space-y-1.5">
            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${teacher_material_practice.percentage ?? 0}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-500">
              <span>Attempted coverage</span>
              <span className="font-bold text-emerald-700">{teacher_material_practice.percentage ?? 0}%</span>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500 text-center">
            {teacher_material_practice.reason || 'Not tracked / No published question bank'}
          </div>
        )}

        <button
          type="button"
          onClick={() => {
            const subjectParam = selectedSubject !== 'all' ? `?subject=${selectedSubject}` : '';
            navigate(`/courses${subjectParam}`);
          }}
          className="w-full btn-outline text-xs py-2 rounded-xl font-bold cursor-pointer inline-flex items-center justify-center gap-1"
        >
          <span>Practise questions</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>

      {/* 4. Support Remaining Card */}
      <div className="bg-white border border-[#DCE7EE] rounded-2xl p-5 space-y-2 shadow-sm">
        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
          Targeted Learning Support
        </h4>
        <div className="grid grid-cols-2 gap-2 text-center pt-1">
          <div className="p-2.5 rounded-xl bg-blue-50/70 border border-blue-100">
            <span className="text-lg font-black text-[#0A8FF5] block">
              {remaining_support.active_count}
            </span>
            <span className="text-[10px] font-bold text-blue-900 uppercase">Active</span>
          </div>
          <div className="p-2.5 rounded-xl bg-emerald-50/70 border border-emerald-100">
            <span className="text-lg font-black text-emerald-600 block">
              {remaining_support.completed_count}
            </span>
            <span className="text-[10px] font-bold text-emerald-900 uppercase">Completed</span>
          </div>
        </div>
      </div>
    </aside>
  );
};
