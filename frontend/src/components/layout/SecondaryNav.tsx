import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export interface SecondaryNavItem {
  id: string;
  label: string;
  route?: string;
}

interface SecondaryNavProps {
  activeTab?: string;
  onSelectTab?: (tabId: string) => void;
  role?: string | null;
}

export const SecondaryNav: React.FC<SecondaryNavProps> = ({ activeTab, onSelectTab, role }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const getNavItems = (): SecondaryNavItem[] => {
    switch (role) {
      case 'ADMIN':
        return [
          { id: 'dashboard', label: 'Overview', route: '/admin/dashboard' },
          { id: 'units', label: 'Academic Units', route: '/admin/academic/units' },
          { id: 'subjects', label: 'Canonical Subjects', route: '/admin/academic/subjects' },
          { id: 'curriculum', label: 'Curriculum Schemes', route: '/admin/curriculum/subjects' },
          { id: 'offerings', label: 'Course Offerings', route: '/admin/offerings' },
          { id: 'moderation', label: 'Moderation & Audit', route: '/admin/moderation' },
        ];
      case 'SUPER_ADMIN':
        return [
          { id: 'dashboard', label: 'Platform Overview', route: '/super-admin/dashboard' },
          { id: 'institutions', label: 'Institutions', route: '/super-admin/institutions' },
          { id: 'pipeline', label: 'AI Pipelines', route: '/super-admin/pipeline' },
          { id: 'audit', label: 'Security Audit', route: '/super-admin/audit' },
        ];
      case 'TEACHER':
        return [
          { id: 'doubts', label: 'Doubts', route: '/doubts' },
          { id: 'learn', label: 'Learn', route: '/courses' },
          { id: 'quiz', label: 'Quiz', route: '/quiz' },
          { id: 'pyq', label: 'PYQ', route: '/pyq' },
          { id: 'studymaterial', label: 'Study Material', route: '/materials' },
          { id: 'teacher_analytics', label: 'Analytics', route: '/analytics' },
        ];
      default:
        // STUDENT
        return [
          { id: 'doubts', label: 'Doubts', route: '/doubts' },
          { id: 'learn', label: 'Learn', route: '/courses' },
          { id: 'quiz', label: 'Quiz', route: '/quiz' },
          { id: 'pyq', label: 'PYQ', route: '/pyq' },
          { id: 'studymaterial', label: 'Study Material', route: '/materials' },
        ];
    }
  };

  const navItems = getNavItems();

  const handleItemClick = (item: SecondaryNavItem) => {
    if (onSelectTab) {
      onSelectTab(item.id);
    }
    if (item.route && location.pathname !== item.route) {
      navigate(item.route);
    }
  };

  const isItemActive = (item: SecondaryNavItem) => {
    if (activeTab) {
      return activeTab === item.id;
    }
    if (item.route) {
      return location.pathname === item.route;
    }
    return false;
  };

  return (
    <nav className="h-[46px] bg-white border-b border-[#E8EFF3] px-4 md:px-8 overflow-x-auto no-scrollbar">
      <div className="max-w-[1540px] mx-auto h-full flex items-center gap-7 sm:gap-9 whitespace-nowrap text-[14px]">
        {navItems.map((item) => {
          const active = isItemActive(item);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => handleItemClick(item)}
              className={`transition-colors cursor-pointer relative py-3 font-semibold ${
                active
                  ? 'text-[#111111] font-bold'
                  : 'text-[#4D5963] hover:text-[#111111]'
              }`}
            >
              <span>{item.label}</span>
              {active && (
                <span className="absolute bottom-0 left-0 right-0 h-[2.5px] bg-[#111111] rounded-full" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};
