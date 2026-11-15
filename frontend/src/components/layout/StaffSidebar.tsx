import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  MessageSquare,
  BookOpen,
  FileText,
  LayoutDashboard,
  BrainCircuit,
  FolderGit2,
  ShieldCheck,
  Server,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const StaffSidebar: React.FC = () => {
  const { role } = useAuth();

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 w-full h-[40px] px-3 rounded-full transition-colors cursor-pointer text-left ${
      isActive
        ? 'bg-[#EBF2F7] text-[#111111] font-bold shadow-xs'
        : 'text-[#2D3748] hover:bg-[#F4F7F9] font-medium'
    }`;

  const renderAdminLinks = () => (
    <>
      <h2 className="text-[14px] font-extrabold text-[#111111] mb-2 px-3 uppercase tracking-wide">
        Administration
      </h2>
      <div className="flex flex-col gap-0.5">
        <NavLink to="/admin/dashboard" className={navItemClass}>
          <LayoutDashboard className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Overview</span>
        </NavLink>
        <NavLink to="/admin/academic/units" className={navItemClass}>
          <FolderGit2 className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Academic Units</span>
        </NavLink>
        <NavLink to="/admin/academic/subjects" className={navItemClass}>
          <BookOpen className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Canonical Subjects</span>
        </NavLink>
        <NavLink to="/admin/curriculum/subjects" className={navItemClass}>
          <FileText className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Curriculum Schemes</span>
        </NavLink>
        <NavLink to="/admin/offerings" className={navItemClass}>
          <Server className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Course Offerings</span>
        </NavLink>
        <NavLink to="/admin/moderation" className={navItemClass}>
          <ShieldCheck className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Moderation & Audit</span>
        </NavLink>
      </div>
    </>
  );

  const renderSuperAdminLinks = () => (
    <>
      <h2 className="text-[14px] font-extrabold text-[#111111] mb-2 px-3 uppercase tracking-wide">
        Governance
      </h2>
      <div className="flex flex-col gap-0.5">
        <NavLink to="/super-admin/dashboard" className={navItemClass}>
          <LayoutDashboard className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Overview</span>
        </NavLink>
        <NavLink to="/super-admin/institutions" className={navItemClass}>
          <Server className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Institutions</span>
        </NavLink>
        <NavLink to="/super-admin/pipeline" className={navItemClass}>
          <BrainCircuit className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">AI Pipelines</span>
        </NavLink>
        <NavLink to="/super-admin/audit" className={navItemClass}>
          <ShieldCheck className="w-4 h-4 text-[#111111] shrink-0" />
          <span className="text-[13px] truncate">Security Audit</span>
        </NavLink>
      </div>
    </>
  );

  return (
    <aside className="w-[190px] xl:w-[210px] 2xl:w-[220px] shrink-0 hidden md:block">
      <nav className="flex flex-col space-y-4">
        {role === 'SUPER_ADMIN' && renderSuperAdminLinks()}
        {role === 'ADMIN' && renderAdminLinks()}
        {(role === 'STUDENT' || role === 'TEACHER') && (
          <NavLink to="/doubts" className={navItemClass}>
            <MessageSquare className="w-4 h-4 text-[#111111] shrink-0" />
            <span className="text-[13px] truncate">Doubts Feed</span>
          </NavLink>
        )}
      </nav>
    </aside>
  );
};
