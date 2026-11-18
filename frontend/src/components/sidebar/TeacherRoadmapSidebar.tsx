import React from 'react';
import { BookOpen, ChevronDown, Layers, Loader2 } from 'lucide-react';
import { useTeacherLearn } from '../../contexts/TeacherLearnContext';

export const TeacherRoadmapSidebar: React.FC = () => {
  const {
    offerings,
    offeringId,
    setOfferingId,
    nodes,
    groupedNodes,
    selectedId,
    selectNode,
    loading,
  } = useTeacherLearn();

  return (
    <nav
      aria-label="Roadmap Outline"
      className="rounded-[16px] border border-[#DCE7EE] bg-white p-3.5 shadow-xs space-y-3 sticky top-20 max-h-[calc(100vh-100px)] overflow-y-auto"
    >
      {/* 1. Optional Course Offering Switcher if teacher has multiple courses */}
      {offerings.length > 1 && (
        <div className="px-1 pb-2.5 border-b border-[#DCE7EE]">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#71808C] block mb-1">
            Assigned Course
          </span>
          <div className="relative">
            <select
              value={offeringId}
              onChange={(e) => setOfferingId(e.target.value)}
              className="w-full appearance-none text-xs font-semibold rounded-lg border border-[#DCE7EE] bg-white px-2.5 py-1.5 pr-7 text-[#111111] focus:outline-none focus:ring-1 focus:ring-[#0A8FF5] cursor-pointer"
            >
              {offerings.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.official_subject_code} · {o.subject_name || 'Course'} {o.section_code ? `(Sec ${o.section_code})` : ''}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-[#71808C] absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>
      )}

      {/* 2. Roadmap Header */}
      <div className="flex items-center justify-between px-2 pb-2 border-b border-[#DCE7EE]">
        <h2 className="text-xs font-bold uppercase tracking-wider text-[#71808C] flex items-center gap-1.5">
          <BookOpen className="h-3.5 w-3.5 text-[#0A8FF5]" />
          Roadmap Topics ({nodes.length})
        </h2>
      </div>

      {/* 3. Topics List */}
      {loading ? (
        <div className="py-8 text-center text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-[#0A8FF5]" />
          <span className="text-xs">Loading topics…</span>
        </div>
      ) : groupedNodes.length ? (
        <div className="space-y-4">
          {groupedNodes.map(([moduleTitle, moduleNodes]) => (
            <div key={moduleTitle} className="space-y-1">
              <p
                className="px-1 text-[10px] font-bold uppercase tracking-wide text-slate-400 truncate"
                title={moduleTitle}
              >
                {moduleTitle}
              </p>
              <div className="space-y-1">
                {moduleNodes.map((node) => {
                  const isSelected = selectedId === node.id;
                  const isPublished = node.status === 'published';
                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => selectNode(node.id)}
                      className={`w-full rounded-xl px-3 py-2.5 text-left transition flex items-start gap-2.5 cursor-pointer ${
                        isSelected
                          ? 'bg-[#EAF5FF] text-[#0A8FF5] font-semibold border border-[#B8D9F5]'
                          : 'text-[#111111] hover:bg-[#F4F7F9] border border-transparent'
                      }`}
                    >
                      <span className="text-[11px] font-mono text-[#71808C] mt-0.5">
                        {node.sequence_no}.
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs leading-snug line-clamp-2">{node.title}</p>
                        {!isPublished && (
                          <div className="mt-1 flex items-center gap-1">
                            <span className="inline-block rounded-full px-2 py-0.5 text-[9px] font-bold uppercase bg-amber-50 text-amber-800 border border-amber-200">
                              Draft
                            </span>
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-4 text-center space-y-2">
          <Layers className="h-6 w-6 text-slate-300 mx-auto" />
          <p className="text-xs text-[#71808C]">No roadmap topics yet.</p>
          <p className="text-[11px] text-slate-400">Upload syllabus materials or generate a roadmap.</p>
        </div>
      )}
    </nav>
  );
};
