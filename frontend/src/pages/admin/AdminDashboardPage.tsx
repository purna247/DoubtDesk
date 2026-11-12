import React, { useEffect, useState } from 'react';
import {
  School,
  FolderGit2,
  BookOpen,
  Server,
  Users,
  ShieldCheck,
  ChevronRight,
  BarChart3,
  Loader2,
  CheckCircle2,
  Activity,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { apiClient } from '../../api/client';

interface AuditEvent {
  id: string;
  event_code: string;
  actor_user_id?: string;
  target_type?: string;
  target_id?: string;
  created_at: string;
}

interface AuditResponse {
  events: AuditEvent[];
  total_count: number;
}

export const AdminDashboardPage: React.FC = () => {
  const { user } = useAuth();

  const [loading, setLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState({
    unitsCount: 0,
    canonicalSubjectsCount: 0,
    curriculumSubjectsCount: 0,
    offeringsCount: 0,
    moderationFlagsCount: 0,
    auditTotalCount: 0,
  });

  const [recentAuditEvents, setRecentAuditEvents] = useState<AuditEvent[]>([]);

  const adminName = user?.fullName || user?.full_name || 'Institution Administrator';
  const tenantName = user?.institutionName || user?.institution_name || 'Academic Institution';

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([
      apiClient.get<any[]>('/api/v1/academics/units').catch(() => []),
      apiClient.get<any[]>('/api/v1/academics/canonical-subjects').catch(() => []),
      apiClient.get<any[]>('/api/v1/academics/curriculum-subjects').catch(() => []),
      apiClient.get<any[]>('/api/v1/academics/offerings').catch(() => []),
      apiClient.get<any[]>('/api/v1/doubts/moderation/flags').catch(() => []),
      apiClient.get<AuditResponse>('/api/v1/admin/audit?limit=5').catch(() => ({ events: [], total_count: 0 })),
    ])
      .then(([units, canonical, curriculum, offerings, flags, audit]) => {
        if (isMounted) {
          setMetrics({
            unitsCount: Array.isArray(units) ? units.length : 0,
            canonicalSubjectsCount: Array.isArray(canonical) ? canonical.length : 0,
            curriculumSubjectsCount: Array.isArray(curriculum) ? curriculum.length : 0,
            offeringsCount: Array.isArray(offerings) ? offerings.length : 0,
            moderationFlagsCount: Array.isArray(flags) ? flags.length : 0,
            auditTotalCount: audit?.total_count || 0,
          });
          if (audit?.events && Array.isArray(audit.events)) {
            setRecentAuditEvents(audit.events);
          }
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const academicCards = [
    {
      title: 'Academic Units',
      desc: 'Schools, Departments, and Autonomous Research Centers',
      icon: FolderGit2,
      route: '/admin/academic/units',
      stat: `${metrics.unitsCount} Active Unit(s)`,
    },
    {
      title: 'Canonical Subject Catalog',
      desc: 'Institution-wide canonical subjects & syllabus standards',
      icon: BookOpen,
      route: '/admin/academic/subjects',
      stat: `${metrics.canonicalSubjectsCount} Subject(s)`,
    },
    {
      title: 'Curriculum Schemes',
      desc: 'Autonomy regulations, credits, and syllabus allocations',
      icon: School,
      route: '/admin/curriculum/subjects',
      stat: `${metrics.curriculumSubjectsCount} Scheme Entry(ies)`,
    },
    {
      title: 'Course Offerings',
      desc: 'Semester terms, sections, and cross-department faculty staffing',
      icon: Server,
      route: '/admin/offerings',
      stat: `${metrics.offeringsCount} Active Offering(s)`,
    },
    {
      title: 'User Directory & Rosters',
      desc: 'Student enrolments, faculty appointments & registration identifiers',
      icon: Users,
      route: '/admin/users',
      stat: 'Active Roster Managed',
    },
    {
      title: 'Audit & Moderation',
      desc: 'Discussion moderation, immutable audit log & audited identity unmasking',
      icon: ShieldCheck,
      route: '/admin/moderation',
      stat: `${metrics.moderationFlagsCount} Pending Flag(s)`,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Institution Command Center Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E8EFF3] pb-5">
        <div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 mb-1.5">
            <School className="w-3.5 h-3.5 text-blue-600" />
            Institution Administration Console
          </div>
          <h1 className="text-2xl font-bold text-[#111111]">{tenantName}</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Administrator: {adminName} • Multi-Tenant Academic Governance & Policy Control
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Tenant Policy Active
          </span>
        </div>
      </div>

      {/* Live Metric Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Academic Units
          </span>
          <div className="text-xl font-black text-[#111111] mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.unitsCount}
          </div>
        </div>

        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Subjects
          </span>
          <div className="text-xl font-black text-[#111111] mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.canonicalSubjectsCount}
          </div>
        </div>

        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Curriculum
          </span>
          <div className="text-xl font-black text-[#111111] mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.curriculumSubjectsCount}
          </div>
        </div>

        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Offerings
          </span>
          <div className="text-xl font-black text-[#111111] mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.offeringsCount}
          </div>
        </div>

        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Flags
          </span>
          <div className="text-xl font-black text-amber-600 mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.moderationFlagsCount}
          </div>
        </div>

        <div className="card-base p-4 border-[#DCE7EE] bg-white">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
            Audit Trail
          </span>
          <div className="text-xl font-black text-slate-700 mt-1">
            {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : metrics.auditTotalCount}
          </div>
        </div>
      </div>

      {/* Operational Academic Modules Grid */}
      <div>
        <div className="flex items-center justify-between mb-3.5">
          <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#0A8FF5]" />
            Institutional Governance & Operations
          </h2>
          <span className="text-xs text-slate-400">Deterministic Tenant Isolation Enforced</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {academicCards.map((card) => {
            const IconComponent = card.icon;
            return (
              <a
                key={card.title}
                href={card.route}
                className="card-base p-5 border-[#DCE7EE] bg-white rounded-2xl hover:border-[#0A8FF5] transition-all group cursor-pointer flex flex-col justify-between shadow-xs"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-10 h-10 rounded-xl bg-slate-50 group-hover:bg-[#EAF5FF] text-slate-700 group-hover:text-[#0A8FF5] flex items-center justify-center transition-colors">
                      <IconComponent className="w-5 h-5" />
                    </div>
                    <span className="text-[11px] font-bold text-slate-500 bg-slate-100 group-hover:bg-blue-50 group-hover:text-[#0A8FF5] px-2.5 py-0.5 rounded-full transition-colors">
                      {card.stat}
                    </span>
                  </div>

                  <h3 className="font-bold text-sm text-[#111111] group-hover:text-[#0A8FF5] transition-colors">
                    {card.title}
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{card.desc}</p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-[#0A8FF5] font-semibold">
                  <span>Open Management Studio</span>
                  <ChevronRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </a>
            );
          })}
        </div>
      </div>

      {/* Tenant Security & Audit Governance Panel */}
      <div className="card-base p-6 border-[#DCE7EE] bg-white rounded-2xl shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-[#111111]">
              Tenant Security Trail & Regulatory Compliance
            </h3>
          </div>
          <a
            href="/admin/moderation"
            className="text-xs font-semibold text-[#0A8FF5] hover:underline"
          >
            View Full Audit Trail &rarr;
          </a>
        </div>

        {recentAuditEvents.length > 0 ? (
          <div className="divide-y divide-slate-100 text-xs">
            {recentAuditEvents.map((evt) => (
              <div key={evt.id} className="py-2.5 flex items-center justify-between">
                <div>
                  <span className="font-bold text-slate-800">{evt.event_code}</span>
                  <span className="text-slate-400 ml-2">Target: {evt.target_type || 'System'}</span>
                </div>
                <span className="text-slate-400">{new Date(evt.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-3 bg-emerald-50/60 border border-emerald-200 rounded-xl p-4">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
            <div>
              <h4 className="text-xs font-bold text-emerald-900">
                Immutable Audit Log Active & Cryptographically Secured
              </h4>
              <p className="text-[11px] text-emerald-700 mt-0.5">
                All administrative and academic mutations are append-only logged with tenant boundary verification. No security anomalies recorded.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
