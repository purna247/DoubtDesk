import React from 'react';
import { Server, ShieldCheck, BrainCircuit, Activity, Plus } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const SuperAdminDashboardPage: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200 mb-1.5">
            <ShieldCheck className="w-3 h-3" /> MFA Session Active
          </div>
          <h1 className="text-xl font-bold text-[#111111]">Platform Governance Console</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Root Administrator: {user?.email || 'superadmin@doubtdesk.platform'}
          </p>
        </div>

        <button className="btn-primary bg-purple-700 hover:bg-purple-800 text-xs flex items-center gap-1.5">
          <Plus className="w-3.5 h-3.5" /> Onboard Institution
        </button>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-base p-4">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Tenant Institutions</span>
            <Server className="w-4 h-4 text-purple-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">1</p>
          <p className="text-[11px] text-slate-400 mt-1">OUTR Bhubaneswar (Active)</p>
        </div>

        <div className="card-base p-4">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Background Workers</span>
            <Activity className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-black text-emerald-600">Operational</p>
          <p className="text-[11px] text-slate-400 mt-1">PostgreSQL Queue Leases</p>
        </div>

        <div className="card-base p-4">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">AI Pipelines</span>
            <BrainCircuit className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">Standard</p>
          <p className="text-[11px] text-slate-400 mt-1">Provider Failover Ready</p>
        </div>

        <div className="card-base p-4">
          <div className="flex items-center justify-between text-slate-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">Security Audits</span>
            <ShieldCheck className="w-4 h-4 text-slate-600" />
          </div>
          <p className="text-2xl font-black text-slate-900">0 Alerts</p>
          <p className="text-[11px] text-slate-400 mt-1">Immutable audit ledger active</p>
        </div>
      </div>
    </div>
  );
};

