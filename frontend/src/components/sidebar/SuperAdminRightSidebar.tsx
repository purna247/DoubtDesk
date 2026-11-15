import React from 'react';
import { ShieldCheck, Activity, BrainCircuit, Server, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const SuperAdminRightSidebar: React.FC = () => {
  const { user } = useAuth();

  return (
    <aside className="w-[290px] xl:w-[320px] 2xl:w-[340px] shrink-0 hidden lg:flex flex-col gap-4 sticky top-6">
      {/* 1. Root Platform Card */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-800 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-bold text-[#111111] leading-tight truncate">
              Root Governance
            </h3>
            <p className="text-[11px] text-[#71808C] mt-0.5 font-medium truncate">
              {user?.email || 'superadmin@doubtdesk'}
            </p>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs">
          <span className="text-slate-500 font-medium">Session Status</span>
          <span className="inline-flex items-center gap-1 font-bold text-purple-800 bg-purple-50 px-2 py-0.5 rounded-full text-[10px] border border-purple-200">
            MFA Active
          </span>
        </div>
      </div>

      {/* 2. Platform Telemetry Card */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <p className="text-[11px] font-bold uppercase tracking-wider text-purple-700 mb-3 flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5" />
          Cluster Telemetry
        </p>

        <div className="space-y-2.5">
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-purple-600" />
              <span className="text-xs font-semibold text-slate-700">Tenants</span>
            </div>
            <span className="text-xs font-bold text-slate-900">1 Online</span>
          </div>

          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-semibold text-slate-700">Workers</span>
            </div>
            <span className="text-xs font-bold text-emerald-600">Operational</span>
          </div>

          <div className="flex items-center justify-between p-2.5 rounded-xl bg-[#F8FAFC] border border-[#E8EFF3]">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-semibold text-slate-700">AI Pipelines</span>
            </div>
            <span className="text-xs font-bold text-blue-600">Failover Ready</span>
          </div>
        </div>
      </div>

      {/* 3. Immutable Security Ledger Status */}
      <div className="sidebar-card border border-[#DCE7EE] rounded-[16px] bg-white p-4 sm:p-5 shadow-xs">
        <div className="flex items-center gap-2 text-emerald-700 mb-2">
          <CheckCircle2 className="w-4 h-4" />
          <span className="text-xs font-bold">Audit Ledger Synced</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-relaxed">
          Zero integrity violations detected across active tenant partitions. Append-only ledger active.
        </p>
      </div>
    </aside>
  );
};
