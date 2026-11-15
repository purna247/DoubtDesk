import React from 'react';
import { School, ShieldCheck, Activity, ChevronRight, Server, FolderGit2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

export interface AdminRightSidebarProps {
  metrics?: {
    unitsCount?: number;
    canonicalSubjectsCount?: number;
    offeringsCount?: number;
    moderationFlagsCount?: number;
    auditTotalCount?: number;
  };
}

export const AdminRightSidebar: React.FC<AdminRightSidebarProps> = ({ metrics }) => {
  const { user } = useAuth();
  const institutionName = user?.institutionName || user?.institution_name || 'Academic Institution';

  return (
    <aside className="w-[290px] xl:w-[320px] 2xl:w-[340px] shrink-0 hidden lg:flex flex-col gap-4 sticky top-6">
      {/* 1. Tenant Overview Card */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
            <School className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold text-[#111111] leading-tight truncate">
              {institutionName}
            </h3>
            <p className="text-[11px] text-[#71808C] mt-0.5 font-medium">Institution Workspace</p>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs">
          <span className="text-slate-500 font-medium">Governance Mode</span>
          <span className="inline-flex items-center gap-1 font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full text-[10px]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Enforced
          </span>
        </div>
      </div>

      {/* 2. Operations & Health Summary Card */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <p className="text-[11px] font-bold uppercase tracking-wider text-[#0A8FF5] mb-3 flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" />
          Governance Telemetry
        </p>

        <div className="space-y-2.5">
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <FolderGit2 className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-semibold text-slate-700">Academic Units</span>
            </div>
            <span className="text-xs font-bold text-slate-900">{metrics?.unitsCount ?? '—'}</span>
          </div>

          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-semibold text-slate-700">Course Offerings</span>
            </div>
            <span className="text-xs font-bold text-slate-900">{metrics?.offeringsCount ?? '—'}</span>
          </div>

          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-slate-500" />
              <span className="text-xs font-semibold text-slate-700">Pending Flags</span>
            </div>
            <span className="text-xs font-bold text-amber-600">
              {metrics?.moderationFlagsCount ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Quick Action Shortcuts */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-2.5">
          Quick Navigation
        </p>
        <div className="space-y-1.5">
          <Link
            to="/admin/academic/units"
            className="flex items-center justify-between p-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-[#F4F8FB] hover:text-[#0A8FF5] transition"
          >
            <span>Manage Academic Units</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          </Link>
          <Link
            to="/admin/offerings"
            className="flex items-center justify-between p-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-[#F4F8FB] hover:text-[#0A8FF5] transition"
          >
            <span>Active Offerings</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          </Link>
          <Link
            to="/admin/moderation"
            className="flex items-center justify-between p-2 rounded-lg text-xs font-medium text-slate-700 hover:bg-[#F4F8FB] hover:text-[#0A8FF5] transition"
          >
            <span>Moderation & Audit</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
          </Link>
        </div>
      </div>
    </aside>
  );
};
