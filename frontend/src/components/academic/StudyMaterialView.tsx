import React, { useEffect, useMemo, useState } from 'react';
import { Download, FileText, Filter, HelpCircle, Loader2 } from 'lucide-react';
import { ApiError, API_BASE_URL, apiClient } from '../../api/client';
import type { CourseOffering } from '../../types/academics';
import { useAuth } from '../../contexts/AuthContext';

interface StudyMaterial {
  id: string;
  course_offering_id: string;
  original_filename: string;
  source_type: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  subject_code?: string | null;
  subject_name?: string | null;
  section_code?: string | null;
}

interface StudyMaterialViewProps {
  selectedSubject?: string;
  offerings: CourseOffering[];
}

const materialLabels: Record<string, string> = {
  syllabus: 'Syllabus',
  lecture_notes: 'Lecture notes',
  slides: 'Lecture slides',
  lab_manual: 'Lab manual',
  question_paper: 'Question paper',
  reference_material: 'Reference material',
};

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const StudyMaterialView: React.FC<StudyMaterialViewProps> = ({
  selectedSubject = 'all',
  offerings,
}) => {
  const { role } = useAuth();
  const [materials, setMaterials] = useState<StudyMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (role !== 'STUDENT') return;
    let cancelled = false;
    setLoading(true);
    setError('');
    apiClient.get<StudyMaterial[]>('/api/v1/sources/student/materials')
      .then((rows) => {
        if (!cancelled) setMaterials(Array.isArray(rows) ? rows : []);
      })
      .catch((reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof ApiError && reason.status === 404
          ? 'The backend is running an older version. Restart the API, then retry loading study materials.'
          : reason instanceof ApiError && reason.status === 403
            ? 'Your account does not have access to student study materials.'
            : 'Study materials could not be loaded. Please retry.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [reloadKey, role]);

  const activeOfferings = useMemo(
    () => selectedSubject === 'all'
      ? offerings
      : offerings.filter((offering) => offering.curriculum_subject_entry_id === selectedSubject),
    [offerings, selectedSubject],
  );
  const visibleOfferingIds = new Set(activeOfferings.map((offering) => offering.id));
  const visibleMaterials = materials.filter((material) => visibleOfferingIds.has(material.course_offering_id));
  const activeSubjectLabel = selectedSubject === 'all' ? '' : (
    activeOfferings[0]?.subject_name || activeOfferings[0]?.official_subject_code || 'Selected subject'
  );

  return (
    <div className="space-y-6">
      {activeSubjectLabel && (
        <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#EAF5FF] border border-[#B8D9F5]">
          <Filter className="w-3.5 h-3.5 text-[#0A8FF5] shrink-0" />
          <span className="text-xs font-semibold text-[#0A8FF5]">Filtered by subject:</span>
          <span className="text-xs font-bold text-[#111111]">{activeSubjectLabel}</span>
        </div>
      )}

      {loading ? (
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-10 text-center text-sm text-[#71808C]">
          <Loader2 className="w-5 h-5 animate-spin mx-auto mb-3" />
          Loading study materials...
        </div>
      ) : error ? (
        <div role="alert" className="border border-rose-200 rounded-[16px] bg-white p-8 text-center text-sm text-rose-700">
          {error}
          <div><button onClick={() => setReloadKey((key) => key + 1)} className="mt-4 rounded-lg border border-rose-200 px-4 py-2 text-xs font-semibold hover:bg-rose-50">Retry</button></div>
        </div>
      ) : visibleMaterials.length ? (
        <div className="space-y-3">
          {visibleMaterials.map((material) => (
            <article key={`${material.id}-${material.course_offering_id}`} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5">
              <div className="flex items-start gap-3 min-w-0">
                <span className="rounded-xl bg-[#EAF5FF] p-2.5 text-[#0A8FF5] shrink-0"><FileText className="w-5 h-5" /></span>
                <div className="min-w-0">
                  <h2 className="font-bold text-[#111111] break-words">{material.original_filename}</h2>
                  <p className="mt-1 text-xs text-[#71808C]">
                    {[material.subject_code, material.subject_name, material.section_code && `Section ${material.section_code}`].filter(Boolean).join(' · ')}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[#71808C]">
                    <span className="rounded-full bg-[#F4F7F9] px-2.5 py-1 font-semibold text-[#4D5963]">{materialLabels[material.source_type] || 'Course material'}</span>
                    <span>{formatFileSize(material.size_bytes)}</span>
                    <span>{new Date(material.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
              <a
                href={`${API_BASE_URL}/api/v1/sources/${material.id}/download`}
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700"
              >
                <Download className="w-4 h-4" /> Download
              </a>
            </article>
          ))}
        </div>
      ) : (
        <div className="border border-[#DCE7EE] rounded-[16px] bg-white p-10 sm:p-14 text-center">
          <div className="w-14 h-14 rounded-full bg-[#F4F7F9] flex items-center justify-center text-[#71808C] mx-auto mb-4 shadow-xs">
            <FileText className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-bold text-[#111111] mb-3">No study materials available yet</h2>
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#F4F7F9] text-xs font-semibold text-[#4D5963]">
            <HelpCircle className="w-4 h-4 text-[#0A8FF5]" />
            <span>Materials appear here after faculty uploads finish processing.</span>
          </div>
        </div>
      )}
    </div>
  );
};
