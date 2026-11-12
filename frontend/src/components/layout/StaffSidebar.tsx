import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  MessageSquare,
  BookOpen,
  FileText,
  LayoutDashboard,
  BrainCircuit,
  BarChart2,
  FolderGit2,
  ShieldCheck,
  Server,
  Award,
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

export const StaffSidebar: React.FC = () => {
  const { role } = useAuth();

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
      isActive
        ? 'bg-[#111111] text-white shadow-sm'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`;

  const renderTeacherLinks = () => (
    <>
      <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
        Faculty Studio
      </div>
      <NavLink to="/teacher/dashboard" className={navItemClass}>
        <LayoutDashboard className="w-4 h-4" /> Overview & Gaps
      </NavLink>
      <NavLink to="/teacher/courses" className={navItemClass}>
        <BrainCircuit className="w-4 h-4" /> Course Studio
      </NavLink>
      <NavLink to="/teacher/quizzes" className={navItemClass}>
        <Award className="w-4 h-4" /> Quiz Studio
      </NavLink>
      <NavLink to="/teacher/analytics" className={navItemClass}>
        <BarChart2 className="w-4 h-4" /> Concept Analytics
      </NavLink>
      <NavLink to="/teacher/dashboard?tab=doubts" className={navItemClass}>
        <MessageSquare className="w-4 h-4" /> Course Doubts
      </NavLink>
    </>
  );

  const renderAdminLinks = () => (
    <>
      <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
        Institution Admin
      </div>
      <NavLink to="/admin/dashboard" className={navItemClass}>
        <LayoutDashboard className="w-4 h-4" /> Institution Overview
      </NavLink>
      <NavLink to="/admin/academic/units" className={navItemClass}>
        <FolderGit2 className="w-4 h-4" /> Academic Units
      </NavLink>
      <NavLink to="/admin/academic/subjects" className={navItemClass}>
        <BookOpen className="w-4 h-4" /> Canonical Subjects
      </NavLink>
      <NavLink to="/admin/curriculum/subjects" className={navItemClass}>
        <FileText className="w-4 h-4" /> Curriculum Schemes
      </NavLink>
      <NavLink to="/admin/offerings" className={navItemClass}>
        <Server className="w-4 h-4" /> Course Offerings
      </NavLink>
      <NavLink to="/admin/moderation" className={navItemClass}>
        <ShieldCheck className="w-4 h-4" /> Moderation & Audit
      </NavLink>
    </>
  );

  const renderSuperAdminLinks = () => (
    <>
      <div className="px-3 pb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
        Platform Governance
      </div>
      <NavLink to="/super-admin/dashboard" className={navItemClass}>
        <LayoutDashboard className="w-4 h-4" /> Platform Overview
      </NavLink>
      <NavLink to="/super-admin/institutions" className={navItemClass}>
        <Server className="w-4 h-4" /> Institutions
      </NavLink>
      <NavLink to="/super-admin/pipeline" className={navItemClass}>
        <BrainCircuit className="w-4 h-4" /> AI Pipelines
      </NavLink>
      <NavLink to="/super-admin/audit" className={navItemClass}>
        <ShieldCheck className="w-4 h-4" /> Security Audit
      </NavLink>
    </>
  );

  return (
    <aside className="w-64 border-r border-[#DCE7EE] bg-white min-h-[calc(100vh-57px)] p-4 flex flex-col justify-between hidden md:flex shrink-0">
      <nav className="flex flex-col space-y-1">
        {role === 'SUPER_ADMIN' && renderSuperAdminLinks()}
        {role === 'ADMIN' && renderAdminLinks()}
        {role === 'TEACHER' && renderTeacherLinks()}
        {role === 'STUDENT' && (
          <NavLink to="/doubts" className={navItemClass}>
            <MessageSquare className="w-4 h-4" /> Back to Doubts Feed
          </NavLink>
        )}
      </nav>
    </aside>
  );
};

